from django.db import models
from django.contrib.auth.models import User
import uuid


class Folder(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders')
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ['owner', 'path', 'name']
        
    def __str__(self):
        return f"{self.path}/{self.name}" if self.path else self.name

    @property
    def full_path(self):
        """Полный путь папки"""
        return f"{self.path}/{self.name}" if self.path else self.name


class StoredFile(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    file = models.FileField()
    original_name = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=100, blank=True)
    path = models.CharField(max_length=1000, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=False)
    public_link = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Stored File'
        verbose_name_plural = 'Stored Files'

    def __str__(self):
        return f"{self.original_name} ({self.owner.username})"

    @property
    def full_path(self):
        """Полный путь файла"""
        return f"{self.path}/{self.original_name}" if self.path else self.original_name