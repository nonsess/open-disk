import os
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from typing import Optional, List, Dict, Any
from django.db import transaction


class Folder(models.Model):
    owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='folders',
        verbose_name='Владелец',
        help_text='Пользователь, которому принадлежит папка'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='Имя папки',
        help_text='Название папки (максимум 255 символов)'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        null=True,
        blank=True,
        verbose_name='Родительская папка',
        help_text='Родительская папка. Если None - корневая папка'
    )
    materialized_path = models.CharField(
        max_length=1000,
        blank=True,
        db_index=True,
        verbose_name='Материализованный путь',
        help_text='Путь к родительской папке для быстрого поиска'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
        
    class Meta:
        ordering = ['name']
        unique_together = ['owner', 'parent', 'name']
        verbose_name = 'Папка'
        verbose_name_plural = 'Папки'
        indexes = [
            models.Index(fields=['owner', 'parent']),
            models.Index(fields=['owner', 'materialized_path']),
            models.Index(fields=['owner', 'parent', 'name']),
        ]
    
    def __str__(self) -> str:
        return self.full_path
    
    def clean(self) -> None:
        super().clean()
        
        self._validate_name(self.name)
        
        if self.pk and self.parent and self.parent.pk == self.pk:
            raise ValidationError('Папка не может быть своим же родителем')
        
        if self.parent:
            current = self.parent
            while current:
                if current.pk == self.pk:
                    raise ValidationError('Обнаружена циклическая ссылка в родительских папках')
                current = current.parent
    
    def save(self, *args, **kwargs) -> None:
        self._update_materialized_path()
        
        if self.pk:
            old_parent = Folder.objects.get(pk=self.pk).parent
            if old_parent != self.parent:
                self._check_unique_in_parent()
        
        self.full_clean()
        super().save(*args, **kwargs)
        
        if self.pk and hasattr(self, '_old_materialized_path'):
            if self._old_materialized_path != self.materialized_path:
                self._update_descendants_paths()
    
    def _update_materialized_path(self) -> None:
        if not self.pk:
            self._old_materialized_path = ""
        
        if self.parent:
            if self.parent.materialized_path:
                new_path = f"{self.parent.materialized_path}/{self.parent.name}"
            else:
                new_path = self.parent.name
            
            if self.pk:
                old_obj = Folder.objects.get(pk=self.pk)
                self._old_materialized_path = old_obj.materialized_path
            else:
                self._old_materialized_path = ""
            
            self.materialized_path = new_path
        else:
            if self.pk:
                old_obj = Folder.objects.get(pk=self.pk)
                self._old_materialized_path = old_obj.materialized_path
            else:
                self._old_materialized_path = ""
            
            self.materialized_path = ""
    
    def _check_unique_in_parent(self) -> None:
        if Folder.objects.filter(
            owner=self.owner,
            parent=self.parent,
            name=self.name
        ).exclude(pk=self.pk).exists():
            raise ValidationError(f"Папка с именем '{self.name}' уже существует в этой папке")
    
    def _update_descendants_paths(self) -> None:
        old_base_path = self._old_materialized_path
        new_base_path = self.materialized_path
        
        if old_base_path:
            old_full_path = f"{old_base_path}/{self.name}" if old_base_path else self.name
        else:
            old_full_path = self.name
        
        if new_base_path:
            new_full_path = f"{new_base_path}/{self.name}" if new_base_path else self.name
        else:
            new_full_path = self.name
        
        descendants = self.get_descendants(include_self=False)
        
        for descendant in descendants:
            if old_full_path and descendant.materialized_path.startswith(old_full_path):
                descendant.materialized_path = descendant.materialized_path.replace(
                    old_full_path,
                    new_full_path,
                    1
                )
                super(Folder, descendant).save(update_fields=['materialized_path'])
    
    @property
    def full_path(self) -> str:
        if self.materialized_path:
            return f"{self.materialized_path}/{self.name}"
        return self.name
    
    @property
    def path(self) -> str:
        return self.materialized_path
    
    @property
    def display_path(self) -> str:
        if self.materialized_path:
            return f"/{self.materialized_path}/{self.name}/"
        return f"/{self.name}/"
    
    @staticmethod
    def _validate_name(name: str) -> None:
        if not name:
            raise ValidationError('Имя папки не может быть пустым.')
                
        if not name.strip():
            raise ValidationError('Имя папки не может состоять только из пробелов.')
        
        forbidden_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']
        
        for char in forbidden_chars:
            if char in name:
                raise ValidationError(f"Имя папки не может содержать символ '{char}'")
        
        forbidden_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
            '.', '..'
        ]
        
        if name.upper() in [n.upper() for n in forbidden_names]:
            raise ValidationError(f"Имя '{name}' зарезервировано системой.")
        
        if len(name) > 255:
            raise ValidationError('Имя папки не может превышать 255 символов.')
        
        if name.startswith(' ') or name.endswith(' '):
            raise ValidationError('Имя папки не может начинаться или заканчиваться пробелом.')
        
        if name.startswith('.') or name.endswith('.'):
            raise ValidationError('Имя папки не может начинаться или заканчиваться точкой.')
    
    def get_absolute_url(self) -> str:
        return f"{reverse('file_list')}?path={self.full_path}"
    
    def is_empty(self) -> bool:
        has_files = self.files.exists()
        has_children = self.children.exists()
        return not (has_files or has_children)
    
    def get_subfolders(self) -> 'models.QuerySet[Folder]':
        return self.children.all().order_by('name')
    
    def get_files(self) -> 'models.QuerySet[StoredFile]':
        return self.files.all().order_by('original_name')
    
    def get_parent_folder(self) -> Optional['Folder']:
        return self.parent
    
    def get_breadcrumbs(self) -> List[Dict[str, str]]:
        breadcrumbs = [{'name': 'Главная', 'path': ''}]
        
        ancestors = self.get_ancestors()
        for ancestor in ancestors:
            breadcrumbs.append({
                'name': ancestor.name,
                'path': ancestor.full_path
            })
        
        breadcrumbs.append({
            'name': self.name,
            'path': self.full_path
        })
        
        return breadcrumbs
    
    def get_ancestors(self) -> List['Folder']:
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors
    
    def get_descendants(self, include_self=False) -> 'models.QuerySet[Folder]':
        base_path = self.full_path
        
        if include_self:
            return Folder.objects.filter(
                owner=self.owner
            ).filter(
                models.Q(materialized_path__startswith=base_path) |
                models.Q(materialized_path=base_path) |
                models.Q(pk=self.pk)
            )
        else:
            return Folder.objects.filter(
                owner=self.owner,
                materialized_path__startswith=base_path
            ).exclude(pk=self.pk)
    
    def get_all_files(self) -> 'models.QuerySet[StoredFile]':
        descendant_folders = self.get_descendants(include_self=True)
        return StoredFile.objects.filter(folder__in=descendant_folders)
    
    @classmethod
    def find_by_path(cls, user: User, path: str) -> Optional['Folder']:
        if not path or path == '':
            return None
        
        normalized_path = cls._normalize_path(path)
        parts = [p for p in normalized_path.split('/') if p]
        
        if not parts:
            return None
        
        for i in range(len(parts), 0, -1):
            materialized_path = '/'.join(parts[:i-1]) if i > 1 else ""
            name = parts[i-1]
            
            try:
                folder = cls.objects.get(
                    owner=user,
                    materialized_path=materialized_path,
                    name=name
                )
                return folder
            except cls.DoesNotExist:
                continue
        
        return None
    
    @classmethod
    def find_or_create_by_path(cls, user: User, path: str) -> 'Folder':
        existing = cls.find_by_path(user, path)
        if existing:
            return existing
        
        normalized_path = cls._normalize_path(path)
        parts = [p for p in normalized_path.split('/') if p]
        
        if not parts:
            raise ValueError("Неверный путь")
        
        current_parent = None
        
        for i, part in enumerate(parts):
            materialized_path = '/'.join(parts[:i]) if i > 0 else ""
            
            try:
                folder = cls.objects.get(
                    owner=user,
                    materialized_path=materialized_path,
                    name=part
                )
                current_parent = folder
            except cls.DoesNotExist:
                folder = cls.objects.create(
                    owner=user,
                    parent=current_parent,
                    name=part,
                    materialized_path=materialized_path
                )
                current_parent = folder
        
        return current_parent
    
    @staticmethod
    def _normalize_path(path: str) -> str:
        if not path:
            return ""
        
        path = path.strip()
        path = path.replace('\\', '/')
        path = path.strip('/')
        
        while '//' in path:
            path = path.replace('//', '/')
        
        return path
    
    @transaction.atomic
    def rename(self, new_name: str) -> Dict[str, str]:
        old_name = self.name
        old_full_path = self.full_path
        
        self._validate_name(new_name)
        
        if Folder.objects.filter(
            owner=self.owner,
            parent=self.parent,
            name=new_name
        ).exclude(pk=self.pk).exists():
            raise ValidationError(f"Папка с именем '{new_name}' уже существует")
        
        self.name = new_name
        self.save()
        
        return {
            'old_name': old_name,
            'new_name': new_name,
            'old_path': old_full_path,
            'new_path': self.full_path
        }
    
    @transaction.atomic
    def move(self, new_parent: Optional['Folder']) -> Dict[str, Any]:
        if new_parent and new_parent.pk == self.pk:
            raise ValidationError('Папка не может быть перемещена в саму себя')
        
        if new_parent:
            descendant_ids = self.get_descendants(include_self=True).values_list('id', flat=True)
            if new_parent.pk in descendant_ids:
                raise ValidationError('Папка не может быть перемещена в свою подпапку')
        
        if new_parent and Folder.objects.filter(
            owner=self.owner,
            parent=new_parent,
            name=self.name
        ).exclude(pk=self.pk).exists():
            raise ValidationError(f"Папка с именем '{self.name}' уже существует в целевой папке")
        
        old_parent = self.parent
        old_full_path = self.full_path
        
        self.parent = new_parent
        self.save()
        
        return {
            'old_parent': old_parent,
            'new_parent': new_parent,
            'old_path': old_full_path,
            'new_path': self.full_path
        }
    
    @classmethod
    @transaction.atomic
    def delete_with_content(cls, folder_id: int, user: User) -> Dict[str, Any]:
        try:
            folder = cls.objects.get(pk=folder_id, owner=user)
        except cls.DoesNotExist:
            raise ValidationError('Папка не найдена или у вас нет прав на ее удаление')
        
        file_count = folder.get_all_files().count()
        folder_count = folder.get_descendants(include_self=True).count()
        
        folder.delete()
        
        return {
            'folder_name': folder.name,
            'folder_path': folder.full_path,
            'files_deleted': file_count,
            'folders_deleted': folder_count
        }


