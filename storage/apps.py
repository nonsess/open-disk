import sys
import boto3
from mypy_boto3_s3 import S3Client
from botocore.exceptions import ClientError

from django.apps import AppConfig
from django.conf import settings


class StorageConfig(AppConfig):
    name = 'storage'

    def ready(self):
        if 'manage.py' in sys.argv[0] and len(sys.argv) > 1:
            command = sys.argv[1]
            if command in ('makemigrations', 'migrate', 'collectstatic', 'shell', 'dbshell'):
                return
        else: self.create_minio_bucket()
    
    def create_minio_bucket(self):
        s3: S3Client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        try:
            s3.head_bucket(Bucket=bucket_name)
        except ClientError:
            s3.create_bucket(Bucket=bucket_name)
