"""
Production Ready Services.

Services for Phase 8 tasks:
- User onboarding (Task 8.1)
- Help documentation (Task 8.2)
- Error handling (Task 8.3)
- Security audit (Task 8.5)
- Subscription & billing (Task 8.7)

Phase 8 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.production_ready import (
    OnboardingProgress, OnboardingStep,
    HelpArticle,
    AuditLogEntry,
    OrganizationSubscription, SubscriptionTier, SubscriptionStatus,
    SUBSCRIPTION_TIERS,
)


class OnboardingService:
    """Service for user onboarding flow."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create(self, user_id: str, organization_id: Optional[UUID] = None) -> OnboardingProgress:
        """Get or create onboarding progress for user."""
        query = select(OnboardingProgress).where(OnboardingProgress.user_id == user_id)
        result = await self.db.execute(query)
        progress = result.scalar_one_or_none()
        
        if not progress:
            progress = OnboardingProgress(
                user_id=user_id,
                organization_id=organization_id,
                current_step=OnboardingStep.WELCOME.value,
            )
            self.db.add(progress)
            await self.db.commit()
            await self.db.refresh(progress)
        
        return progress
    
    async def complete_step(
        self,
        user_id: str,
        step: str,
        created_resource_id: Optional[UUID] = None,
    ) -> OnboardingProgress:
        """Mark a step as complete."""
        progress = await self.get_or_create(user_id)
        
        # Update step completion
        step_field = f"{step}_completed"
        if hasattr(progress, step_field):
            setattr(progress, step_field, True)
        
        # Track created resources
        if created_resource_id:
            if step == OnboardingStep.FIRST_CLIENT.value:
                progress.created_client_id = created_resource_id
            elif step == OnboardingStep.UPLOAD_DOCUMENT.value:
                progress.created_document_id = created_resource_id
            elif step == OnboardingStep.CREATE_ENTRY.value:
                progress.created_entry_id = created_resource_id
        
        # Update timestamps
        timestamps = progress.step_timestamps or {}
        timestamps[step] = datetime.now(tz=timezone.utc).isoformat()
        progress.step_timestamps = timestamps
        
        # Calculate next step and check completion
        next_step = progress.get_next_step()
        progress.current_step = next_step
        
        if next_step == OnboardingStep.COMPLETED.value:
            progress.is_completed = True
            progress.completed_at = datetime.now(tz=timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(progress)
        
        return progress
    
    async def skip_onboarding(self, user_id: str) -> OnboardingProgress:
        """Skip the onboarding process."""
        progress = await self.get_or_create(user_id)
        progress.is_skipped = True
        progress.current_step = OnboardingStep.COMPLETED.value
        await self.db.commit()
        await self.db.refresh(progress)
        return progress
    
    async def reset_onboarding(self, user_id: str) -> OnboardingProgress:
        """Reset onboarding to start over."""
        progress = await self.get_or_create(user_id)
        
        progress.current_step = OnboardingStep.WELCOME.value
        progress.welcome_completed = False
        progress.company_profile_completed = False
        progress.ace_credentials_completed = False
        progress.first_client_completed = False
        progress.upload_document_completed = False
        progress.create_entry_completed = False
        progress.is_completed = False
        progress.is_skipped = False
        progress.completed_at = None
        progress.step_timestamps = {}
        
        await self.db.commit()
        await self.db.refresh(progress)
        
        return progress
    
    def get_step_content(self, step: str) -> Dict[str, Any]:
        """Get content/instructions for a step."""
        steps = {
            OnboardingStep.WELCOME.value: {
                "title": "Welcome to GATE",
                "description": "Let's get you set up in just a few minutes.",
                "help_text": "This wizard will guide you through the initial setup process.",
                "estimated_time": "5 minutes",
            },
            OnboardingStep.COMPANY_PROFILE.value: {
                "title": "Set Up Your Company Profile",
                "description": "Enter your brokerage information and contact details.",
                "help_text": "This information will appear on entries and reports.",
                "fields": ["company_name", "address", "phone", "email", "license_number"],
            },
            OnboardingStep.ACE_CREDENTIALS.value: {
                "title": "Connect to ACE",
                "description": "Enter your CBP ACE portal credentials for automated filing.",
                "help_text": "Your credentials are encrypted and stored securely.",
                "optional": True,
                "fields": ["ace_username", "ace_password", "filer_code", "port_code"],
            },
            OnboardingStep.FIRST_CLIENT.value: {
                "title": "Add Your First Client",
                "description": "Create an importer record to start filing entries.",
                "help_text": "You can add more clients later from the Clients page.",
                "fields": ["company_name", "ior_number", "address", "contact"],
            },
            OnboardingStep.UPLOAD_DOCUMENT.value: {
                "title": "Upload a Sample Document",
                "description": "Try our AI-powered document processing.",
                "help_text": "Upload a commercial invoice or packing list to see extraction.",
                "accepted_types": ["pdf", "png", "jpg"],
            },
            OnboardingStep.CREATE_ENTRY.value: {
                "title": "Create Your First Entry",
                "description": "Use extracted data to create a customs entry.",
                "help_text": "We'll walk you through each section of the entry form.",
            },
        }
        return steps.get(step, {"title": step, "description": ""})


class HelpService:
    """Service for help documentation."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_articles(
        self,
        category: Optional[str] = None,
        published_only: bool = True,
    ) -> List[HelpArticle]:
        """List help articles."""
        query = select(HelpArticle)
        
        conditions = []
        if category:
            conditions.append(HelpArticle.category == category)
        if published_only:
            conditions.append(HelpArticle.is_published == True)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(HelpArticle.order, HelpArticle.title)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_article(self, slug: str) -> Optional[HelpArticle]:
        """Get article by slug."""
        query = select(HelpArticle).where(HelpArticle.slug == slug)
        result = await self.db.execute(query)
        article = result.scalar_one_or_none()
        
        if article:
            # Increment view count
            article.view_count += 1
            await self.db.commit()
        
        return article
    
    async def search_articles(self, query_text: str, limit: int = 20) -> List[HelpArticle]:
        """Search help articles."""
        search = f"%{query_text.lower()}%"
        
        query = (
            select(HelpArticle)
            .where(
                and_(
                    HelpArticle.is_published == True,
                    or_(
                        func.lower(HelpArticle.title).like(search),
                        func.lower(HelpArticle.summary).like(search),
                        func.lower(HelpArticle.content).like(search),
                    )
                )
            )
            .order_by(HelpArticle.view_count.desc())
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def mark_helpful(self, slug: str, is_helpful: bool) -> None:
        """Mark article as helpful or not."""
        article = await self.get_article(slug)
        if article:
            if is_helpful:
                article.helpful_count += 1
            else:
                article.not_helpful_count += 1
            await self.db.commit()
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories with article counts."""
        query = (
            select(
                HelpArticle.category,
                func.count(HelpArticle.id).label("count"),
            )
            .where(HelpArticle.is_published == True)
            .group_by(HelpArticle.category)
            .order_by(HelpArticle.category)
        )
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [{"category": row.category, "count": row.count} for row in rows]
    
    async def get_featured_articles(self, limit: int = 5) -> List[HelpArticle]:
        """Get featured articles."""
        query = (
            select(HelpArticle)
            .where(
                and_(
                    HelpArticle.is_published == True,
                    HelpArticle.is_featured == True,
                )
            )
            .order_by(HelpArticle.view_count.desc())
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()


class AuditLogService:
    """Service for security audit logging."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        organization_id: Optional[UUID] = None,
        client_id: Optional[UUID] = None,
        details: Optional[Dict] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> AuditLogEntry:
        """Create an audit log entry."""
        entry = AuditLogEntry(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=organization_id,
            client_id=client_id,
            details=details or {},
            status=status,
            error_message=error_message,
        )
        
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        
        return entry
    
    async def list_logs(
        self,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """List audit log entries."""
        query = select(AuditLogEntry)
        
        conditions = []
        if action:
            conditions.append(AuditLogEntry.action == action)
        if resource_type:
            conditions.append(AuditLogEntry.resource_type == resource_type)
        if user_id:
            conditions.append(AuditLogEntry.user_id == user_id)
        if organization_id:
            conditions.append(AuditLogEntry.organization_id == organization_id)
        if start_date:
            conditions.append(AuditLogEntry.created_at >= start_date)
        if end_date:
            conditions.append(AuditLogEntry.created_at <= end_date + timedelta(days=1))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(AuditLogEntry.created_at)).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_security_summary(
        self,
        organization_id: Optional[UUID] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get security summary for dashboard."""
        start_date = date.today() - timedelta(days=days)
        
        query = select(AuditLogEntry).where(AuditLogEntry.created_at >= start_date)
        
        if organization_id:
            query = query.where(AuditLogEntry.organization_id == organization_id)
        
        result = await self.db.execute(query)
        logs = result.scalars().all()
        
        # Analyze logs
        total_events = len(logs)
        failed_events = sum(1 for l in logs if l.status == "failed")
        
        action_counts = {}
        for l in logs:
            action_counts[l.action] = action_counts.get(l.action, 0) + 1
        
        return {
            "period_days": days,
            "total_events": total_events,
            "failed_events": failed_events,
            "success_rate": round((total_events - failed_events) / total_events * 100, 1) if total_events > 0 else 100,
            "top_actions": sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        }


class SubscriptionService:
    """Service for subscription and billing management."""
    
    TRIAL_DAYS = 14
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create_subscription(self, organization_id: UUID) -> OrganizationSubscription:
        """Get or create subscription for organization."""
        query = select(OrganizationSubscription).where(
            OrganizationSubscription.organization_id == organization_id
        )
        result = await self.db.execute(query)
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            # Create new subscription with trial
            now = datetime.now(tz=timezone.utc)
            subscription = OrganizationSubscription(
                organization_id=organization_id,
                tier=SubscriptionTier.FREE.value,
                status=SubscriptionStatus.TRIALING.value,
                trial_start=now,
                trial_end=now + timedelta(days=self.TRIAL_DAYS),
                entries_limit=SUBSCRIPTION_TIERS[SubscriptionTier.STARTER.value]["entries_per_month"],
            )
            self.db.add(subscription)
            await self.db.commit()
            await self.db.refresh(subscription)
        
        return subscription
    
    async def get_subscription(self, organization_id: UUID) -> Optional[OrganizationSubscription]:
        """Get subscription for organization."""
        query = select(OrganizationSubscription).where(
            OrganizationSubscription.organization_id == organization_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def upgrade_tier(
        self,
        organization_id: UUID,
        new_tier: str,
        stripe_subscription_id: Optional[str] = None,
    ) -> OrganizationSubscription:
        """Upgrade subscription tier."""
        subscription = await self.get_or_create_subscription(organization_id)
        
        if new_tier not in SUBSCRIPTION_TIERS:
            raise ValueError(f"Invalid tier: {new_tier}")
        
        tier_config = SUBSCRIPTION_TIERS[new_tier]
        
        subscription.tier = new_tier
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.entries_limit = tier_config["entries_per_month"]
        
        if stripe_subscription_id:
            subscription.stripe_subscription_id = stripe_subscription_id
        
        now = datetime.now(tz=timezone.utc)
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=30)
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return subscription
    
    async def downgrade_tier(
        self,
        organization_id: UUID,
        new_tier: str,
    ) -> OrganizationSubscription:
        """Downgrade at end of current period."""
        subscription = await self.get_or_create_subscription(organization_id)
        
        if new_tier not in SUBSCRIPTION_TIERS:
            raise ValueError(f"Invalid tier: {new_tier}")
        
        # Schedule downgrade at period end
        subscription.cancel_at_period_end = True
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return subscription
    
    async def cancel_subscription(
        self,
        organization_id: UUID,
        at_period_end: bool = True,
    ) -> OrganizationSubscription:
        """Cancel subscription."""
        subscription = await self.get_or_create_subscription(organization_id)
        
        subscription.canceled_at = datetime.now(tz=timezone.utc)
        
        if at_period_end:
            subscription.cancel_at_period_end = True
        else:
            subscription.status = SubscriptionStatus.CANCELED.value
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return subscription
    
    async def record_payment(
        self,
        organization_id: UUID,
        amount_cents: int,
    ) -> OrganizationSubscription:
        """Record successful payment."""
        subscription = await self.get_or_create_subscription(organization_id)
        
        subscription.last_payment_at = datetime.now(tz=timezone.utc)
        subscription.last_payment_amount = amount_cents
        subscription.payment_failed_at = None
        subscription.payment_retry_count = 0
        
        # Extend period
        subscription.current_period_start = datetime.now(tz=timezone.utc)
        subscription.current_period_end = datetime.now(tz=timezone.utc) + timedelta(days=30)
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return subscription
    
    async def record_payment_failure(
        self,
        organization_id: UUID,
        error_message: Optional[str] = None,
    ) -> OrganizationSubscription:
        """Record payment failure."""
        subscription = await self.get_or_create_subscription(organization_id)
        
        subscription.payment_failed_at = datetime.now(tz=timezone.utc)
        subscription.payment_retry_count += 1
        subscription.status = SubscriptionStatus.PAST_DUE.value
        
        await self.db.commit()
        await self.db.refresh(subscription)
        
        return subscription
    
    async def increment_entry_count(self, organization_id: UUID) -> bool:
        """Increment entry count. Returns True if allowed."""
        subscription = await self.get_or_create_subscription(organization_id)
        
        if not subscription.can_create_entry():
            return False
        
        subscription.entries_this_month += 1
        await self.db.commit()
        
        return True
    
    async def reset_monthly_usage(self) -> int:
        """Reset monthly usage counters. Returns count of subscriptions reset."""
        query = select(OrganizationSubscription)
        result = await self.db.execute(query)
        subscriptions = result.scalars().all()
        
        count = 0
        for sub in subscriptions:
            if sub.entries_this_month > 0:
                sub.entries_this_month = 0
                count += 1
        
        await self.db.commit()
        return count
    
    def get_tier_info(self, tier: str) -> Dict[str, Any]:
        """Get tier information."""
        return SUBSCRIPTION_TIERS.get(tier, {})
    
    def get_all_tiers(self) -> Dict[str, Dict]:
        """Get all tier information."""
        return SUBSCRIPTION_TIERS


class ErrorHandlingService:
    """
    Service for standardized error handling.
    
    Task 8.3 from ROADMAP_FULL_WORKFLOW.md
    """
    
    # Standard error messages for common scenarios
    ERROR_MESSAGES = {
        "not_found": "The requested resource was not found.",
        "unauthorized": "You must be logged in to access this resource.",
        "forbidden": "You don't have permission to access this resource.",
        "validation_error": "The provided data is invalid.",
        "rate_limited": "Too many requests. Please try again later.",
        "server_error": "An unexpected error occurred. Please try again.",
        "maintenance": "System is under maintenance. Please try again later.",
        "client_not_found": "Client not found.",
        "entry_not_found": "Entry not found.",
        "document_not_found": "Document not found.",
        "invalid_status_transition": "This status change is not allowed.",
        "entry_limit_reached": "You've reached your entry limit for this month.",
        "payment_required": "Please update your payment method to continue.",
        "trial_expired": "Your trial has expired. Please subscribe to continue.",
    }
    
    @classmethod
    def get_user_message(cls, error_code: str, fallback: Optional[str] = None) -> str:
        """Get user-friendly error message."""
        return cls.ERROR_MESSAGES.get(error_code, fallback or cls.ERROR_MESSAGES["server_error"])
    
    @classmethod
    def format_validation_errors(cls, errors: List[Dict]) -> Dict[str, List[str]]:
        """Format validation errors for display."""
        formatted = {}
        for error in errors:
            field = error.get("loc", ["unknown"])[-1]
            message = error.get("msg", "Invalid value")
            
            if field not in formatted:
                formatted[field] = []
            formatted[field].append(message)
        
        return formatted
    
    @classmethod
    def sanitize_error_for_client(cls, error: Exception) -> Dict[str, Any]:
        """Sanitize error for client response (no stack traces)."""
        error_type = type(error).__name__
        
        # Map exception types to user-friendly messages
        error_map = {
            "ValueError": "validation_error",
            "PermissionError": "forbidden",
            "NotFoundError": "not_found",
            "AuthenticationError": "unauthorized",
        }
        
        code = error_map.get(error_type, "server_error")
        
        return {
            "error": True,
            "code": code,
            "message": cls.get_user_message(code),
            "detail": str(error) if code != "server_error" else None,
        }
