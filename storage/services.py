from typing import List, Dict, Optional, Tuple, Set
import os
from django.core.exceptions import ValidationError
from django.db import IntegrityError
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
            
            normalized_path = MinIOClient.normalize_path(path)
            
            full_path = f"{normalized_path}/{name}" if normalized_path else name
            full_path = MinIOClient.normalize_path(full_path)
            
            minio_client = MinIOClient()
            success, message = minio_client.create_folder(user, full_path)
            
            if not success:
                return False, message, None
            
            folder = Folder.objects.create(
                owner=user,
                name=name,
                path=normalized_path
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
        errors = []
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
                stored_file.save()
                
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
        
        StorageService._create_folders_from_paths(user, folder_paths)
        
        return uploaded_count, errors
    
    @staticmethod
    def _create_folders_from_paths(user: User, folder_paths: Set[str]) -> None:
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
    def validate_upload_data(
        files: List[UploadedFile],
        relative_paths: List[str]
    ) -> Optional[str]:
        if not files:
            return "Файл(ы) не выбраны."
        
        if len(files) != len(relative_paths):
            return "Ошибка при загрузке структуры папок."
        
        return None