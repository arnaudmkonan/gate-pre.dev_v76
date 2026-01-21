from sqlalchemy import Boolean, Column, Integer, String, Text

from app.models.base import BaseModel


class CeleryConfig(BaseModel):
    """Celery/Redis configuration model."""

    __tablename__ = "celery_config"

    redis_host = Column(String(255), nullable=False)
    redis_port = Column(Integer, default=6379, nullable=False)
    redis_password = Column(Text, nullable=True)  # Encrypted in application layer
    result_backend = Column(String(500), nullable=False)
    worker_concurrency = Column(Integer, default=4, nullable=False)
    task_timeout = Column(Integer, default=3600, nullable=False)  # seconds
    max_retries = Column(Integer, default=3, nullable=False)
    retry_backoff = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
