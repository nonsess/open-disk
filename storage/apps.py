import sys
import boto3
from botocore.exceptions import ClientError

from django.apps import AppConfig
from django.conf import settings


class StorageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'storage'

    def ready(self):
        if 'manage.py' in sys.argv[0] and len(sys.argv) > 1:
            command = sys.argv[1]
            if command in ('makemigrations', 'migrate', 'collectstatic', 'shell', 'dbshell'):
                return

        self.create_minio_bucket()
    
    def create_minio_bucket(self):
        s3 = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        try:
            s3.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                s3.create_bucket(Bucket=bucket_name)
                print(f"Bucket '{bucket_name}' создан в MinIO")
            else:
                print(f"Ошибка при проверке бакета: {e}")