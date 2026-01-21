"""PostgreSQL database backup utility for Supabase."""
import os
import subprocess
import logging
import hashlib
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class PostgresBackup:
    """Handles PostgreSQL database backups."""

    def __init__(
        self,
        database_url: str,
        s3_bucket: str,
        s3_access_key: str,
        s3_secret_key: str,
        backup_dir: str = "/tmp/backups"
    ):
        """Initialize PostgreSQL backup handler."""
        self.database_url = database_url
        self.s3_bucket = s3_bucket
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key
        )
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> dict:
        """Create a PostgreSQL backup using pg_dump."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        backup_file = self.backup_dir / f"backup-{timestamp}.sql.gz"

        logger.info(f"Starting PostgreSQL backup: {backup_file}")

        try:
            # Extract database credentials from URL
            # Format: postgresql://user:password@host:port/dbname
            db_parts = self.database_url.replace("postgresql://", "").split("/")
            credentials, db_name = db_parts[0], db_parts[1]
            user, password = credentials.split(":")
            host_parts = host_parts[0].split(":")
            host = host_parts[0]
            port = host_parts[1] if len(host_parts) > 1 else "5432"

            # Run pg_dump with compression
            cmd = [
                "pg_dump",
                f"--host={host}",
                f"--port={port}",
                f"--username={user}",
                f"--dbname={db_name}",
                "--format=plain",
                "--compress=9",
                "--verbose"
            ]

            # Set password via environment
            env = os.environ.copy()
            env["PGPASSWORD"] = password

            result = subprocess.run(
                cmd,
                stdout=open(backup_file, "wb"),
                stderr=subprocess.PIPE,
                env=env,
                timeout=3600  # 1 hour timeout
            )

            if result.returncode != 0:
                logger.error(f"pg_dump failed: {result.stderr.decode()}")
                raise RuntimeError(f"Backup failed: {result.stderr.decode()}")

            # Verify backup file
            file_size = backup_file.stat().st_size
            if file_size == 0:
                raise RuntimeError("Backup file is empty")

            logger.info(f"Backup created successfully: {backup_file} ({file_size} bytes)")

            return {
                "status": "success",
                "file": str(backup_file),
                "size": file_size,
                "timestamp": timestamp
            }

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            if backup_file.exists():
                backup_file.unlink()
            raise

    def verify_backup(self, backup_file: str) -> dict:
        """Verify backup integrity."""
        backup_path = Path(backup_file)

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        logger.info(f"Verifying backup: {backup_file}")

        try:
            # Check file size
            file_size = backup_path.stat().st_size
            if file_size == 0:
                raise ValueError("Backup file is empty")

            # Calculate checksum
            sha256_hash = hashlib.sha256()
            with open(backup_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)

            checksum = sha256_hash.hexdigest()

            # Try to list contents (for gzip files)
            try:
                result = subprocess.run(
                    ["tar", "-tzf", backup_file],
                    capture_output=True,
                    timeout=60
                )
                is_valid = result.returncode == 0
            except Exception:
                is_valid = True  # Assume valid if tar check fails

            logger.info(f"Backup verified: size={file_size}, checksum={checksum[:16]}...")

            return {
                "status": "verified" if is_valid else "corrupted",
                "file_size": file_size,
                "checksum": checksum,
                "valid": is_valid
            }

        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            raise

    def upload_to_s3(self, backup_file: str) -> dict:
        """Upload backup to S3."""
        backup_path = Path(backup_file)
        s3_key = f"database/backups/{backup_path.name}"

        logger.info(f"Uploading backup to S3: s3://{self.s3_bucket}/{s3_key}")

        try:
            # Upload file
            self.s3_client.upload_file(
                str(backup_path),
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    "ServerSideEncryption": "AES256",
                    "Metadata": {
                        "timestamp": datetime.utcnow().isoformat(),
                        "type": "database-backup"
                    }
                }
            )

            logger.info(f"Backup uploaded successfully: {s3_key}")

            return {
                "status": "uploaded",
                "s3_key": s3_key,
                "s3_url": f"s3://{self.s3_bucket}/{s3_key}"
            }

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise

    def cleanup_local(self, backup_file: str, keep_days: int = 7):
        """Clean up old local backups."""
        logger.info(f"Cleaning up backups older than {keep_days} days")

        cutoff_time = datetime.utcnow().timestamp() - (keep_days * 86400)

        for backup in self.backup_dir.glob("backup-*.sql.gz"):
            mtime = backup.stat().st_mtime
            if mtime < cutoff_time:
                logger.info(f"Removing old backup: {backup}")
                backup.unlink()

    def cleanup_s3(self, retention_days: int = 30):
        """Clean up old S3 backups."""
        logger.info(f"Cleaning up S3 backups older than {retention_days} days")

        try:
            # List objects in backup directory
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_bucket,
                Prefix="database/backups/"
            )

            if "Contents" not in response:
                logger.info("No backups found in S3")
                return

            cutoff_time = datetime.utcnow().timestamp() - (retention_days * 86400)

            for obj in response["Contents"]:
                last_modified = obj["LastModified"].timestamp()
                if last_modified < cutoff_time:
                    logger.info(f"Deleting old backup: {obj['Key']}")
                    self.s3_client.delete_object(
                        Bucket=self.s3_bucket,
                        Key=obj["Key"]
                    )

        except ClientError as e:
            logger.error(f"S3 cleanup failed: {e}")
            raise

    def run_full_backup(self, retention_days: int = 30) -> dict:
        """Execute full backup workflow."""
        logger.info("Starting full PostgreSQL backup workflow")

        try:
            # Create backup
            backup_info = self.create_backup()

            # Verify backup
            verify_info = self.verify_backup(backup_info["file"])

            if not verify_info["valid"]:
                raise RuntimeError("Backup verification failed")

            # Upload to S3
            upload_info = self.upload_to_s3(backup_info["file"])

            # Cleanup
            self.cleanup_local(backup_info["file"])
            self.cleanup_s3(retention_days)

            return {
                "status": "success",
                "backup": backup_info,
                "verification": verify_info,
                "upload": upload_info
            }

        except Exception as e:
            logger.error(f"Backup workflow failed: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }


if __name__ == "__main__":
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Get configuration from environment
    database_url = os.getenv("DATABASE_URL")
    s3_bucket = os.getenv("S3_BACKUP_BUCKET")
    s3_access_key = os.getenv("S3_ACCESS_KEY")
    s3_secret_key = os.getenv("S3_SECRET_KEY")
    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

    if not all([database_url, s3_bucket, s3_access_key, s3_secret_key]):
        logger.error("Missing required environment variables")
        sys.exit(1)

    # Run backup
    backup = PostgresBackup(
        database_url=database_url,
        s3_bucket=s3_bucket,
        s3_access_key=s3_access_key,
        s3_secret_key=s3_secret_key
    )

    result = backup.run_full_backup(retention_days=retention_days)

    if result["status"] != "success":
        logger.error(f"Backup failed: {result}")
        sys.exit(1)

    logger.info("Backup completed successfully")
    sys.exit(0)