class StoredFile(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Владелец',
        help_text='Пользователь, которому принадлежит файл'
    )
    folder = models.ForeignKey(
        Folder,
        on_delete=models.CASCADE,
        related_name='files',
        null=True,
        blank=True,
        verbose_name='Папка',
        help_text='Папка, в которой находится файл'
    )
    file = models.FileField(
        verbose_name='Файл',
        help_text='Файл в хранилище',
    )
    original_name = models.CharField(
        max_length=255,
        verbose_name='Оригинальное имя',
        help_text='Имя файла при загрузке'
    )
    size = models.PositiveBigIntegerField(
        verbose_name='Размер',
        help_text='Размер файла в байтах'
    )
    mime_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='MIME-тип',
        help_text='Тип содержимого файла'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата загрузки'
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name='Публичный доступ',
        help_text='Доступен ли файл по публичной ссылке'
    )
    public_link = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name='Публичная ссылка',
        help_text='Уникальный идентификатор для публичного доступа'
    )
        
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'
        indexes = [
            models.Index(fields=['owner', 'folder']),
            models.Index(fields=['owner', 'uploaded_at']),
            models.Index(fields=['public_link']),
            models.Index(fields=['is_public']),
            models.Index(fields=['folder', 'original_name']),
        ]
        unique_together = ['owner', 'folder', 'original_name']
    
    def __str__(self) -> str:
        return f"{self.original_name} ({self.owner.username})"
    
    def clean(self) -> None:
        super().clean()
        
        self._validate_filename(self.original_name)
        
        if self.size < 0:
            raise ValidationError('Размер файла не может быть отрицательным.')
        
        if self.size > 10 * 1024 * 1024 * 1024:  # 10 GB
            raise ValidationError('Размер файла не может превышать 10 ГБ.')
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        
        if not self.file.name or not self.file.name.startswith(f"user-{self.owner_id}-files/"):
            self.file.name = f"user-{self.owner_id}-files/{self.full_path}"
        
        super().save(*args, **kwargs)
    
    @property
    def full_path(self) -> str:
        if self.folder:
            return f"{self.folder.full_path}/{self.original_name}"
        return self.original_name
    
    @property
    def path(self) -> str:
        if self.folder:
            return self.folder.full_path
        return ""
    
    @property
    def display_path(self) -> str:
        if self.folder:
            return f"/{self.folder.full_path}/{self.original_name}"
        return f"/{self.original_name}"
    
    @property
    def extension(self) -> str:
        name, ext = os.path.splitext(self.original_name)
        return ext.lower() if ext else ''
    
    @property
    def filename_without_extension(self) -> str:
        name, _ = os.path.splitext(self.original_name)
        return name
    
    @staticmethod
    def _validate_filename(filename: str) -> None:
        if not filename:
            raise ValidationError('Имя файла не может быть пустым.')
        
        if not filename.strip():
            raise ValidationError('Имя файла не может состоять только из пробелов.')
        
        forbidden_chars = ['\\', ':', '*', '?', '"', '<', '>', '|', '\0']
        
        for char in forbidden_chars:
            if char in filename:
                raise ValidationError(f"Имя файла не может содержать символ '{char}'")
        
        if '/' in filename or '\\' in filename:
            raise ValidationError('Имя файла не может содержать символы / или \\.')
        
        if len(filename) > 255:
            raise ValidationError('Имя файла не может превышать 255 символов.')
        
        if filename.endswith('.') or filename.endswith(' '):
            raise ValidationError('Имя файла не может заканчиваться точкой или пробелом.')
        
        forbidden_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
        ]
        
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in forbidden_names:
            raise ValidationError(f"Имя файла '{filename}' зарезервировано системой.")
    
    def get_absolute_url(self) -> str:
        return reverse('download_file', kwargs={'pk': self.pk})
    
    def get_public_url(self) -> Optional[str]:
        if self.is_public:
            return reverse('public_download', kwargs={'uuid': self.public_link})
        return None
    
    def get_download_url(self, request: Optional['HttpRequest'] = None) -> str:
        if self.is_public:
            return self.get_public_url() or self.file.url
        return self.file.url
    
    def get_size_display(self) -> str:
        if self.size < 1024:
            return f"{self.size} Б"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} КБ"
        elif self.size < 1024 * 1024 * 1024:
            return f"{self.size / (1024 * 1024):.1f} МБ"
        else:
            return f"{self.size / (1024 * 1024 * 1024):.2f} ГБ"
    
    def get_icon_class(self) -> str:
        ext = self.extension
        
        icon_map = {
            '.jpg': 'fa-file-image',
            '.jpeg': 'fa-file-image',
            '.png': 'fa-file-image',
            '.gif': 'fa-file-image',
            '.bmp': 'fa-file-image',
            '.svg': 'fa-file-image',
            '.webp': 'fa-file-image',
            '.pdf': 'fa-file-pdf',
            '.doc': 'fa-file-word',
            '.docx': 'fa-file-word',
            '.xls': 'fa-file-excel',
            '.xlsx': 'fa-file-excel',
            '.ppt': 'fa-file-powerpoint',
            '.pptx': 'fa-file-powerpoint',
            '.zip': 'fa-file-archive',
            '.rar': 'fa-file-archive',
            '.7z': 'fa-file-archive',
            '.tar': 'fa-file-archive',
            '.gz': 'fa-file-archive',
            '.mp3': 'fa-file-audio',
            '.wav': 'fa-file-audio',
            '.ogg': 'fa-file-audio',
            '.flac': 'fa-file-audio',
            '.mp4': 'fa-file-video',
            '.avi': 'fa-file-video',
            '.mov': 'fa-file-video',
            '.mkv': 'fa-file-video',
            '.webm': 'fa-file-video',
            '.txt': 'fa-file-alt',
            '.md': 'fa-file-alt',
            '.rtf': 'fa-file-alt',
            '.py': 'fa-file-code',
            '.js': 'fa-file-code',
            '.html': 'fa-file-code',
            '.css': 'fa-file-code',
            '.json': 'fa-file-code',
            '.xml': 'fa-file-code',
        }
        
        return icon_map.get(ext, 'fa-file')
    
    def is_image(self) -> bool:
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.tiff']
        return self.extension in image_extensions
    
    def is_document(self) -> bool:
        document_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.odt']
        return self.extension in document_extensions
    
    def can_preview(self) -> bool:
        previewable_types = ['image/', 'text/', 'application/pdf']
        return any(self.mime_type.startswith(t) for t in previewable_types)
    
    def get_preview_url(self) -> Optional[str]:
        if self.can_preview():
            return reverse('preview_file', kwargs={'pk': self.pk})
        return None
    
    @classmethod
    def create_in_folder(cls, user: User, folder: Optional[Folder], original_name: str, 
                        file_obj, size: int, mime_type: str = '') -> 'StoredFile':
        base_name, extension = os.path.splitext(original_name)
        counter = 0
        new_name = original_name
        
        while cls.objects.filter(
            owner=user,
            folder=folder,
            original_name=new_name
        ).exists():
            counter += 1
            new_name = f"{base_name} ({counter}){extension}"
        
        stored_file = cls(
            owner=user,
            folder=folder,
            original_name=new_name,
            file=file_obj,
            size=size,
            mime_type=mime_type or 'application/octet-stream'
        )
        
        stored_file.save()
        return stored_file
    
    @transaction.atomic
    def rename(self, new_name: str) -> Dict[str, str]:
        old_name = self.original_name
        
        self._validate_filename(new_name)
        
        if StoredFile.objects.filter(
            owner=self.owner,
            folder=self.folder,
            original_name=new_name
        ).exclude(pk=self.pk).exists():
            raise ValidationError(f"Файл с именем '{new_name}' уже существует в этой папке")
        
        self.original_name = new_name
        self.save()
        
        return {
            'old_name': old_name,
            'new_name': new_name,
            'old_path': f"{self.path}/{old_name}" if self.path else old_name,
            'new_path': self.full_path
        }
    
    @transaction.atomic
    def move(self, new_folder: Optional[Folder]) -> Dict[str, Any]:
        if new_folder and StoredFile.objects.filter(
            owner=self.owner,
            folder=new_folder,
            original_name=self.original_name
        ).exclude(pk=self.pk).exists():
            raise ValidationError(f"Файл с именем '{self.original_name}' уже существует в целевой папке")
        
        old_folder = self.folder
        old_full_path = self.full_path
        
        self.folder = new_folder
        self.save()
        
        return {
            'old_folder': old_folder,
            'new_folder': new_folder,
            'old_path': old_full_path,
            'new_path': self.full_path
        }