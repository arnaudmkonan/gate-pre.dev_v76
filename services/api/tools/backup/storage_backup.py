"""Supabase Storage backup utility."""
import os
import logging
from datetime import datetime
from pathlib import Path
import boto3
from supabase import create_client

logger = logging.getLogger(__name__)


class StorageBackup:
    """Handles Supabase Storage backups."""

    def __init__(
        self,
        supabase_url: str,
        supabase_service_key: str,
        s3_bucket: str,
        s3_access_key: str,
        s3_secret_key: str,
        backup_dir: str = "/tmp/backups/storage"
    ):
        """Initialize storage backup handler."""
        self.supabase = create_client(supabase_url, supabase_service_key)
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key
        )
        self.s3_bucket = s3_bucket
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup_bucket(self, bucket_name: str) -> dict:
        """Backup all objects from a Supabase storage bucket."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        bucket_backup_dir = self.backup_dir / f"{bucket_name}-{timestamp}"
        bucket_backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Backing up storage bucket: {bucket_name}")

        try:
            # List all objects in bucket
            files = self.supabase.storage.from_(bucket_name).list()

            total_size = 0
            file_count = 0

            for file_obj in files:
                file_path = file_obj["name"]
                logger.debug(f"Downloading: {file_path}")

                try:
                    # Download file
                    file_data = self.supabase.storage.from_(bucket_name).download(file_path)

                    # Create local directory structure
                    local_path = bucket_backup_dir / file_path
                    local_path.parent.mkdir(parents=True, exist_ok=True)

                    # Write file
                    with open(local_path, "wb") as f:
                        f.write(file_data)

                    total_size += len(file_data)
                    file_count += 1

                except Exception as e:
                    logger.warning(f"Failed to download {file_path}: {e}")
                    continue

            logger.info(
                f"Bucket backup completed: {file_count} files, {total_size} bytes"
            )

            return {
                "status": "success",
                "bucket": bucket_name,
                "file_count": file_count,
                "total_size": total_size,
                "backup_dir": str(bucket_backup_dir),
                "timestamp": timestamp
            }

        except Exception as e:
            logger.error(f"Bucket backup failed: {e}")
            return {
                "status": "failed",
                "bucket": bucket_name,
                "error": str(e)
            }

    def upload_backup_to_s3(self, backup_dir: str, bucket_name: str) -> dict:
        """Upload backup directory to S3."""
        backup_path = Path(backup_dir)
        timestamp = backup_path.name.split("-")[-2:]
        s3_prefix = f"storage/backups/{bucket_name}/{'-'.join(timestamp)}"

        logger.info(f"Uploading backup to S3: {s3_prefix}")

        try:
            total_uploaded = 0
            file_count = 0

            for file_path in backup_path.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(backup_path)
                    s3_key = f"{s3_prefix}/{relative_path}"

                    self.s3_client.upload_file(
                        str(file_path),
                        self.s3_bucket,
                        s3_key,
                        ExtraArgs={"ServerSideEncryption": "AES256"}
                    )

                    total_uploaded += file_path.stat().st_size
                    file_count += 1

            logger.info(f"Uploaded {file_count} files to S3")

            return {
                "status": "uploaded",
                "file_count": file_count,
                "total_size": total_uploaded,
                "s3_prefix": s3_prefix
            }

        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            raise

    def run_full_backup(self, buckets: list = None) -> dict:
        """Execute full storage backup workflow."""
        if buckets is None:
            buckets = ["raw-files", "silver-data"]

        logger.info(f"Starting storage backup for {len(buckets)} buckets")

        results = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "buckets": {}
        }

        for bucket in buckets:
            try:
                backup_info = self.backup_bucket(bucket)
                if backup_info["status"] == "success":
                    upload_info = self.upload_backup_to_s3(
                        backup_info["backup_dir"],
                        bucket
                    )
                    results["buckets"][bucket] = {
                        "backup": backup_info,
                        "upload": upload_info
                    }
                else:
                    results["buckets"][bucket] = backup_info
                    results["status"] = "partial"
            except Exception as e:
                logger.error(f"Failed to backup {bucket}: {e}")
                results["buckets"][bucket] = {"status": "failed", "error": str(e)}
                results["status"] = "partial"

        return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    s3_bucket = os.getenv("S3_BACKUP_BUCKET")
    s3_access_key = os.getenv("S3_ACCESS_KEY")
    s3_secret_key = os.getenv("S3_SECRET_KEY")

    if not all([supabase_url, supabase_key, s3_bucket, s3_access_key, s3_secret_key]):
        logger.error("Missing required environment variables")
        exit(1)

    backup = StorageBackup(
        supabase_url=supabase_url,
        supabase_service_key=supabase_key,
        s3_bucket=s3_bucket,
        s3_access_key=s3_access_key,
        s3_secret_key=s3_secret_key
    )

    result = backup.run_full_backup()
    logger.info(f"Backup result: {result}")
    exit(0 if result["status"] != "failed" else 1)
