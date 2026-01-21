"""Celery tasks for automated backups and maintenance."""
import logging
import os
from datetime import datetime, timedelta

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    name="backup.database",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=300
)
def backup_database(self):
    """Backup PostgreSQL database to S3."""
    try:
        from services.api.tools.backup.pg_backup import PostgresBackup

        logger.info("Starting database backup task")

        backup = PostgresBackup(
            database_url=settings.database_url,
            s3_bucket=settings.s3_backup_bucket,
            s3_access_key=settings.s3_access_key,
            s3_secret_key=settings.s3_secret_key
        )

        result = backup.run_full_backup(
            retention_days=settings.backup_retention_days
        )

        if result["status"] == "success":
            logger.info("Database backup completed successfully")
            return {
                "status": "success",
                "backup": result["backup"],
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise Exception(f"Backup failed: {result}")

    except Exception as exc:
        logger.error(f"Database backup failed: {exc}")
        # Retry after 5 minutes on failure
        self.retry(exc=exc)


@celery_app.task(
    name="backup.storage",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=300
)
def backup_storage(self):
    """Backup Supabase Storage to S3."""
    try:
        from services.api.tools.backup.storage_backup import StorageBackup

        logger.info("Starting storage backup task")

        backup = StorageBackup(
            supabase_url=settings.supabase_url,
            supabase_service_key=settings.supabase_service_role_key,
            s3_bucket=settings.s3_backup_bucket,
            s3_access_key=settings.s3_access_key,
            s3_secret_key=settings.s3_secret_key
        )

        result = backup.run_full_backup(
            buckets=["raw-files", "silver-data"]
        )

        logger.info(f"Storage backup completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Storage backup failed: {exc}")
        self.retry(exc=exc)


@celery_app.task(
    name="backup.verify",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=2
)
def verify_backups(self):
    """Verify backup integrity."""
    try:
        import boto3
        from datetime import datetime, timedelta

        logger.info("Starting backup verification task")

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key
        )

        # Check recent backups
        response = s3_client.list_objects_v2(
            Bucket=settings.s3_backup_bucket,
            Prefix="database/backups/",
            MaxKeys=10
        )

        if "Contents" not in response:
            logger.warning("No backups found to verify")
            return {"status": "no_backups"}

        # Verify recent backups
        cutoff_time = datetime.utcnow() - timedelta(days=1)
        verified = 0
        failed = 0

        for obj in response["Contents"]:
            last_modified = obj["LastModified"].replace(tzinfo=None)
            if last_modified > cutoff_time:
                try:
                    # Check object exists and is accessible
                    s3_client.head_object(
                        Bucket=settings.s3_backup_bucket,
                        Key=obj["Key"]
                    )
                    verified += 1
                except Exception as e:
                    logger.error(f"Failed to verify {obj['Key']}: {e}")
                    failed += 1

        logger.info(f"Backup verification completed: {verified} verified, {failed} failed")

        return {
            "status": "completed",
            "verified": verified,
            "failed": failed
        }

    except Exception as exc:
        logger.error(f"Backup verification failed: {exc}")
        self.retry(exc=exc)


@celery_app.task(
    name="backup.cleanup",
    bind=True
)
def cleanup_old_backups(self):
    """Clean up old backups based on retention policy."""
    try:
        import boto3
        from datetime import datetime, timedelta

        logger.info("Starting backup cleanup task")

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key
        )

        cutoff_date = datetime.utcnow() - timedelta(days=settings.backup_retention_days)
        deleted = 0

        # Cleanup database backups
        response = s3_client.list_objects_v2(
            Bucket=settings.s3_backup_bucket,
            Prefix="database/backups/"
        )

        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["LastModified"].replace(tzinfo=None) < cutoff_date:
                    logger.info(f"Deleting old backup: {obj['Key']}")
                    s3_client.delete_object(
                        Bucket=settings.s3_backup_bucket,
                        Key=obj["Key"]
                    )
                    deleted += 1

        # Cleanup storage backups
        response = s3_client.list_objects_v2(
            Bucket=settings.s3_backup_bucket,
            Prefix="storage/backups/"
        )

        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["LastModified"].replace(tzinfo=None) < cutoff_date:
                    logger.info(f"Deleting old backup: {obj['Key']}")
                    s3_client.delete_object(
                        Bucket=settings.s3_backup_bucket,
                        Key=obj["Key"]
                    )
                    deleted += 1

        logger.info(f"Backup cleanup completed: {deleted} files deleted")

        return {
            "status": "completed",
            "deleted": deleted
        }

    except Exception as exc:
        logger.error(f"Backup cleanup failed: {exc}")
        raise


@celery_app.task(
    name="maintenance.database",
    bind=True
)
def database_maintenance(self):
    """Perform database maintenance tasks."""
    try:
        from sqlalchemy import text
        from app.core.database import SessionLocal

        logger.info("Starting database maintenance task")

        with SessionLocal() as session:
            # Analyze tables
            session.execute(text("ANALYZE;"))
            logger.info("Database analysis completed")

            # Cleanup old audit logs
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            session.execute(
                text("""
                DELETE FROM audit_logs
                WHERE created_at < :cutoff_date
                """),
                {"cutoff_date": cutoff_date}
            )
            logger.info("Cleaned up old audit logs")

            # Vacuum (if needed)
            session.execute(text("VACUUM ANALYZE;"))
            logger.info("Database vacuum completed")

            session.commit()

        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as exc:
        logger.error(f"Database maintenance failed: {exc}")
        raise


# Schedule tasks
celery_app.conf.beat_schedule = {
    # Run backups daily at 2 AM UTC
    "backup-database": {
        "task": "backup.database",
        "schedule": 86400,  # Every 24 hours
        "options": {"expires": 3600}
    },
    "backup-storage": {
        "task": "backup.storage",
        "schedule": 86400,
        "options": {"expires": 3600}
    },

    # Verify backups daily at 3 AM UTC
    "verify-backups": {
        "task": "backup.verify",
        "schedule": 86400,
        "options": {"expires": 3600}
    },

    # Cleanup old backups weekly
    "cleanup-backups": {
        "task": "backup.cleanup",
        "schedule": 604800,  # Every 7 days
        "options": {"expires": 3600}
    },

    # Database maintenance weekly
    "database-maintenance": {
        "task": "maintenance.database",
        "schedule": 604800,
        "options": {"expires": 3600}
    }
}


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if len(sys.argv) < 2:
        print("Usage: backup_tasks.py <backup-database|backup-storage|verify-backups|cleanup|maintenance>")
        sys.exit(1)

    task = sys.argv[1]

    if task == "backup-database":
        result = backup_database()
    elif task == "backup-storage":
        result = backup_storage()
    elif task == "verify-backups":
        result = verify_backups()
    elif task == "cleanup":
        result = cleanup_old_backups()
    elif task == "maintenance":
        result = database_maintenance()
    else:
        print(f"Unknown task: {task}")
        sys.exit(1)

    print(f"Task completed: {result}")
