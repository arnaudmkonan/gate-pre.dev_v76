"""
GATE Platform — SQLAlchemy Base Models.

Provides the declarative Base and a BaseModel mixin with
common fields (id, created_at, updated_at).

Note: updated_at is maintained via an SQLAlchemy event listener so that
ORM-level mutations (attribute changes → session.commit) correctly
update the timestamp — unlike `onupdate=` which only fires for bulk
SQL UPDATE statements.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, event
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()


class BaseModel(Base):
    """Base model with common fields shared by all GATE entities."""

    __abstract__ = True

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


@event.listens_for(BaseModel, "before_update", propagate=True)
def _set_updated_at(mapper, connection, target):
    """
    Automatically set updated_at on every ORM-level update.

    SQLAlchemy's `onupdate=` only fires for bulk SQL UPDATE statements,
    not for ORM attribute mutations.  This event listener covers both
    cases without any per-model boilerplate.
    """
    target.updated_at = datetime.now(timezone.utc)
