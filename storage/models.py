import os
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from typing import Optional, List, Dict


class Folder(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='folders',
        verbose_name='Владелец'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='Имя папки',
        help_text='Название папки'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        null=True,
        blank=True,
        verbose_name='Родительская папка'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    class Meta:
        ordering = ['name']
        unique_together = ['owner', 'parent', 'name']
        indexes = [
            models.Index(fields=['owner', 'parent']),
            models.Index(fields=['owner', 'parent', 'name']),
        ]
        verbose_name = 'Папка'
        verbose_name_plural = 'Папки'
    
    def __str__(self):
        return self.name
    
    @property
    def full_path(self) -> str:
        parts = []
        current = self
        
        while current:
            parts.insert(0, current.name)
            current = current.parent
        
        if len(parts) == 1:
            return parts[0]

        return '/'.join(parts)
        
    def get_breadcrumbs(self) -> List[Dict[str, str]]:
        crumbs = []
        current = self
        
        while current:
            crumbs.insert(0, {
                'name': current.name,
                'path': current.full_path
            })
            current = current.parent
        
        crumbs.insert(0, {
            'name': 'Главная',
            'path': ''
        })
        
        return crumbs

    def delete(self, *args, **kwargs):
        from django.db import transaction
        
        with transaction.atomic():
            all_files = []
            
            def collect_files(folder):
                for file_obj in folder.files.all():
                    all_files.append(file_obj)
                
                for child in folder.children.all():
                    collect_files(child)
            
            collect_files(self)
            
            for file_obj in all_files:
                try:
                    if file_obj.file:
                        file_obj.file.delete(save=False)
                except Exception as e:
                    print(f"Ошибка удаления файла {file_obj.original_name}: {e}")
            
            super().delete(*args, **kwargs)
    
    def clean(self):
        super().clean()
        
        if Folder.objects.filter(
            owner=self.owner,
            parent=self.parent,
            name=self.name
        ).exclude(pk=self.pk).exists():
            raise ValidationError(f"Папка '{self.name}' уже существует")
        
        if self.pk and self.parent:
            current = self.parent
            while current:
                if current.pk == self.pk:
                    raise ValidationError("Обнаружена циклическая ссылка")
                current = current.parent
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @transaction.atomic
    def rename(self, new_name: str) -> Dict[str, str]:
        old_name = self.name
        
        if Folder.objects.filter(
            owner=self.owner,
            parent=self.parent,
            name=new_name
        ).exclude(pk=self.pk).exists():
            raise ValidationError(f"Папка '{new_name}' уже существует")
        
        self.name = new_name
        self.save()
        
        return {
            'old_name': old_name,
            'new_name': new_name
        }
    
    @classmethod
    def find_by_path(cls, user: User, path: str) -> Optional['Folder']:
        if not path or path == '':
            return None
        
        parts = [p for p in path.strip('/').split('/') if p]
        if not parts:
            return None
        
        current = None
        
        for part in parts:
            try:
                current = cls.objects.get(
                    owner=user,
                    parent=current,
                    name=part
                )
            except cls.DoesNotExist:
                return None
        
        return current
    
    @classmethod
    def find_or_create_by_path(cls, user: User, path: str) -> 'Folder':
        if not path or path == '':
            raise ValueError("Путь не может быть пустым")
        
        parts = [p for p in path.strip('/').split('/') if p]
        if not parts:
            raise ValueError("Путь не может быть пустым")
        
        current = None
        
        for part in parts:
            folder, created = cls.objects.get_or_create(
                owner=user,
                parent=current,
                name=part,
                defaults={'owner': user}
            )
            current = folder
        
        return current
    

def generate_file_path(instance, filename: str) -> str:
    instance.original_name = filename
    
    ext = os.path.splitext(filename)[1].lower()
    unique_filename = f"{uuid.uuid4()}{ext}"
    
    return f"user-{instance.owner.id}-files/{unique_filename}"


class StoredFile(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Владелец'
    )
    folder = models.ForeignKey(
        Folder,
        on_delete=models.CASCADE,
        related_name='files',
        null=True,
        blank=True,
        verbose_name='Папка'
    )
    file = models.FileField(
        upload_to=generate_file_path,
        verbose_name='Файл в хранилище',
        max_length=500
    )
    original_name = models.CharField(
        max_length=500,
        verbose_name='Оригинальное имя файла'
    )
    display_name = models.CharField(
        max_length=500,
        verbose_name='Имя для отображения',
        default=''
    )
    size = models.BigIntegerField(
        default=0,
        verbose_name='Размер (байты)'
    )
    mime_type = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='MIME-тип'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата загрузки'
    )
    
    class Meta:
        ordering = ['display_name']
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'
        indexes = [
            models.Index(fields=['owner', 'folder']),
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['folder', 'display_name']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'folder', 'display_name'],
                name='unique_file_name_per_folder'
            )
        ]

    def __str__(self):
        return self.display_name
    
    def save(self, *args, **kwargs):
        if not self.display_name and self.original_name:
            self.display_name = self.original_name
        
        if self.file and hasattr(self.file, 'size'):
            self.size = self.file.size
            
            if not self.mime_type and self.original_name:
                ext = os.path.splitext(self.original_name)[1].lower()
                mime_types = {
                    '.txt': 'text/plain',
                    '.pdf': 'application/pdf',
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.zip': 'application/zip',
                    '.rar': 'application/x-rar-compressed',
                    '.mp4': 'video/mp4',
                    '.mp3': 'audio/mpeg',
                    '.doc': 'application/msword',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.xls': 'application/vnd.ms-excel',
                    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                }
                self.mime_type = mime_types.get(ext, 'application/octet-stream')
        
        super().save(*args, **kwargs)
    
    def clean(self):
        super().clean()
        
        if StoredFile.objects.filter(
            owner=self.owner,
            folder=self.folder,
            display_name=self.display_name
        ).exclude(pk=self.pk).exists():
            raise ValidationError(f"Файл с именем '{self.display_name}' уже существует")
    
    def delete(self, *args, **kwargs):
        if self.file:
            try:
                self.file.delete(save=False)
            except Exception as e:
                print(f"Ошибка удаления файла из MinIO: {e}")
        
        super().delete(*args, **kwargs)

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
    
    @property
    def url(self) -> str:
        return self.file.url
    
    @property
    def human_size(self) -> str:
        if self.size == 0:
            return "0 Б"
        
        size = float(self.size)
        for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        
        return f"{size:.1f} ТБ"
    
    @transaction.atomic
    def rename(self, new_name: str) -> Dict[str, str]:
        old_name = self.display_name
        
        if not new_name or not new_name.strip():
            raise ValidationError("Имя файла не может быть пустым")
        
        self._validate_filename(new_name)
        
        if StoredFile.objects.filter(
            owner=self.owner,
            folder=self.folder,
            display_name=new_name
        ).exclude(pk=self.pk).exists():
            raise ValidationError(f"Файл с именем '{new_name}' уже существует")
        
        self.display_name = new_name
        self.save()
        
        return {
            'old_name': old_name,
            'new_name': new_name
        }