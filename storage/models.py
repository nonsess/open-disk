import os
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from typing import Optional, List, Dict, Any


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
    path = models.CharField(
        max_length=1000, 
        blank=True,
        verbose_name='Путь',
        help_text='Путь к папке, не включая её имя'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
        
    class Meta:
        ordering = ['path', 'name']
        unique_together = ['owner', 'path', 'name']
        verbose_name = 'Папка'
        verbose_name_plural = 'Папки'
        indexes = [
            models.Index(fields=['owner', 'path']),
            models.Index(fields=['owner', 'path', 'name']),
        ]
    
    def __str__(self) -> str:
        if self.path:
            return f"{self.path}/{self.name}"
        return self.name
    
    def clean(self) -> None:
        super().clean()
        
        self._validate_name(self.name)
        
        if self.path:
            self._validate_path(self.path)
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        
        self.path = self._normalize_path(self.path)
        
        super().save(*args, **kwargs)
    
    @property
    def full_path(self) -> str:
        if self.path:
            return f"{self.path}/{self.name}"
        return self.name
    
    @property
    def display_path(self) -> str:
        if self.path:
            return f"/{self.path}/{self.name}/"
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
    
    @staticmethod
    def _validate_path(path: str) -> None:
        if not path:
            return

        parts = [p for p in path.split('/') if p]
        
        for part in parts:
            if part:
                Folder._validate_name(part)
        
        if '//' in path:
            raise ValidationError('Путь не может содержать двойные слэши (//).')
        
        forbidden_chars = ['\\', ':', '*', '?', '"', '<', '>', '|', '\0']
        for char in forbidden_chars:
            if char in path:
                raise ValidationError(f"Путь не может содержать символ '{char}'")
        
        if len(path) > 1000:
            raise ValidationError('Путь слишком длинный (максимум 1000 символов).')
    
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
    
    def get_absolute_url(self) -> str:
        if self.path:
            return f"{reverse('file_list')}?path={self.full_path}"
        return reverse('file_list')
    
    def is_empty(self) -> bool:
        has_files = StoredFile.objects.filter(
            owner=self.owner,
            path=self.full_path
        ).exists()
        
        has_subfolders = Folder.objects.filter(
            owner=self.owner,
            path=self.full_path
        ).exists()
        
        return not (has_files or has_subfolders)
    
    def get_subfolders(self) -> 'models.QuerySet[Folder]':
        return Folder.objects.filter(
            owner=self.owner,
            path=self.full_path
        ).order_by('name')
    
    def get_files(self) -> 'models.QuerySet[StoredFile]':
        return StoredFile.objects.filter(
            owner=self.owner,
            path=self.full_path
        ).order_by('original_name')
    
    def get_parent(self) -> Optional['Folder']:
        if not self.path:
            return None
        
        parts = self.path.split('/')
        parent_path = '/'.join(parts[:-1]) if len(parts) > 1 else ''
        parent_name = parts[-1]
        
        try:
            return Folder.objects.get(
                owner=self.owner,
                path=parent_path,
                name=parent_name
            )
        except Folder.DoesNotExist:
            return None
    
    def get_breadcrumbs(self) -> List[Dict[str, str]]:
        breadcrumbs = [{'name': 'Главная', 'path': ''}]
        
        if self.path:
            parts = self.path.split('/')
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
        
        breadcrumbs.append({
            'name': self.name,
            'path': self.full_path
        })
        
        return breadcrumbs


class StoredFile(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Владелец',
        help_text='Пользователь, которому принадлежит файл'
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
    path = models.CharField(
        max_length=1000,
        blank=True,
        verbose_name='Путь',
        help_text='Путь к файлу, не включая его имя'
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
            models.Index(fields=['owner', 'path']),
            models.Index(fields=['owner', 'uploaded_at']),
            models.Index(fields=['public_link']),
            models.Index(fields=['is_public']),
        ]
    
    def __str__(self) -> str:
        return f"{self.original_name} ({self.owner.username})"
    
    def clean(self) -> None:
        super().clean()
        
        self._validate_filename(self.original_name)
        
        if self.path:
            Folder._validate_path(self.path)
        
        if self.size < 0:
            raise ValidationError('Размер файла не может быть отрицательным.')
        
        if self.size > 10 * 1024 * 1024 * 1024:  # 10 GB
            raise ValidationError('Размер файла не может превышать 10 ГБ.')
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        
        self.path = Folder._normalize_path(self.path)
        
        if not self.file.name or not self.file.name.startswith(f"user-{self.owner_id}-files/"):
            file_name = os.path.basename(self.file.name) if self.file.name else self.original_name
            self.file.name = f"user-{self.owner_id}-files/{self.full_path}"
        
        super().save(*args, **kwargs)
    
    @property
    def full_path(self) -> str:
        if self.path:
            return f"{self.path}/{self.original_name}"
        return self.original_name
    
    @property
    def display_path(self) -> str:
        if self.path:
            return f"/{self.path}/{self.original_name}"
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
        
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp']:
            return 'fa-file-image'
        elif ext in ['.pdf']:
            return 'fa-file-pdf'
        elif ext in ['.doc', '.docx']:
            return 'fa-file-word'
        elif ext in ['.xls', '.xlsx']:
            return 'fa-file-excel'
        elif ext in ['.ppt', '.pptx']:
            return 'fa-file-powerpoint'
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return 'fa-file-archive'
        elif ext in ['.mp3', '.wav', '.ogg', '.flac']:
            return 'fa-file-audio'
        elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            return 'fa-file-video'
        elif ext in ['.txt', '.md', '.rtf']:
            return 'fa-file-alt'
        elif ext in ['.py', '.js', '.html', '.css', '.json', '.xml']:
            return 'fa-file-code'
        else:
            return 'fa-file'
    
    def get_folder(self) -> Optional[Folder]:
        if not self.path:
            return None
        
        parts = self.path.split('/')
        folder_path = '/'.join(parts[:-1]) if len(parts) > 1 else ''
        folder_name = parts[-1]
        
        try:
            return Folder.objects.get(
                owner=self.owner,
                path=folder_path,
                name=folder_name
            )
        except Folder.DoesNotExist:
            return None
    
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