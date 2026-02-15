import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/doc_ingestion",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/doc_ingestion",
        alias="DATABASE_URL_SYNC",
    )

    # Supabase
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")

    # Storage
    storage_provider: str = Field(default="supabase", alias="STORAGE_PROVIDER")
    supabase_storage_endpoint: str = Field(default="", alias="SUPABASE_STORAGE_ENDPOINT")
    supabase_storage_access_key: str = Field(default="", alias="SUPABASE_STORAGE_ACCESS_KEY")
    supabase_storage_secret_key: str = Field(default="", alias="SUPABASE_STORAGE_SECRET_KEY")
    supabase_storage_bucket: str = Field(default="raw-files", alias="SUPABASE_STORAGE_BUCKET")
    supabase_storage_region: str = Field(default="us-east-1", alias="SUPABASE_STORAGE_REGION")
    max_upload_size_mb: int = Field(default=100, alias="MAX_UPLOAD_SIZE_MB")
    signed_url_ttl_seconds: int = Field(default=3600, alias="SIGNED_URL_TTL_SECONDS")

    # Redis & Celery
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0",
        alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_RESULT_BACKEND",
    )

    # Vector Store
    vector_store_backend: str = Field(default="supabase", alias="VECTOR_STORE_BACKEND")
    vector_store_url: str = Field(default="", alias="VECTOR_STORE_URL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="OPENAI_EMBEDDING_MODEL",
    )

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Security
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")

    # Sentry
    sentry_dsn: Optional[str] = Field(default=None, alias="SENTRY_DSN")
    sentry_environment: str = Field(default="development", alias="SENTRY_ENV")
    sentry_traces_sample_rate: float = Field(default=0.1, alias="SENTRY_TRACES_SAMPLE_RATE")
    sentry_enabled: bool = Field(default=False, alias="SENTRY_ENABLED")

    # SMTP for notifications
    smtp_host: Optional[str] = Field(default=None, alias="SMTP_HOST")
    smtp_port: Optional[int] = Field(default=587, alias="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="noreply@example.com", alias="SMTP_FROM_EMAIL")
    smtp_tls: bool = Field(default=True, alias="SMTP_TLS")

    # Email Ingestion
    email_imap_host: Optional[str] = Field(default=None, alias="EMAIL_IMAP_HOST")
    email_imap_port: int = Field(default=993, alias="EMAIL_IMAP_PORT")
    email_imap_user: Optional[str] = Field(default=None, alias="EMAIL_IMAP_USER")
    email_imap_password: Optional[str] = Field(default=None, alias="EMAIL_IMAP_PASSWORD")
    email_folder: str = Field(default="INBOX", alias="EMAIL_FOLDER")
    email_processed_folder: str = Field(default="Processed", alias="EMAIL_PROCESSED_FOLDER")
    email_poll_interval_minutes: int = Field(default=5, alias="EMAIL_POLL_INTERVAL_MINUTES")
    # Email Filters
    email_lookback_days: int = Field(default=7, alias="EMAIL_LOOKBACK_DAYS")  # Only process last N days
    email_allowed_senders: Optional[str] = Field(default=None, alias="EMAIL_ALLOWED_SENDERS")  # Comma-separated
    email_subject_keywords: Optional[str] = Field(default=None, alias="EMAIL_SUBJECT_KEYWORDS")  # Comma-separated

    # Backup Configuration
    s3_backup_bucket: Optional[str] = Field(default=None, alias="S3_BACKUP_BUCKET")
    s3_access_key: Optional[str] = Field(default=None, alias="S3_ACCESS_KEY")
    s3_secret_key: Optional[str] = Field(default=None, alias="S3_SECRET_KEY")
    backup_retention_days: int = Field(default=30, alias="BACKUP_RETENTION_DAYS")
    encryption_passphrase: Optional[str] = Field(default=None, alias="ENCRYPTION_PASSPHRASE")

    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # CORS Configuration
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:3001,http://localhost:8080",
        alias="CORS_ORIGINS",
    )  # Comma-separated list of allowed origins

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_default: str = Field(default="100/minute", alias="RATE_LIMIT_DEFAULT")
    rate_limit_burst: str = Field(default="200/minute", alias="RATE_LIMIT_BURST")
    rate_limit_storage_url: str = Field(default="memory://", alias="RATE_LIMIT_STORAGE")

    # Customer Tier Rate Limits (requests per minute)
    tier_starter_limit: int = Field(default=60, alias="TIER_STARTER_LIMIT")
    tier_professional_limit: int = Field(default=200, alias="TIER_PROFESSIONAL_LIMIT")
    tier_enterprise_limit: int = Field(default=1000, alias="TIER_ENTERPRISE_LIMIT")

    # ACE Transmission (CBP SFTP)
    ace_sftp_enabled: bool = Field(default=False, alias="ACE_SFTP_ENABLED")
    ace_sftp_host: str = Field(default="", alias="ACE_SFTP_HOST")
    ace_sftp_port: int = Field(default=22, alias="ACE_SFTP_PORT")
    ace_sftp_user: str = Field(default="", alias="ACE_SFTP_USER")
    ace_sftp_key_path: str = Field(default="", alias="ACE_SFTP_KEY_PATH")
    ace_upload_path: str = Field(default="/incoming", alias="ACE_UPLOAD_PATH")
    ace_response_path: str = Field(default="/outgoing", alias="ACE_RESPONSE_PATH")

    # SMTP / Email
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="noreply@gate-platform.com", alias="SMTP_FROM_EMAIL")
    smtp_tls: bool = Field(default=True, alias="SMTP_TLS")

    @property
    def cors_origins_list(self) -> list:
        """Parse CORS origins into a list."""
        if self.environment == "development":
            return ["*"]  # Allow all in development
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
