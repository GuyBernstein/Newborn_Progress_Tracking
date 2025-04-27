import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import BinaryIO, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.AWS_S3_BUCKET

    def _generate_file_key(self, baby_id: int, filename: str) -> str:
        """
        Generate a unique S3 key for a file.

        Args:
            baby_id: ID of the baby
            filename: Original filename

        Returns:
            S3 key string
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = os.path.splitext(filename)[1].lower()
        unique_id = str(uuid.uuid4())[:8]

        return f"baby_{baby_id}/{timestamp}_{unique_id}{extension}"

    async def upload_file(
            self,
            file: UploadFile,
            baby_id: int,
            content_type: Optional[str] = None
    ) -> Dict:
        """
        Upload a file to S3.

        Args:
            file: UploadFile object
            baby_id: ID of the baby
            content_type: Optional content type

        Returns:
            Dictionary with file metadata
        """
        filename = file.filename or "unnamed_file"
        s3_key = self._generate_file_key(baby_id, filename)

        # Set content type if provided
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        else:
            # Try to infer content type from filename
            extension = os.path.splitext(filename)[1].lower()
            if extension in ['.jpg', '.jpeg']:
                extra_args["ContentType"] = 'image/jpeg'
            elif extension == '.png':
                extra_args["ContentType"] = 'image/png'
            elif extension == '.pdf':
                extra_args["ContentType"] = 'application/pdf'

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        try:
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                **extra_args
            )

            # Generate a pre-signed URL (valid for 1 hour)
            url = self.generate_presigned_url(s3_key, expiration=3600)

            return {
                "s3_key": s3_key,
                "s3_url": url,
                "filename": filename,
                "file_size": file_size,
                "content_type": content_type or extra_args.get("ContentType", "application/octet-stream")
            }

        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """
        Generate a pre-signed URL for a file.

        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Pre-signed URL string
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating pre-signed URL: {e}")
            return ""

    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            s3_key: S3 object key

        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            return False

    def list_files(self, prefix: str) -> List[Dict]:
        """
        List files in S3 with a given prefix.

        Args:
            prefix: S3 key prefix (e.g., 'baby_1/')

        Returns:
            List of file metadata dictionaries
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            if 'Contents' not in response:
                return []

            files = []
            for obj in response['Contents']:
                files.append({
                    "s3_key": obj['Key'],
                    "size": obj['Size'],
                    "last_modified": obj['LastModified'].isoformat(),
                    "s3_url": self.generate_presigned_url(obj['Key'])
                })

            return files

        except ClientError as e:
            logger.error(f"Error listing files in S3: {e}")
            return []

    def check_bucket_exists(self) -> bool:
        """Check if the S3 bucket exists and is accessible."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError:
            return False

    def create_bucket_if_not_exists(self) -> bool:
        """Create the S3 bucket if it doesn't exist."""
        if self.check_bucket_exists():
            return True

        try:
            location = {'LocationConstraint': settings.AWS_REGION}
            self.s3_client.create_bucket(
                Bucket=self.bucket_name,
                CreateBucketConfiguration=location
            )
            return True
        except ClientError as e:
            logger.error(f"Error creating S3 bucket: {e}")
            return False


# Singleton instance
s3_service = S3Service()