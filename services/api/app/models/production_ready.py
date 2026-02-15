"""
User Onboarding Models and Service.

Tracks onboarding progress and guides new users through setup.

Task 8.1 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from app.models.base import BaseModel


class OnboardingStep(str, Enum):
    """Onboarding workflow steps."""
    WELCOME = "welcome"
    COMPANY_PROFILE = "company_profile"
    ACE_CREDENTIALS = "ace_credentials"
    FIRST_CLIENT = "first_client"
    UPLOAD_DOCUMENT = "upload_document"
    CREATE_ENTRY = "create_entry"
    COMPLETED = "completed"


class OnboardingProgress(BaseModel):
    """
    Tracks user onboarding progress.
    """
    __tablename__ = "onboarding_progress"
    
    user_id = Column(String(100), nullable=False, unique=True, index=True)
    organization_id = Column(PGUUID(as_uuid=True), nullable=True)
    
    # Current step
    current_step = Column(String(30), default=OnboardingStep.WELCOME.value, nullable=False)
    
    # Step completion status
    welcome_completed = Column(Boolean, default=False, nullable=False)
    company_profile_completed = Column(Boolean, default=False, nullable=False)
    ace_credentials_completed = Column(Boolean, default=False, nullable=False)
    first_client_completed = Column(Boolean, default=False, nullable=False)
    upload_document_completed = Column(Boolean, default=False, nullable=False)
    create_entry_completed = Column(Boolean, default=False, nullable=False)
    
    # Overall status
    is_completed = Column(Boolean, default=False, nullable=False)
    is_skipped = Column(Boolean, default=False, nullable=False)
    
    # Step completion timestamps
    step_timestamps = Column(JSONB, default={}, nullable=True)
    
    # Completion tracking
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Created resources during onboarding
    created_client_id = Column(PGUUID(as_uuid=True), nullable=True)
    created_document_id = Column(PGUUID(as_uuid=True), nullable=True)
    created_entry_id = Column(PGUUID(as_uuid=True), nullable=True)
    
    __table_args__ = (
        Index("ix_onboarding_user", "user_id"),
        Index("ix_onboarding_status", "is_completed"),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "current_step": self.current_step,
            "steps": {
                "welcome": self.welcome_completed,
                "company_profile": self.company_profile_completed,
                "ace_credentials": self.ace_credentials_completed,
                "first_client": self.first_client_completed,
                "upload_document": self.upload_document_completed,
                "create_entry": self.create_entry_completed,
            },
            "is_completed": self.is_completed,
            "is_skipped": self.is_skipped,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress_percentage": self.get_progress_percentage(),
        }
    
    def get_progress_percentage(self) -> int:
        """Calculate completion percentage."""
        steps_completed = sum([
            self.welcome_completed,
            self.company_profile_completed,
            self.ace_credentials_completed,
            self.first_client_completed,
            self.upload_document_completed,
            self.create_entry_completed,
        ])
        return int(steps_completed / 6 * 100)
    
    def get_next_step(self) -> Optional[str]:
        """Get the next incomplete step."""
        if not self.welcome_completed:
            return OnboardingStep.WELCOME.value
        if not self.company_profile_completed:
            return OnboardingStep.COMPANY_PROFILE.value
        if not self.ace_credentials_completed:
            return OnboardingStep.ACE_CREDENTIALS.value
        if not self.first_client_completed:
            return OnboardingStep.FIRST_CLIENT.value
        if not self.upload_document_completed:
            return OnboardingStep.UPLOAD_DOCUMENT.value
        if not self.create_entry_completed:
            return OnboardingStep.CREATE_ENTRY.value
        return OnboardingStep.COMPLETED.value


class HelpArticle(BaseModel):
    """
    Help documentation article.
    
    Task 8.2 from ROADMAP_FULL_WORKFLOW.md
    """
    __tablename__ = "help_articles"
    
    # Article metadata
    slug = Column(String(100), nullable=False, unique=True, index=True)
    title = Column(String(300), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    subcategory = Column(String(50), nullable=True)
    
    # Content
    summary = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    content_format = Column(String(20), default="markdown")
    
    # Media
    video_url = Column(String(500), nullable=True)
    screenshots = Column(JSONB, default=[], nullable=True)
    
    # Ordering & visibility
    order = Column(Integer, default=0, nullable=False)
    is_published = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    
    # Search optimization
    keywords = Column(JSONB, default=[], nullable=True)
    
    # Analytics
    view_count = Column(Integer, default=0, nullable=False)
    helpful_count = Column(Integer, default=0, nullable=False)
    not_helpful_count = Column(Integer, default=0, nullable=False)
    
    __table_args__ = (
        Index("ix_help_articles_published", "is_published"),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "slug": self.slug,
            "title": self.title,
            "category": self.category,
            "subcategory": self.subcategory,
            "summary": self.summary,
            "content": self.content,
            "video_url": self.video_url,
            "screenshots": self.screenshots,
            "is_featured": self.is_featured,
            "view_count": self.view_count,
            "helpful_count": self.helpful_count,
        }


class AuditLogEntry(BaseModel):
    """
    Audit log for security tracking.
    
    Task 8.5 from ROADMAP_FULL_WORKFLOW.md
    """
    __tablename__ = "security_audit_log"
    
    # Action info
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(100), nullable=True)
    
    # Actor info
    user_id = Column(String(100), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Context
    organization_id = Column(PGUUID(as_uuid=True), nullable=True)
    client_id = Column(PGUUID(as_uuid=True), nullable=True)
    
    # Details
    details = Column(JSONB, default={}, nullable=True)
    
    # Status
    status = Column(String(20), default="success", nullable=False)
    error_message = Column(Text, nullable=True)
    
    __table_args__ = (
        Index("ix_audit_log_action", "action"),
        Index("ix_audit_log_resource", "resource_type", "resource_id"),
        Index("ix_audit_log_user", "user_id"),
        Index("ix_audit_log_time", "created_at"),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "ip_address": self.ip_address,
            "details": self.details,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SubscriptionTier(str, Enum):
    """Subscription tiers."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription statuses."""
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    PAUSED = "paused"


