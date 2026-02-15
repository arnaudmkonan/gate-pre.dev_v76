"""
API routes for LLM Agent processing.

Provides endpoints to:
- Trigger agent analysis on documents
- View agent processing results
- Check agent processing status
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.document_metadata import DocumentMetadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["Agents"])


class AgentProcessRequest(BaseModel):
    """Request to process a document with agents."""
    
    document_id: str = Field(..., description="UUID of the document to process")
    pipeline_type: str = Field(
        default="standard",
        description="Pipeline type: 'standard' or 'analysis'"
    )


class AgentProcessResponse(BaseModel):
    """Response from agent processing request."""
    
    task_id: str
    document_id: str
    pipeline_type: str
    status: str = "queued"
    message: str = "Agent processing has been queued"


class AgentInfo(BaseModel):
    """Information about a single agent."""
    
    name: str
    description: str
    capabilities: List[str]


class AvailableAgentsResponse(BaseModel):
    """List of available agents."""
    
    agents: List[AgentInfo]
    pipeline_types: List[str]


class AgentResultResponse(BaseModel):
    """Agent processing results for a document."""
    
    document_id: str
    filename: str
    has_results: bool
    classification: Optional[str] = None
    confidence: Optional[float] = None
    processing_status: str = "pending"


@router.get("/available", response_model=AvailableAgentsResponse)
async def get_available_agents():
    """Get list of available agents and their capabilities."""
    
    agents = [
        AgentInfo(
            name="DocumentClassifierAgent",
            description="Classifies documents into predefined categories",
            capabilities=["Classification", "Category detection", "Confidence scoring"]
        ),
        AgentInfo(
            name="MultiLabelClassifierAgent",
            description="Assigns multiple labels to documents",
            capabilities=["Multi-label tagging", "PII detection", "Sensitivity labeling"]
        ),
        AgentInfo(
            name="EntityExtractionAgent",
            description="Extracts structured entities from documents",
            capabilities=["Named entity recognition", "Relationship extraction", "Normalization"]
        ),
        AgentInfo(
            name="SummarizationAgent",
            description="Creates intelligent document summaries",
            capabilities=["Executive summary", "Key points", "Action items"]
        ),
        AgentInfo(
            name="KeyInsightsAgent",
            description="Extracts strategic insights and recommendations",
            capabilities=["Insight extraction", "Risk identification", "Opportunity spotting"]
        ),
        AgentInfo(
            name="QAGenerationAgent",
            description="Generates Q&A pairs from documents",
            capabilities=["FAQ generation", "Question answering", "Knowledge base creation"]
        ),
        AgentInfo(
            name="QualityReviewAgent",
            description="Reviews and validates processing quality",
            capabilities=["Quality scoring", "Issue identification", "Improvement suggestions"]
        ),
        AgentInfo(
            name="ComplianceCheckAgent",
            description="Checks documents for compliance requirements",
            capabilities=["PII handling", "Data classification", "Regulatory compliance"]
        ),
    ]
    
    return AvailableAgentsResponse(
        agents=agents,
        pipeline_types=["standard", "analysis"]
    )


@router.post("/process", response_model=AgentProcessResponse)
async def process_document_with_agents(
    request: AgentProcessRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Trigger agent processing on a document.
    
    The document must have been previously ingested and have extracted content.
    The document_id can be either a document_metadata ID or an ingest_jobs ID (job_id).
    """
    try:
        # Verify document exists
        doc_uuid = UUID(request.document_id)
        
        # First try to find by document_metadata.id
        result = await session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = result.scalar_one_or_none()
        
        # If not found, try looking up by job_id
        if not doc:
            result = await session.execute(
                select(DocumentMetadata).where(DocumentMetadata.job_id == doc_uuid)
            )
            doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not doc.extracted_text_snippet:
            raise HTTPException(
                status_code=400, 
                detail="Document has no extracted content for analysis"
            )
        
        # Queue the agent processing task - pass the actual document_metadata.id
        from app.workers.agent_processor import process_with_agents
        
        task = process_with_agents.delay(
            str(doc.id),  # Use the actual document_metadata.id
            request.pipeline_type
        )
        
        return AgentProcessResponse(
            task_id=task.id,
            document_id=str(doc.id),
            pipeline_type=request.pipeline_type,
            status="queued",
            message=f"Agent processing queued for {doc.filename}"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid document ID: {e}")
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Failed to queue agent processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{document_id}", response_model=AgentResultResponse)
async def get_agent_results(
    document_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get agent processing results for a document.
    
    The document_id can be either a document_metadata ID or an ingest_jobs ID (job_id).
    """
    
    try:
        doc_uuid = UUID(document_id)
        
        # First try to find by document_metadata.id
        result = await session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = result.scalar_one_or_none()
        
        # If not found, try looking up by job_id
        if not doc:
            result = await session.execute(
                select(DocumentMetadata).where(DocumentMetadata.job_id == doc_uuid)
            )
            doc = result.scalar_one_or_none()
        
        if not doc:
            # Return a valid response with has_results=False instead of 404
            # This prevents JSON parse errors in the frontend
            return AgentResultResponse(
                document_id=document_id,
                filename="unknown",
                has_results=False,
                classification=None,
                confidence=None,
                processing_status="not_found"
            )
        
        # Check if agents have processed this document
        # (We're using detected_language as a marker for classification result)
        has_results = doc.detected_language is not None
        
        return AgentResultResponse(
            document_id=str(doc.id),
            filename=doc.filename,
            has_results=has_results,
            classification=doc.detected_language if has_results else None,
            confidence=0.8 if has_results else None,  # Would be stored in metadata
            processing_status="completed" if has_results else "pending"
        )
        
    except ValueError:
        # Invalid UUID format - return a valid response
        return AgentResultResponse(
            document_id=document_id,
            filename="unknown",
            has_results=False,
            classification=None,
            confidence=None,
            processing_status="invalid_id"
        )
    except Exception as e:
        logger.error(f"Failed to get agent results: {e}")
        # Return a valid JSON response instead of raising an exception
        return AgentResultResponse(
            document_id=document_id,
            filename="unknown",
            has_results=False,
            classification=None,
            confidence=None,
            processing_status="error"
        )


@router.get("/status/{task_id}")
async def get_agent_task_status(task_id: str):
    """Get the status of an agent processing task."""
    
    from app.core.celery_app import celery_app
    
    try:
        result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
        }
        
        if result.ready():
            if result.successful():
                response["result"] = result.result
            else:
                response["error"] = str(result.result)
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-all-pending")
async def process_all_pending_documents():
    """Trigger processing of all pending documents that need agent analysis."""
    
    from app.workers.agent_processor import process_pending_documents
    
    try:
        task = process_pending_documents.delay()
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": "Batch agent processing has been queued"
        }
        
    except Exception as e:
        logger.error(f"Failed to queue batch processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))
