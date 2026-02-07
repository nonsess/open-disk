import boto3
from mypy_boto3_s3 import S3Client
from django.conf import settings
from botocore.exceptions import ClientError
from django.contrib.auth.models import User


class MinIOClient:
    def __init__(self):
        self.client: S3Client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            verify=False
        )
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME
    
    def create_minio_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            self.client.create_bucket(Bucket=self.bucket)

    @staticmethod
    def normalize_path(path: str) -> str:
        if not path:
            return ""
        
        path = path.strip()
        
        path = path.replace('\\', '/')

        path = path.strip('/')
        
        while '//' in path:
            path = path.replace('//', '/')
        
        return path
    
    @staticmethod
    def validate_folder_path(path: str) -> tuple[bool, str]:
        if '//' in path:
            return False, "Путь не может содержать двойные слэши (//)"
                
        if len(path) > 1000:
            return False, "Путь слишком длинный (максимум 1000 символов)"
        
        parts = [p for p in path.split('/') if p]
        
        for part in parts:
            if len(part) > 255:
                return False, f"Имя '{part}' слишком длинное (максимум 255 символов)"
            
            if part in ['.', '..']:
                return False, f"Имя '{part}' недопустимо"
        
        return True, ""
    
    def create_folder(self, user: User, folder_path: str) -> tuple[bool, str]:
        try:
            folder_path = self.normalize_path(folder_path)
            
            is_valid, error_msg = self.validate_folder_path(folder_path)
            if not is_valid:
                return False, error_msg
            
            if folder_path:
                minio_key = f"user-{user.id}-files/{folder_path}/"
            else:
                minio_key = f"user-{user.id}-files/"
            
            if self._folder_exists_in_minio(minio_key):
                return False, "Папка уже существует в хранилище"
            
            self.client.put_object(
                Bucket=self.bucket,
                Key=minio_key,
                Body=b'',
                ContentLength=0,
                ContentType='application/x-directory',
                Metadata={
                    'x-amz-meta-folder': 'true',
                    'x-amz-meta-owner-id': str(user.id),
                }
            )            
            return True, f"Папка создана: {minio_key}"
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                return False, "Бакет не существует"
            elif error_code == 'AccessDenied':
                return False, "Доступ запрещен"
            else:
                return False, f"Ошибка MinIO: {str(e)}"
        except Exception as e:
            return False, f"Неожиданная ошибка: {str(e)}"
    
    def _folder_exists_in_minio(self, folder_key: str) -> bool:
        try:
            self.client.head_object(
                Bucket=self.bucket,
                Key=folder_key
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def delete_folder(self, user: User, folder_path: str) -> tuple[bool, str]:
        try:
            folder_path = self.normalize_path(folder_path)
            
            prefix = f"user-{user.id}-files/{folder_path}/"
            if folder_path == "":
                prefix = f"user-{user.id}-files/"
            
            objects_to_delete = []
            
            paginator = self.client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects_to_delete.append({'Key': obj['Key']})
            
            if not objects_to_delete:
                return True, "Папка пуста или не существует"
            
            delete_response = self.client.delete_objects(
                Bucket=self.bucket,
                Delete={'Objects': objects_to_delete}
            )
            
            deleted_count = len(delete_response.get('Deleted', []))
            return True, f"Удалено {deleted_count} объектов"
            
        except Exception as e:
            return False, f"Ошибка при удалении папки: {str(e)}"