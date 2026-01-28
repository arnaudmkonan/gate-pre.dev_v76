"""
Production Ready API Routes.

Endpoints for:
- User onboarding (Task 8.1)
- Help documentation (Task 8.2)
- Error handling (Task 8.3)
- Performance optimization (Task 8.4)
- Security audit (Task 8.5)
- Deployment & infrastructure (Task 8.6)
- Subscription & billing (Task 8.7)

Phase 8 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


router = APIRouter(prefix="/api", tags=["Production Ready"])


# ==================== Request Models ====================

class CompleteOnboardingStepRequest(BaseModel):
    step: str
    created_resource_id: Optional[str] = None


class CreateHelpArticleRequest(BaseModel):
    slug: str
    title: str
    category: str
    content: str
    summary: Optional[str] = None
    subcategory: Optional[str] = None
    video_url: Optional[str] = None
    keywords: Optional[List[str]] = None


class UpgradeSubscriptionRequest(BaseModel):
    tier: str
    stripe_subscription_id: Optional[str] = None


class RecordPaymentRequest(BaseModel):
    amount_cents: int


# ==================== Onboarding (Task 8.1) ====================

@router.get("/onboarding/{user_id}")
async def get_onboarding_progress(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get onboarding progress for user."""
    from app.services.production_ready_service import OnboardingService
    
    service = OnboardingService(db)
    progress = await service.get_or_create(user_id)
    
    return {
        "progress": progress.to_dict(),
        "next_step": progress.get_next_step(),
        "step_content": service.get_step_content(progress.current_step),
    }


