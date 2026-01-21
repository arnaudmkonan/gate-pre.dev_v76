import logging
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.services.storage_callback_service import StorageCallbackService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/callbacks", tags=["callbacks"])


def get_callback_secret() -> str:
    """Get callback secret from config."""
    secret = getattr(settings, "storage_callback_secret", None)
    if not secret:
        # Fallback to a default for development
        secret = "dev-secret-change-in-production"
    return secret


@router.post("/storage", status_code=status.HTTP_200_OK)
async def handle_storage_callback(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """
    Handle storage callback from Supabase or S3.

    Expected headers:
    - X-Signature-256: HMAC-SHA256 signature of the request body

    Expected payload:
    {
        "path": "uploads/filename.txt",  # or "storage_path"
        "status": "stored",  # or "failed"
        "error_message": "Optional error message if status is failed"
    }

    Returns:
        200 OK on success
        400 Bad Request for invalid payload
        401 Unauthorized for invalid signature
        500 Internal Server Error for processing errors
    """
    try:
        # Get raw request body
        body = await request.body()
        body_str = body.decode("utf-8")

        # Get signature from headers
        signature = request.headers.get("X-Signature-256")
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Signature-256 header",
            )

        # Validate signature
        secret = get_callback_secret()
        is_valid = StorageCallbackService.validate_signature(
            payload=body_str,
            signature=signature,
            secret=secret,
        )

        if not is_valid:
            logger.warning(f"Invalid signature for storage callback")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        # Parse payload
        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )

        # Process callback
        result = await StorageCallbackService.process_callback(
            session=session,
            payload=payload,
        )

        if not result.get("success"):
            logger.error(f"Failed to process callback: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to process callback"),
            )

        logger.info(f"Storage callback processed successfully: {result}")

        return {
            "success": True,
            "message": result.get("message", "Callback processed"),
            "file_id": result.get("file_id"),
            "storage_path": result.get("storage_path"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing storage callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process callback",
        )
