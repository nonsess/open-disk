import os
from typing import List, Dict, Optional, Tuple
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile

from storage.models import Folder, StoredFile
from storage.minio_client import MinIOClient


class StorageService:
    @staticmethod
    def get_folder_contents(
        user: User, 
        current_path: str = ""
    ) -> Tuple[List[StoredFile], List[Folder], List[Dict[str, str]], Optional[Folder]]:
        current_folder = None
        if current_path:
            current_folder = Folder.find_by_path(user, current_path)
            if not current_folder:
                return [], [], [], None
        
        files = StoredFile.objects.filter(
            owner=user,
            folder=current_folder
        ).order_by('original_name')
        
        folders = Folder.objects.filter(
            owner=user,
            parent=current_folder
        ).order_by('name')
        
        breadcrumbs = [{'name': 'Главная', 'path': ''}]
        
        if current_folder:
            ancestors = current_folder.get_ancestors()
            for ancestor in ancestors:
                breadcrumbs.append({
                    'name': ancestor.name,
                    'path': ancestor.full_path
                })
            breadcrumbs.append({
                'name': current_folder.name,
                'path': current_folder.full_path
            })
        
        return files, folders, breadcrumbs, current_folder
    
    @staticmethod
    def create_folder(
        user: User, 
        name: str, 
        parent_path: str = ""
    ) -> Tuple[bool, str, Optional[Folder]]:
        try:
            Folder._validate_name(name)
            
            parent = None
            if parent_path:
                parent = Folder.find_by_path(user, parent_path)
                if not parent:
                    return False, "Родительская папка не найдена", None
            
            existing = Folder.objects.filter(
                owner=user,
                parent=parent,
                name=name
            ).first()
            
            if existing:
                return False, "Папка с таким названием уже существует", None
            
            minio_client = MinIOClient()
            
            full_path = name
            if parent:
                full_path = f"{parent.full_path}/{name}"
            
            success, message = minio_client.create_folder(user, full_path)
            
            if not success:
                return False, message, None
            
            folder = Folder.objects.create(
                owner=user,
                parent=parent,
                name=name
            )
            
            return True, f"Папка '{name}' успешно создана", folder
            
        except ValidationError as e:
            return False, str(e), None
        except IntegrityError:
            return False, "Папка с таким названием уже существует.", None
        except Exception as e:
            return False, f"Ошибка создания папки: {str(e)}", None
    
    @staticmethod
    @transaction.atomic
    def rename_folder(
        user: User,
        folder_id: int,
        new_name: str
    ) -> Tuple[bool, str, Optional[Folder]]:
        try:
            try:
                folder = Folder.objects.get(pk=folder_id, owner=user)
            except Folder.DoesNotExist:
                return False, "Папка не найдена", None
            
            old_name = folder.name
            old_full_path = folder.full_path
            
            minio_client = MinIOClient()
            
            temp_new_name = folder.name
            folder.name = new_name
            new_full_path = folder.full_path
            folder.name = temp_new_name
            
            success, message = minio_client.rename_folder(
                user=user,
                old_path=old_full_path,
                new_name=new_name
            )
            
            if not success:
                return False, message, None
            
            result = folder.rename(new_name)
            
            return True, f"Папка '{old_name}' переименована в '{new_name}'", folder
            
        except ValidationError as e:
            return False, str(e), None
        except Exception as e:
            return False, f"Ошибка переименования папки: {str(e)}", None
    
    @staticmethod
    @transaction.atomic
    def delete_folder(
        user: User,
        folder_id: int
    ) -> Tuple[bool, str, str]:
        try:
            try:
                folder = Folder.objects.get(pk=folder_id, owner=user)
            except Folder.DoesNotExist:
                return False, "Папка не найдена", ""
            
            folder_name = folder.name
            folder_path = folder.full_path
            
            redirect_path = ""
            if folder.parent:
                redirect_path = folder.parent.full_path
            
            minio_client = MinIOClient()
            minio_success, minio_message = minio_client.delete_folder(
                user, folder_path
            )
            
            if not minio_success:
                return False, f"Ошибка при удалении из хранилища: {minio_message}", redirect_path
            
            result = Folder.delete_with_content(folder_id, user)
            
            message = f"Папка '{folder_name}' удалена."
            if result['files_deleted'] > 0:
                message += f" Удалено {result['files_deleted']} файлов."
            if result['folders_deleted'] > 1:
                message += f" Удалено {result['folders_deleted'] - 1} подпапок."
            
            return True, message, redirect_path
            
        except Exception as e:
            return False, f"Ошибка при удалении папки: {str(e)}", ""
    
    @staticmethod
    def upload_files(
        user: User,
        files: List[UploadedFile],
        relative_paths: List[str]
    ) -> Tuple[int, List[str]]:
        uploaded_count = 0
        errors: List[str] = []
        
        for uploaded_file, rel_path in zip(files, relative_paths):
            try:
                rel_path = MinIOClient.normalize_path(rel_path)
                
                folder_path = os.path.dirname(rel_path)
                file_name = os.path.basename(rel_path)
                
                StoredFile._validate_filename(file_name)
                
                folder = None
                if folder_path:
                    folder = Folder.find_or_create_by_path(user, folder_path)
                
                existing_file = StoredFile.objects.filter(
                    owner=user,
                    folder=folder,
                    original_name=file_name
                ).first()
                
                if existing_file:
                    errors.append(f"{rel_path}: Файл с таким именем уже существует")
                    continue
                
                stored_file = StoredFile(
                    owner=user,
                    folder=folder,
                    original_name=file_name,
                    size=uploaded_file.size,
                    mime_type=uploaded_file.content_type or 'application/octet-stream'
                )
                
                full_path = f"user-{user.id}-files/{rel_path}"
                stored_file.file.save(full_path, uploaded_file, save=True)
                
                uploaded_count += 1
                
            except ValidationError as e:
                errors.append(f"{rel_path}: {str(e)}")
            except Exception as e:
                errors.append(f"{rel_path}: {str(e)}")
        
        return uploaded_count, errors
    
    @staticmethod
    def delete_file(user: User, file_id: int) -> Tuple[bool, str]:
        try:
            file_obj = StoredFile.objects.get(pk=file_id, owner=user)
            
            file_obj.file.delete(save=False)
            
            file_obj.delete()
            
            return True, "Файл успешно удалён."
            
        except StoredFile.DoesNotExist:
            return False, "Файл не найден."
        except Exception as e:
            return False, f"Ошибка при удалении файла: {str(e)}"
    

    @staticmethod
    @transaction.atomic
    def rename_file(
        user: User,
        file_id: int,
        new_name: str
    ) -> Tuple[bool, str, Optional[StoredFile]]:
        try:
            try:
                file_obj = StoredFile.objects.get(pk=file_id, owner=user)
            except StoredFile.DoesNotExist:
                return False, "Файл не найден", None
            
            old_name = file_obj.original_name
            
            old_storage_path = file_obj.file.name
            
            if not old_storage_path.startswith(f"user-{user.id}-files/"):
                return False, f"Некорректный путь файла: {old_storage_path}", None
            
            path_parts = old_storage_path.rsplit('/', 1)
            if len(path_parts) == 2:
                directory = path_parts[0] + '/'
                new_storage_path = directory + new_name
            else:
                new_storage_path = new_name
                        
            minio_client = MinIOClient()
            
            success, message = minio_client.rename_object(
                old_key=old_storage_path,
                new_key=new_storage_path
            )
            
            if not success:
                return False, message, None
            
            file_obj.original_name = new_name
            file_obj.file.name = new_storage_path
            file_obj.save()
            
            return True, f"Файл '{old_name}' переименован в '{new_name}'", file_obj
            
        except ValidationError as e:
            return False, str(e), None
        except Exception as e:
            return False, f"Ошибка переименования файла: {str(e)}", None


    @staticmethod
    def validate_upload_data(
        files: List[UploadedFile],
        relative_paths: List[str]
    ) -> Optional[str]:
        if not files:
            return "Файл(ы) не выбраны."
        
        if len(files) != len(relative_paths):
            return "Ошибка при загрузке структуры папок."
        
        return None
    
    @staticmethod
    def find_folder_by_path(user: User, path: str) -> Optional[Folder]:
        return Folder.find_by_path(user, path)
    
    @staticmethod
    def get_folder_by_id(user: User, folder_id: int) -> Optional[Folder]:
        try:
            return Folder.objects.get(pk=folder_id, owner=user)
        except Folder.DoesNotExist:
            return None
    
    @staticmethod
    def search_files(user: User, query: str) -> List[StoredFile]:
        if not query:
            return []

        return StoredFile.objects.filter(
            owner=user,
            original_name__icontains=query
        ).order_by('original_name')