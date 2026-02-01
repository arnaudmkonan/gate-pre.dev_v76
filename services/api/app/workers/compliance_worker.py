"""
Celery worker for compliance checks on extracted documents.

This worker processes documents after extraction to run:
1. HTS code validation
2. OFAC SDN party screening
3. NAICS code classification

Results are stored in document_metadata.compliance_results.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.models.document_metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class ComplianceStatus:
    """Compliance check status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_compliance_checks(self, document_id: str) -> Dict[str, Any]:
    """
    Run HTS/OFAC/NAICS compliance checks on an extracted document.
    
    Args:
        document_id: UUID of the DocumentMetadata record
        
    Returns:
        Dict with compliance check results
    """
    try:
        logger.info(f"Starting compliance checks for document {document_id}")
        result = _run_compliance_sync(document_id)
        logger.info(f"Compliance checks completed for document {document_id}: {result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"Error running compliance checks for {document_id}: {e}")
        _update_compliance_status(document_id, ComplianceStatus.FAILED, error=str(e))
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


def _run_compliance_sync(document_id: str) -> Dict[str, Any]:
    """Run compliance checks synchronously."""
    from app.services.post_extraction_service import PostExtractionService
    
    doc_uuid = UUID(document_id)
    
    with get_sync_db() as session:
        # Get document metadata
        result = session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc_metadata = result.scalar_one_or_none()
        
        if not doc_metadata:
            raise ValueError(f"Document {document_id} not found")
        
        # Update status to processing
        doc_metadata.compliance_status = ComplianceStatus.PROCESSING
        session.add(doc_metadata)
        session.commit()
        
        # Skip if no extracted text
        if not doc_metadata.extracted_text_snippet:
            logger.info(f"Document {document_id} has no extracted text, skipping compliance checks")
            doc_metadata.compliance_status = ComplianceStatus.SKIPPED
            doc_metadata.compliance_results = {"skipped_reason": "no_extracted_text"}
            doc_metadata.compliance_checked_at = datetime.now(timezone.utc)
            session.add(doc_metadata)
            session.commit()
            return {"status": "skipped", "reason": "no_extracted_text"}
        
        # Run compliance checks using PostExtractionService (sync version)
        try:
            compliance_result = _run_post_extraction_sync(
                session,
                document_id=document_id,
                extracted_text=doc_metadata.extracted_text_snippet,
                filename=doc_metadata.filename
            )
            
            # Update document with results
            doc_metadata.compliance_status = ComplianceStatus.COMPLETED
            doc_metadata.compliance_results = compliance_result
            doc_metadata.compliance_checked_at = datetime.now(timezone.utc)
            session.add(doc_metadata)
            session.commit()
            
            return {
                "status": "completed",
                "document_id": document_id,
                "checks_performed": list(compliance_result.keys()),
                "overall_risk": compliance_result.get("overall_risk_level", "unknown")
            }
            
        except Exception as e:
            logger.error(f"Compliance check error for {document_id}: {e}")
            doc_metadata.compliance_status = ComplianceStatus.FAILED
            doc_metadata.compliance_results = {"error": str(e)}
            doc_metadata.compliance_checked_at = datetime.now(timezone.utc)
            session.add(doc_metadata)
            session.commit()
            raise


def _run_post_extraction_sync(
    session,
    document_id: str,
    extracted_text: str,
    filename: str
) -> Dict[str, Any]:
    """
    Run post-extraction compliance checks synchronously.
    
    Uses the synchronous methods from PostExtractionService.
    """
    from app.services.post_extraction_service import (
        PostExtractionService, 
        PostExtractionResult,
        RiskLevel
    )
    
    results = {
        "hts_validations": [],
        "party_screenings": [],
        "naics_classifications": [],
        "overall_risk_level": RiskLevel.CLEAR,
        "issues_found": [],
    }
    
    # Extract potential HTS codes from text (simple pattern matching)
    hts_codes = _extract_hts_from_text(extracted_text)
    if hts_codes:
        logger.info(f"Found {len(hts_codes)} potential HTS codes in document")
        results["hts_validations"] = [{"code": code, "status": "found"} for code in hts_codes[:5]]
    
    # Extract party names for OFAC screening
    parties = _extract_parties_from_text(extracted_text)
    if parties:
        logger.info(f"Found {len(parties)} parties for OFAC screening")
        for party_name, party_type in parties[:5]:  # Limit to 5 parties
            screening_result = _screen_party_sync(session, party_name, party_type)
            results["party_screenings"].append(screening_result)
            
            # Update risk level if matches found
            if screening_result.get("matches_found", 0) > 0:
                results["overall_risk_level"] = RiskLevel.HIGH
                results["issues_found"].append({
                    "type": "ofac_match",
                    "party": party_name,
                    "matches": screening_result.get("matches_found", 0)
                })
    
    # NAICS classification based on product descriptions
    products = _extract_products_from_text(extracted_text)
    if products:
        logger.info(f"Found {len(products)} products for NAICS classification")
        naics_result = _classify_naics_sync(session, products[:5])
        results["naics_classifications"] = naics_result
    
    return results


def _extract_hts_from_text(text: str) -> list:
    """Extract potential HTS codes from text using regex."""
    import re
    
    # HTS pattern: 4-10 digits, optionally with periods
    pattern = r'\b(\d{4}(?:\.\d{2}(?:\.\d{2,4})?)?)\b'
    matches = re.findall(pattern, text)
    
    # Filter to likely HTS codes (4+ digits)
    hts_codes = []
    for match in matches:
        digits = match.replace(".", "")
        if 4 <= len(digits) <= 10:
            hts_codes.append(match)
    
    return list(set(hts_codes))[:10]  # Dedupe and limit


def _extract_parties_from_text(text: str) -> list:
    """Extract party names from common document patterns."""
    parties = []
    
    # Common party field patterns
    patterns = [
        (r"(?:shipper|exporter|seller)[:\s]+([A-Z][A-Za-z\s&,.]+(?:Ltd|Inc|Corp|Co|LLC)?)", "seller"),
        (r"(?:consignee|buyer|importer)[:\s]+([A-Z][A-Za-z\s&,.]+(?:Ltd|Inc|Corp|Co|LLC)?)", "buyer"),
        (r"(?:notify\s*party)[:\s]+([A-Z][A-Za-z\s&,.]+(?:Ltd|Inc|Corp|Co|LLC)?)", "notify_party"),
    ]
    
    import re
    for pattern, party_type in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches[:2]:  # Max 2 per type
            name = match.strip()
            if len(name) > 3:  # Skip very short matches
                parties.append((name, party_type))
    
    return parties


def _extract_products_from_text(text: str) -> list:
    """Extract product descriptions from text."""
    products = []
    
    # Look for description field patterns
    import re
    patterns = [
        r"(?:description|goods|merchandise|commodity)[:\s]+([^\n]{10,100})",
        r"(?:item|product)[:\s]+([^\n]{5,100})",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        products.extend(matches)
    
    return products[:5]


def _screen_party_sync(session, party_name: str, party_type: str) -> Dict[str, Any]:
    """Screen a party against OFAC SDN list synchronously."""
    from app.models.reference_data import OFACSdn
    from sqlalchemy import func, or_, String
    
    result = {
        "party_name": party_name,
        "party_type": party_type,
        "matches_found": 0,
        "matches": [],
        "risk_level": "clear"
    }
    
    if not party_name or len(party_name) < 3:
        return result
    
    # Simple prefix search
    prefix = party_name.upper()[:10]
    
    try:
        stmt = select(OFACSdn).where(
            or_(
                func.upper(OFACSdn.sdn_name).like(f"{prefix}%"),
                OFACSdn.aliases.cast(String).ilike(f"%{prefix}%"),
            )
        ).limit(5)
        
        matches = session.execute(stmt).scalars().all()
        
        if matches:
            result["matches_found"] = len(matches)
            result["risk_level"] = "high" if len(matches) > 0 else "clear"
            result["matches"] = [
                {
                    "sdn_name": m.sdn_name,
                    "sdn_type": m.sdn_type,
                    "program": m.program
                }
                for m in matches[:3]
            ]
    except Exception as e:
        logger.warning(f"OFAC screening error for {party_name}: {e}")
        result["error"] = str(e)
    
    return result


def _classify_naics_sync(session, product_descriptions: list) -> list:
    """Classify products to NAICS codes synchronously."""
    from app.models.reference_data import NAICSCode
    from sqlalchemy import or_
    
    results = []
    
    for description in product_descriptions:
        # Extract key words for search
        words = description.lower().split()[:3]
        if not words:
            continue
        
        try:
            conditions = [NAICSCode.title.ilike(f"%{word}%") for word in words]
            stmt = select(NAICSCode).where(or_(*conditions)).limit(3)
            
            matches = session.execute(stmt).scalars().all()
            
            for match in matches:
                results.append({
                    "naics_code": match.naics_code,
                    "title": match.title,
                    "sector": match.sector,
                    "based_on": description[:50]
                })
        except Exception as e:
            logger.warning(f"NAICS classification error: {e}")
    
    return results


def _update_compliance_status(
    document_id: str, 
    status: str, 
    error: Optional[str] = None
):
    """Update compliance status in database."""
    try:
        doc_uuid = UUID(document_id)
        with get_sync_db() as session:
            result = session.execute(
                select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
            )
            doc_metadata = result.scalar_one_or_none()
            
            if doc_metadata:
                doc_metadata.compliance_status = status
                if error:
                    doc_metadata.compliance_results = {"error": error}
                doc_metadata.compliance_checked_at = datetime.now(timezone.utc)
                session.add(doc_metadata)
                session.commit()
    except Exception as e:
        logger.error(f"Failed to update compliance status: {e}")


@celery_app.task(bind=True)
def process_pending_compliance(self) -> Dict[str, Any]:
    """
    Periodic task to find documents with pending compliance and run checks.
    
    This task:
    1. Finds all documents with compliance_status = 'pending'
    2. Queues them for compliance processing
    3. Reports status
    """
    try:
        logger.info("Checking for pending compliance checks...")
        result = _process_pending_compliance_sync()
        logger.info(f"Pending compliance processing completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Error processing pending compliance: {e}")
        raise


def _process_pending_compliance_sync() -> Dict[str, Any]:
    """Find and process pending compliance checks."""
    with get_sync_db() as session:
        # Get documents with pending compliance (limit to 10 at a time)
        result = session.execute(
            select(DocumentMetadata).where(
                DocumentMetadata.compliance_status == ComplianceStatus.PENDING,
                DocumentMetadata.ingestion_status == "completed"  # Only check completed extractions
            ).limit(10)
        )
        pending_docs = result.scalars().all()
        
        logger.info(f"Found {len(pending_docs)} documents with pending compliance")
        
        queued_count = 0
        for doc in pending_docs:
            try:
                run_compliance_checks.delay(str(doc.id))
                queued_count += 1
                logger.info(f"Queued compliance checks for: {doc.filename}")
            except Exception as e:
                logger.error(f"Error queuing compliance for {doc.id}: {e}")
        
        return {
            "status": "completed",
            "pending_found": len(pending_docs),
            "queued_for_processing": queued_count,
        }
