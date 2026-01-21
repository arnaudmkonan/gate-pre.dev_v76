import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.models.storage_config import StorageConfig

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing object storage operations."""

    def __init__(self, config: StorageConfig):
        """Initialize storage service with config."""
        self.config = config
        self.client = self._init_client()

    def _init_client(self):
        """Initialize S3 client for Supabase-compatible storage."""
        try:
            return boto3.client(
                "s3",
                endpoint_url=self.config.endpoint,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                region_name=self.config.region,
            )
        except Exception as e:
            logger.error(f"Failed to initialize storage client: {e}")
            raise

    def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> dict:
        """Upload file to storage and return metadata."""
        try:
            # Compute checksum
            checksum = hashlib.sha256(file_bytes).hexdigest()
            storage_path = f"uploads/{filename}"

            # Upload file
            self.client.put_object(
                Bucket=self.config.bucket_name,
                Key=storage_path,
                Body=file_bytes,
                ContentType=content_type,
                Metadata={"checksum": checksum},
            )

            logger.info(f"File uploaded: {storage_path}, checksum: {checksum}")

            return {
                "storage_path": storage_path,
                "checksum": checksum,
                "file_size": len(file_bytes),
            }
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            raise

    def generate_signed_url(
        self,
        storage_path: str,
        ttl_seconds: int = 3600,
    ) -> tuple[str, datetime]:
        """Generate signed URL for file access."""
        try:
            signed_url = self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.config.bucket_name,
                    "Key": storage_path,
                },
                ExpiresIn=ttl_seconds,
            )

            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

            logger.info(f"Signed URL generated for: {storage_path}")
            return signed_url, expires_at

        except ClientError as e:
            logger.error(f"Error generating signed URL: {e}")
            raise

    def get_object_metadata(self, storage_path: str) -> dict:
        """Get object metadata from storage."""
        try:
            response = self.client.head_object(
                Bucket=self.config.bucket_name,
                Key=storage_path,
            )

            return {
                "file_size": response.get("ContentLength"),
                "mime_type": response.get("ContentType"),
                "last_modified": response.get("LastModified"),
                "metadata": response.get("Metadata", {}),
            }
        except ClientError as e:
            logger.error(f"Error getting object metadata: {e}")
            raise

    def delete_file(self, storage_path: str) -> bool:
        """Delete file from storage."""
        try:
            self.client.delete_object(
                Bucket=self.config.bucket_name,
                Key=storage_path,
            )
            logger.info(f"File deleted: {storage_path}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting file: {e}")
            raise

    def test_connection(self) -> bool:
        """Test storage connection by listing bucket with limit."""
        try:
            # Attempt a non-destructive operation to test connectivity
            self.client.list_objects_v2(
                Bucket=self.config.bucket_name,
                MaxKeys=1
            )
            logger.info(f"Storage connection test successful for bucket: {self.config.bucket_name}")
            return True
        except ClientError as e:
            logger.error(f"Storage connection test failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during storage connection test: {e}")
            raise
