import uuid
from django.db import models
from django.contrib.auth.models import User

class StoredFile(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    original_name = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=False)
    public_link = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Stored File'
        verbose_name_plural = 'Stored Files'

    def __str__(self):
        return f"{self.original_name} ({self.owner.username})"