@router.post("/onboarding/{user_id}/complete-step")
async def complete_onboarding_step(
    user_id: str,
    request: CompleteOnboardingStepRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete an onboarding step."""
    from app.services.production_ready_service import OnboardingService
    
    service = OnboardingService(db)
    progress = await service.complete_step(
        user_id,
        request.step,
        UUID(request.created_resource_id) if request.created_resource_id else None,
    )
    
    return {
        "progress": progress.to_dict(),
        "next_step": progress.get_next_step(),
        "step_content": service.get_step_content(progress.current_step),
        "message": f"Step '{request.step}' completed",
    }


@router.post("/onboarding/{user_id}/skip")
async def skip_onboarding(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Skip the onboarding process."""
    from app.services.production_ready_service import OnboardingService
    
    service = OnboardingService(db)
    progress = await service.skip_onboarding(user_id)
    
    return {
        "progress": progress.to_dict(),
        "message": "Onboarding skipped",
    }


@router.post("/onboarding/{user_id}/reset")
async def reset_onboarding(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Reset onboarding to start over."""
    from app.services.production_ready_service import OnboardingService
    
    service = OnboardingService(db)
    progress = await service.reset_onboarding(user_id)
    
    return {
        "progress": progress.to_dict(),
        "message": "Onboarding reset",
    }


@router.get("/onboarding/steps")
async def get_onboarding_steps():
    """Get all onboarding steps with content."""
    from app.models.production_ready import OnboardingStep
    from app.services.production_ready_service import OnboardingService
    
    # Use a dummy service just for step content
    steps = []
    for step in OnboardingStep:
        if step != OnboardingStep.COMPLETED:
            content = OnboardingService.get_step_content(None, step.value)
            steps.append({
                "step": step.value,
                **content,
            })
    
    return {"steps": steps}


# ==================== Help Documentation (Task 8.2) ====================

@router.get("/help")
async def get_help_center(
    db: AsyncSession = Depends(get_db),
):
    """Get help center overview."""
    from app.services.production_ready_service import HelpService
    
    service = HelpService(db)
    
    categories = await service.get_categories()
    featured = await service.get_featured_articles()
    
    return {
        "categories": categories,
        "featured_articles": [a.to_dict() for a in featured],
    }


@router.get("/help/search")
async def search_help(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Search help articles."""
    from app.services.production_ready_service import HelpService
    
    service = HelpService(db)
    articles = await service.search_articles(q, limit)
    
    return {
        "query": q,
        "results": [a.to_dict() for a in articles],
        "count": len(articles),
    }


@router.get("/help/category/{category}")
async def get_help_category(
    category: str,
    db: AsyncSession = Depends(get_db),
):
    """Get articles in a category."""
    from app.services.production_ready_service import HelpService
    
    service = HelpService(db)
    articles = await service.list_articles(category=category)
    
    return {
        "category": category,
        "articles": [a.to_dict() for a in articles],
        "count": len(articles),
    }


@router.get("/help/article/{slug}")
async def get_help_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a help article by slug."""
    from app.services.production_ready_service import HelpService
    
    service = HelpService(db)
    article = await service.get_article(slug)
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return article.to_dict()


@router.post("/help/article/{slug}/feedback")
async def submit_article_feedback(
    slug: str,
    helpful: bool = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback on article helpfulness."""
    from app.services.production_ready_service import HelpService
    
    service = HelpService(db)
    await service.mark_helpful(slug, helpful)
    
    return {"message": "Thank you for your feedback!"}


@router.post("/help/articles")
async def create_help_article(
    request: CreateHelpArticleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new help article (admin only)."""
    from app.models.production_ready import HelpArticle
    
    article = HelpArticle(
        slug=request.slug,
        title=request.title,
        category=request.category,
        content=request.content,
        summary=request.summary,
        subcategory=request.subcategory,
        video_url=request.video_url,
        keywords=request.keywords or [],
    )
    
    db.add(article)
    await db.commit()
    await db.refresh(article)
    
    return {
        "article": article.to_dict(),
        "message": "Article created",
    }


# ==================== Audit Log (Task 8.5) ====================

@router.get("/audit-log")
async def get_audit_log(
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get audit log entries."""
    from app.services.production_ready_service import AuditLogService
    
    service = AuditLogService(db)
    
    logs = await service.list_logs(
        action=action,
        resource_type=resource_type,
        user_id=user_id,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
        limit=limit,
    )
    
    return {
        "logs": [l.to_dict() for l in logs],
        "count": len(logs),
    }


@router.get("/audit-log/summary")
async def get_security_summary(
    organization_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get security summary for dashboard."""
    from app.services.production_ready_service import AuditLogService
    
    service = AuditLogService(db)
    
    summary = await service.get_security_summary(
        organization_id=UUID(organization_id) if organization_id else None,
        days=days,
    )
    
    return summary


# ==================== Subscription & Billing (Task 8.7) ====================

@router.get("/subscriptions/tiers")
async def get_subscription_tiers():
    """Get available subscription tiers."""
    from app.services.production_ready_service import SubscriptionService
    
    service = SubscriptionService(None)
    
    return {
        "tiers": service.get_all_tiers(),
    }


@router.get("/subscriptions/{organization_id}")
async def get_subscription(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get subscription for organization."""
    from app.services.production_ready_service import SubscriptionService
    
    service = SubscriptionService(db)
    subscription = await service.get_or_create_subscription(UUID(organization_id))
    
    tier_info = service.get_tier_info(subscription.tier)
    
    return {
        "subscription": subscription.to_dict(),
        "tier_info": tier_info,
        "is_active": subscription.is_active(),
        "is_trialing": subscription.is_trialing(),
        "can_create_entry": subscription.can_create_entry(),
    }


@router.post("/subscriptions/{organization_id}/upgrade")
async def upgrade_subscription(
    organization_id: str,
    request: UpgradeSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Upgrade subscription tier."""
    from app.services.production_ready_service import SubscriptionService
    
    service = SubscriptionService(db)
    
    try:
        subscription = await service.upgrade_tier(
            UUID(organization_id),
            request.tier,
            request.stripe_subscription_id,
        )
        
        return {
            "subscription": subscription.to_dict(),
            "message": f"Upgraded to {request.tier}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/subscriptions/{organization_id}/cancel")
async def cancel_subscription(
    organization_id: str,
    at_period_end: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """Cancel subscription."""
    from app.services.production_ready_service import SubscriptionService
    
    service = SubscriptionService(db)
    subscription = await service.cancel_subscription(UUID(organization_id), at_period_end)
    
    return {
        "subscription": subscription.to_dict(),
        "message": "Subscription canceled" if not at_period_end else "Subscription will cancel at period end",
    }


@router.post("/subscriptions/{organization_id}/record-payment")
async def record_payment(
    organization_id: str,
    request: RecordPaymentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record a successful payment (webhook handler)."""
    from app.services.production_ready_service import SubscriptionService
    
    service = SubscriptionService(db)
    subscription = await service.record_payment(UUID(organization_id), request.amount_cents)
    
    return {
        "subscription": subscription.to_dict(),
        "message": "Payment recorded",
    }


@router.post("/subscriptions/{organization_id}/payment-failed")
async def record_payment_failure(
    organization_id: str,
    error_message: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Record a payment failure (webhook handler)."""
    from app.services.production_ready_service import SubscriptionService
    
    service = SubscriptionService(db)
    subscription = await service.record_payment_failure(UUID(organization_id), error_message)
    
    return {
        "subscription": subscription.to_dict(),
        "message": "Payment failure recorded",
    }


# ==================== Health & Performance (Tasks 8.4, 8.6) ====================

@router.get("/health/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db),
):
    """Detailed health check with component status."""
    from datetime import datetime
    from sqlalchemy import text
    import time
    
    # Database check
    db_start = time.time()
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
        db_latency = round((time.time() - db_start) * 1000, 2)
    except Exception as e:
        db_status = "unhealthy"
        db_latency = None
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": {
                "status": db_status,
                "latency_ms": db_latency,
            },
            "api": {
                "status": "healthy",
            },
        },
        "version": "1.0.0",
    }


@router.get("/health/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
):
    """Kubernetes readiness probe."""
    from sqlalchemy import text
    
    try:
        await db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception:
        raise HTTPException(status_code=503, detail="Not ready")


@router.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"alive": True}


# ==================== Error Reference ====================

@router.get("/errors/reference")
async def get_error_reference():
    """Get all error codes and messages."""
    from app.services.production_ready_service import ErrorHandlingService
    
    return {
        "error_codes": ErrorHandlingService.ERROR_MESSAGES,
    }