class OrganizationSubscription(BaseModel):
    """
    Organization subscription for billing.
    
    Task 8.7 from ROADMAP_FULL_WORKFLOW.md
    """
    __tablename__ = "organization_subscriptions"
    
    organization_id = Column(PGUUID(as_uuid=True), nullable=False, unique=True, index=True)
    
    # Tier and status
    tier = Column(String(30), default=SubscriptionTier.FREE.value, nullable=False)
    status = Column(String(30), default=SubscriptionStatus.TRIALING.value, nullable=False)
    
    # Stripe integration
    stripe_customer_id = Column(String(100), nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True)
    stripe_payment_method_id = Column(String(100), nullable=True)
    
    # Trial
    trial_start = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    trial_extended_by_days = Column(Integer, default=0)
    
    # Billing period
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    
    # Usage
    entries_this_month = Column(Integer, default=0, nullable=False)
    entries_limit = Column(Integer, default=50, nullable=False)  # Free tier limit
    
    # Payment
    last_payment_at = Column(DateTime(timezone=True), nullable=True)
    last_payment_amount = Column(Integer, nullable=True)  # In cents
    payment_failed_at = Column(DateTime(timezone=True), nullable=True)
    payment_retry_count = Column(Integer, default=0)
    
    # Cancellation
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    
    __table_args__ = (
        Index("ix_subscriptions_org", "organization_id"),
        Index("ix_subscriptions_status", "status"),
        Index("ix_subscriptions_tier", "tier"),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "tier": self.tier,
            "status": self.status,
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "entries_this_month": self.entries_this_month,
            "entries_limit": self.entries_limit,
            "cancel_at_period_end": self.cancel_at_period_end,
            "has_payment_method": self.stripe_payment_method_id is not None,
        }
    
    def is_trialing(self) -> bool:
        """Check if in trial period."""
        if self.trial_end:
            return datetime.now(tz=timezone.utc) < self.trial_end
        return False
    
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value]
    
    def can_create_entry(self) -> bool:
        """Check if org can create more entries."""
        if self.tier in [SubscriptionTier.PROFESSIONAL.value, SubscriptionTier.ENTERPRISE.value]:
            return True  # Unlimited
        return self.entries_this_month < self.entries_limit


# Tier pricing and limits
SUBSCRIPTION_TIERS = {
    SubscriptionTier.FREE.value: {
        "name": "Free",
        "price_monthly": 0,
        "entries_per_month": 10,
        "clients": 1,
        "users": 1,
        "features": ["Basic entry filing", "Single client", "Email support"],
    },
    SubscriptionTier.STARTER.value: {
        "name": "Starter",
        "price_monthly": 299,  # $299/mo
        "entries_per_month": 50,
        "clients": 5,
        "users": 2,
        "features": ["All Free features", "5 clients", "Priority email support", "Basic reports"],
    },
    SubscriptionTier.PROFESSIONAL.value: {
        "name": "Professional",
        "price_monthly": 599,  # $599/mo
        "entries_per_month": 500,
        "clients": 50,
        "users": 10,
        "features": ["All Starter features", "Unlimited entries", "Client portal", "Advanced reports", "ACE integration"],
    },
    SubscriptionTier.ENTERPRISE.value: {
        "name": "Enterprise",
        "price_monthly": 1499,  # $1499/mo
        "entries_per_month": -1,  # Unlimited
        "clients": -1,  # Unlimited
        "users": -1,  # Unlimited
        "features": ["All Professional features", "Dedicated support", "Custom integrations", "SLA guarantee", "Audit logging"],
    },
}
