import os
from typing import List, Dict, Optional, Tuple
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile
from concurrent.futures import ThreadPoolExecutor, as_completed

from storage.models import Folder, StoredFile


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
        ).order_by('display_name')
        
        folders = Folder.objects.filter(
            owner=user,
            parent=current_folder
        ).order_by('name')
        
        if current_folder:
            breadcrumbs = current_folder.get_breadcrumbs()
        else:
            breadcrumbs = [{'name': 'Главная', 'path': ''}]
        
        return files, folders, breadcrumbs, current_folder
    
    @staticmethod
    def create_folder(
        user: User, 
        name: str, 
        parent_path: str = ""
    ) -> Tuple[bool, str, Optional[Folder]]:
        try:
            parent = None
            if parent_path:
                parent = Folder.find_by_path(user, parent_path)
                if not parent:
                    return False, "Родительская папка не найдена", None
            
            folder = Folder.objects.create(
                owner=user,
                parent=parent,
                name=name
            )
            
            return True, f"Папка '{name}' создана", folder
            
        except ValidationError as e:
            return False, str(e), None
        except IntegrityError:
            return False, f"Папка '{name}' уже существует", None
        except Exception as e:
            return False, f"Ошибка: {str(e)}", None
    
    @staticmethod
    @transaction.atomic
    def rename_folder(
        user: User,
        folder_id: int,
        new_name: str
    ) -> Tuple[bool, str, Optional[Folder]]:
        try:
            folder = Folder.objects.get(pk=folder_id, owner=user)
        except Folder.DoesNotExist:
            return False, "Папка не найдена", None
        
        try:
            folder.rename(new_name)
            return True, f"Папка переименована в '{new_name}'", folder
        except ValidationError as e:
            return False, str(e), folder
        except Exception as e:
            return False, f"Ошибка: {str(e)}", folder
    
    @staticmethod
    @transaction.atomic
    def delete_folder(
        user: User,
        folder_id: int
    ) -> Tuple[bool, str, str]:
        try:
            folder = Folder.objects.get(pk=folder_id, owner=user)
        except Folder.DoesNotExist:
            return False, "Папка не найдена", ""
        
        redirect_path = folder.parent.full_path if folder.parent else ""

        folder_name = folder.name
        
        folder.delete()
        
        return True, f"Папка '{folder_name}' удалена", redirect_path
    
    @staticmethod
    def upload_files(
        user: User,
        files: List[UploadedFile],
        relative_paths: List[str]
    ) -> Tuple[int, List[str]]:
        uploaded_count = 0
        errors = []

        def _upload_single_file(file_obj: UploadedFile, rel_path: str):
            try:
                folder_path = os.path.dirname(rel_path)
                file_name = os.path.basename(rel_path)
                StoredFile._validate_filename(file_name)

                folder = None
                if folder_path:
                    folder = Folder.find_or_create_by_path(user, folder_path)

                stored_file = StoredFile(
                    owner=user,
                    folder=folder,
                    original_name=file_name,
                    size=file_obj.size,
                    mime_type=file_obj.content_type or 'application/octet-stream'
                )
                stored_file.file.save(file_name, file_obj, save=True)
                return True, None
            except Exception as e:
                return False, f"{rel_path}: {str(e)}"
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_upload_single_file, file_obj, rel_path)
                for file_obj, rel_path in zip(files, relative_paths)
            ]

            for future in as_completed(futures):
                success, error = future.result()
                if success:
                    uploaded_count += 1
                else:
                    errors.append(error)

        return uploaded_count, errors
    
    @staticmethod
    def delete_file(user: User, file_id: int) -> Tuple[bool, str, str]:
        try:
            file_obj = StoredFile.objects.get(pk=file_id, owner=user)

            redirect_path = file_obj.folder.full_path if file_obj.folder else ""
            
            file_obj.delete()
            
            return True, "Файл удалён", redirect_path
        except StoredFile.DoesNotExist:
            return False, "Файл не найден", ""
        except Exception as e:
            return False, f"Ошибка: {str(e)}", ""
    
    @staticmethod
    @transaction.atomic
    def rename_file(
        user: User,
        file_id: int,
        new_name: str
    ) -> Tuple[bool, str, Optional[StoredFile]]:
        try:
            file_obj = StoredFile.objects.get(pk=file_id, owner=user)
            
            file_obj.rename(new_name)
            
            return True, f"Файл переименован в '{new_name}'", file_obj
            
        except StoredFile.DoesNotExist:
            return False, "Файл не найден", None
        except ValidationError as e:
            return False, str(e), None
        except Exception as e:
            return False, f"Ошибка: {str(e)}", None
    
    @staticmethod
    def validate_upload_data(files, relative_paths):
        if not files:
            return "Файлы не выбраны"
        if len(files) != len(relative_paths):
            return "Ошибка в данных"
        return None
    
    @staticmethod
    def search_files(user: User, query: str) -> List[StoredFile]:
        if not query:
            return []
        
        return StoredFile.objects.filter(
            owner=user,
            display_name__icontains=query
        ).order_by('display_name')