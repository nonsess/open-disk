import os
from typing import List, Dict, Optional, Tuple, Set
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
    ) -> Tuple[List[StoredFile], List[Folder], List[Dict[str, str]]]:
        files = StoredFile.objects.filter(
            owner=user,
            path=current_path
        ).order_by('original_name')
        
        folders = Folder.objects.filter(
            owner=user,
            path=current_path
        ).order_by('name')
        
        breadcrumbs = StorageService._build_breadcrumbs(current_path)
        
        return files, folders, breadcrumbs
    
    @staticmethod
    def _build_breadcrumbs(current_path: str) -> List[Dict[str, str]]:
        breadcrumbs = [{'name': 'Главная', 'path': ''}]
        
        if not current_path:
            return breadcrumbs
        
        parts = current_path.split('/')
        accumulated = ''
        
        for part in parts:
            if accumulated:
                accumulated += '/' + part
            else:
                accumulated = part
            
            breadcrumbs.append({
                'name': part,
                'path': accumulated
            })
        
        return breadcrumbs
    
    @staticmethod
    def create_folder(
        user: User, 
        name: str, 
        path: str = ""
    ) -> Tuple[bool, str, Optional[Folder]]:
        try:
            Folder._validate_name(name)
            if path:
                Folder._validate_path(path)
                        
            full_path = f"{path}/{name}" if path else name
            
            minio_client = MinIOClient()
            success, message = minio_client.create_folder(user, full_path)
            
            if not success:
                return False, message, None
            
            folder = Folder.objects.create(
                owner=user,
                name=name,
                path=full_path
            )
            
            return True, f"Папка '{name}' успешно создана.", folder
            
        except ValidationError as e:
            return False, str(e), None
        except IntegrityError:
            return False, "Папка с таким названием уже существует.", None
        except Exception as e:
            return False, f"Ошибка создания папки: {str(e)}", None
    
    @staticmethod
    def upload_files(
        user: User,
        files: List[UploadedFile],
        relative_paths: List[str]
    ) -> Tuple[int, List[str]]:
        uploaded_count = 0
        errors: List[str] = []
        folder_paths: Set[str] = set()
        
        for uploaded_file, rel_path in zip(files, relative_paths):
            try:
                rel_path = MinIOClient.normalize_path(rel_path)
                
                folder_path = os.path.dirname(rel_path)
                file_name = os.path.basename(rel_path)
                
                StoredFile._validate_filename(file_name)
                
                if folder_path:
                    Folder._validate_path(folder_path)
                
                stored_file = StoredFile(
                    owner=user,
                    original_name=file_name,
                    size=uploaded_file.size,
                    mime_type=uploaded_file.content_type or 'application/octet-stream',
                    path=folder_path
                )
                
                full_path = f"user-{user.id}-files/{rel_path}"
                stored_file.file.save(full_path, uploaded_file, save=True)
                
                if folder_path:
                    parts = folder_path.split('/')
                    accumulated = ''
                    for part in parts:
                        if accumulated:
                            accumulated += '/' + part
                        else:
                            accumulated = part
                        folder_paths.add(accumulated)
                
                uploaded_count += 1
                
            except ValidationError as e:
                errors.append(f"{rel_path}: {str(e)}")
            except Exception as e:
                errors.append(f"{rel_path}: {str(e)}")
        
        StorageService._create_missing_folders(user, folder_paths)
        
        return uploaded_count, errors
    
    @staticmethod
    def _create_missing_folders(user: User, folder_paths: Set[str]) -> None:
        for full_folder_path in folder_paths:
            if '/' in full_folder_path:
                parent_path = '/'.join(full_folder_path.split('/')[:-1])
                folder_name = full_folder_path.split('/')[-1]
            else:
                parent_path = ''
                folder_name = full_folder_path
            
            Folder.objects.get_or_create(
                owner=user,
                path=parent_path,
                name=folder_name
            )
    
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
    def delete_folder(user: User, folder_path: str) -> Tuple[bool, str, str]:
        try:
            folder_path = MinIOClient.normalize_path(folder_path)
            
            if not folder_path:
                folder_name = "корневую папку"
                redirect_path = ''
            else:
                parts = folder_path.split('/')
                folder_name = parts[-1] if parts else "папку"
                
                if len(parts) > 1:
                    redirect_path = '/'.join(parts[:-1])
                else:
                    redirect_path = ''
            
            files_query = StoredFile.objects.filter(
                owner=user,
                path=folder_path
            )
            
            files_deleted_count = files_query.count()
            
            for file_obj in files_query:
                try:
                    file_obj.file.delete(save=False)
                except Exception:
                    pass
            
            files_query.delete()
            
            subfolders_query = Folder.objects.filter(
                owner=user,
                path=folder_path
            )
            subfolders_count = subfolders_query.count()
            subfolders_query.delete()
            
            if folder_path:
                if '/' in folder_path:
                    parts = folder_path.split('/')
                    parent_path = '/'.join(parts[:-1])
                    current_folder_name = parts[-1]
                else:
                    parent_path = ''
                    current_folder_name = folder_path
                
                Folder.objects.filter(
                    owner=user,
                    path=parent_path,
                    name=current_folder_name
                ).delete()
            
            minio_client = MinIOClient()
            minio_success, minio_message = minio_client.delete_folder(
                user, folder_path
            )
            
            message = f"Папка '{folder_name}' удалена."
            if files_deleted_count > 0:
                message += f" Удалено {files_deleted_count} файлов."
            if subfolders_count > 0:
                message += f" Удалено {subfolders_count} подпапок."
            
            if not minio_success:
                message += f" Внимание при удалении из хранилища: {minio_message}"
            
            return True, message, redirect_path
            
        except Exception as e:
            return False, f"Ошибка при удаления папки: {str(e)}", ""

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