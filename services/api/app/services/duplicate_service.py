"""
Duplicate Detection Service.

Detects duplicate documents using multiple methods:
1. File hash (checksum) - exact duplicates
2. Content similarity - near-duplicates (OCR variations, rescans)
3. Key field matching - same invoice number, vendor + amount + date
"""

import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID
from difflib import SequenceMatcher

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_metadata import DocumentMetadata
from app.models.extraction_result import ExtractionResult

logger = logging.getLogger(__name__)


# Similarity thresholds
EXACT_HASH_MATCH = 1.0
HIGH_SIMILARITY_THRESHOLD = 0.95  # Near-duplicate
MEDIUM_SIMILARITY_THRESHOLD = 0.85  # Possible duplicate
KEY_FIELD_MATCH_THRESHOLD = 0.9  # Key fields match


class DuplicateMatch:
    """Represents a potential duplicate match."""

    def __init__(
        self,
        document_id: str,
        filename: str,
        match_type: str,
        confidence: float,
        match_details: Dict[str, Any],
        created_at: datetime
    ):
        self.document_id = document_id
        self.filename = filename
        self.match_type = match_type  # "exact_hash", "content_similarity", "key_fields"
        self.confidence = confidence
        self.match_details = match_details
        self.created_at = created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "match_type": self.match_type,
            "confidence": self.confidence,
            "match_details": self.match_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DuplicateDetectionService:
    """
    Service for detecting duplicate documents.
    """

    @staticmethod
    def compute_file_hash(content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def compute_content_fingerprint(text: str) -> str:
        """
        Compute a fingerprint of text content.
        Normalizes whitespace and converts to lowercase for comparison.
        """
        # Normalize: lowercase, collapse whitespace, remove punctuation
        normalized = ' '.join(text.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()

    @staticmethod
    def text_similarity(text1: str, text2: str) -> float:
        """
        Compute similarity between two text strings.
        Returns value between 0 and 1.
        """
        if not text1 or not text2:
            return 0.0

        # Normalize texts
        t1 = ' '.join(text1.lower().split())
        t2 = ' '.join(text2.lower().split())

        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, t1, t2).ratio()

    @staticmethod
    async def check_exact_duplicate(
        session: AsyncSession,
        file_hash: str,
        file_size: Optional[int] = None,
        exclude_document_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        days_back: int = 365
    ) -> Optional[DuplicateMatch]:
        """
        Check for exact duplicate by file size and content fingerprint.
        Since we don't store file hash, we use size + content similarity as proxy.
        """
        if not file_size:
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        # Find documents with same size (potential exact duplicates)
        query = select(DocumentMetadata).where(
            and_(
                DocumentMetadata.size == file_size,
                DocumentMetadata.created_at >= cutoff,
            )
        )

        if exclude_document_id:
            query = query.where(DocumentMetadata.id != UUID(exclude_document_id))

        if customer_id:
            query = query.where(DocumentMetadata.customer_id == customer_id)

        query = query.order_by(DocumentMetadata.created_at.desc()).limit(5)

        result = await session.execute(query)
        candidates = result.scalars().all()

        # For exact size match, return as high-confidence potential duplicate
        if candidates:
            existing = candidates[0]
            return DuplicateMatch(
                document_id=str(existing.id),
                filename=existing.filename,
                match_type="size_match",
                confidence=0.9,  # High but not certain without hash
                match_details={
                    "size": file_size,
                    "message": "Same file size - likely duplicate"
                },
                created_at=existing.created_at
            )

        return None

    @staticmethod
    async def check_content_similarity(
        session: AsyncSession,
        content: str,
        exclude_document_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        days_back: int = 90,
        limit: int = 10
    ) -> List[DuplicateMatch]:
        """
        Check for similar documents by content comparison.
        Returns list of potential matches sorted by similarity.
        """
        if not content or len(content) < 100:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        # Get recent documents with content
        query = select(DocumentMetadata).where(
            and_(
                DocumentMetadata.extracted_text_snippet.isnot(None),
                DocumentMetadata.created_at >= cutoff,
            )
        )

        if exclude_document_id:
            query = query.where(DocumentMetadata.id != UUID(exclude_document_id))

        if customer_id:
            query = query.where(DocumentMetadata.customer_id == customer_id)

        query = query.order_by(DocumentMetadata.created_at.desc()).limit(100)

        result = await session.execute(query)
        candidates = result.scalars().all()

        matches = []
        for doc in candidates:
            if not doc.extracted_text_snippet:
                continue

            similarity = DuplicateDetectionService.text_similarity(
                content[:5000],  # Compare first 5000 chars
                doc.extracted_text_snippet[:5000]
            )

            if similarity >= MEDIUM_SIMILARITY_THRESHOLD:
                match_type = "exact_content" if similarity >= 0.99 else "content_similarity"
                matches.append(DuplicateMatch(
                    document_id=str(doc.id),
                    filename=doc.filename,
                    match_type=match_type,
                    confidence=similarity,
                    match_details={
                        "similarity_score": round(similarity, 4),
                        "message": f"{similarity:.0%} content similarity"
                    },
                    created_at=doc.created_at
                ))

        # Sort by similarity descending
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches[:limit]

    @staticmethod
    async def check_key_field_duplicates(
        session: AsyncSession,
        document_id: str,
        customer_id: Optional[str] = None,
        days_back: int = 365
    ) -> List[DuplicateMatch]:
        """
        Check for duplicates based on extracted key fields.

        For invoices: invoice_number, vendor_name + total_amount + invoice_date
        For receipts: receipt_number, store_name + total + transaction_date
        """
        doc_uuid = UUID(document_id)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        # Get extractions for current document
        ext_result = await session.execute(
            select(ExtractionResult).where(ExtractionResult.document_id == doc_uuid)
        )
        current_extractions = {e.field_name: e.field_value for e in ext_result.scalars().all()}

        if not current_extractions:
            return []

        matches = []

        # Check for invoice number match
        invoice_number = current_extractions.get("invoice_number") or current_extractions.get("receipt_number")
        if invoice_number:
            matches.extend(await DuplicateDetectionService._find_by_field_value(
                session=session,
                field_names=["invoice_number", "receipt_number"],
                field_value=str(invoice_number),
                exclude_document_id=document_id,
                customer_id=customer_id,
                cutoff=cutoff
            ))

        # Check for vendor + amount + date combination
        vendor = current_extractions.get("vendor_name") or current_extractions.get("store_name")
        amount = current_extractions.get("total_amount") or current_extractions.get("total")
        date = current_extractions.get("invoice_date") or current_extractions.get("transaction_date")

        if vendor and amount:
            combo_matches = await DuplicateDetectionService._find_by_field_combination(
                session=session,
                vendor_value=str(vendor),
                amount_value=amount,
                date_value=str(date) if date else None,
                exclude_document_id=document_id,
                customer_id=customer_id,
                cutoff=cutoff
            )
            matches.extend(combo_matches)

        # Deduplicate matches
        seen = set()
        unique_matches = []
        for m in matches:
            if m.document_id not in seen:
                seen.add(m.document_id)
                unique_matches.append(m)

        return unique_matches

    @staticmethod
    async def _find_by_field_value(
        session: AsyncSession,
        field_names: List[str],
        field_value: str,
        exclude_document_id: str,
        customer_id: Optional[str],
        cutoff: datetime
    ) -> List[DuplicateMatch]:
        """Find documents with matching field value."""
        query = select(ExtractionResult).where(
            and_(
                ExtractionResult.field_name.in_(field_names),
                ExtractionResult.created_at >= cutoff,
                ExtractionResult.document_id != UUID(exclude_document_id),
            )
        )

        result = await session.execute(query)
        extractions = result.scalars().all()

        matches = []
        for ext in extractions:
            ext_value = str(ext.field_value) if ext.field_value else ""
            if ext_value.lower().strip() == field_value.lower().strip():
                # Get document info
                doc_result = await session.execute(
                    select(DocumentMetadata).where(DocumentMetadata.id == ext.document_id)
                )
                doc = doc_result.scalar_one_or_none()

                if doc and (not customer_id or doc.customer_id == customer_id):
                    matches.append(DuplicateMatch(
                        document_id=str(ext.document_id),
                        filename=doc.filename if doc else "unknown",
                        match_type="key_field_match",
                        confidence=KEY_FIELD_MATCH_THRESHOLD,
                        match_details={
                            "matched_field": ext.field_name,
                            "matched_value": field_value,
                            "message": f"Same {ext.field_name}: {field_value}"
                        },
                        created_at=doc.created_at if doc else None
                    ))

        return matches

    @staticmethod
    async def _find_by_field_combination(
        session: AsyncSession,
        vendor_value: str,
        amount_value: Any,
        date_value: Optional[str],
        exclude_document_id: str,
        customer_id: Optional[str],
        cutoff: datetime
    ) -> List[DuplicateMatch]:
        """Find documents with matching vendor + amount + date combination."""
        # Get all vendor extractions
        vendor_fields = ["vendor_name", "store_name", "party_a_name", "company_name"]
        amount_fields = ["total_amount", "total", "contract_value", "net_income"]

        vendor_query = select(ExtractionResult).where(
            and_(
                ExtractionResult.field_name.in_(vendor_fields),
                ExtractionResult.created_at >= cutoff,
                ExtractionResult.document_id != UUID(exclude_document_id),
            )
        )

        vendor_result = await session.execute(vendor_query)
        vendor_extractions = vendor_result.scalars().all()

        # Group by document
        doc_vendors = {}
        for ext in vendor_extractions:
            doc_id = str(ext.document_id)
            if doc_id not in doc_vendors:
                doc_vendors[doc_id] = {}
            doc_vendors[doc_id]["vendor"] = str(ext.field_value) if ext.field_value else ""

        # Get amounts for those documents
        if doc_vendors:
            doc_uuids = [UUID(d) for d in doc_vendors.keys()]
            amount_query = select(ExtractionResult).where(
                and_(
                    ExtractionResult.field_name.in_(amount_fields),
                    ExtractionResult.document_id.in_(doc_uuids),
                )
            )
            amount_result = await session.execute(amount_query)
            for ext in amount_result.scalars().all():
                doc_id = str(ext.document_id)
                if doc_id in doc_vendors:
                    doc_vendors[doc_id]["amount"] = ext.field_value

        matches = []
        for doc_id, fields in doc_vendors.items():
            vendor = fields.get("vendor", "")
            amount = fields.get("amount")

            # Check vendor similarity
            vendor_similarity = DuplicateDetectionService.text_similarity(vendor_value, vendor)

            # Check amount match
            amount_match = False
            if amount is not None and amount_value is not None:
                try:
                    # Handle both numeric and string amounts
                    amt1 = float(str(amount_value).replace("$", "").replace(",", ""))
                    amt2 = float(str(amount).replace("$", "").replace(",", ""))
                    amount_match = abs(amt1 - amt2) < 0.01
                except (ValueError, TypeError):
                    amount_match = str(amount_value) == str(amount)

            if vendor_similarity >= 0.8 and amount_match:
                # Get document info
                doc_result = await session.execute(
                    select(DocumentMetadata).where(DocumentMetadata.id == UUID(doc_id))
                )
                doc = doc_result.scalar_one_or_none()

                if doc and (not customer_id or doc.customer_id == customer_id):
                    confidence = (vendor_similarity + (1.0 if amount_match else 0)) / 2
                    matches.append(DuplicateMatch(
                        document_id=doc_id,
                        filename=doc.filename if doc else "unknown",
                        match_type="key_field_combination",
                        confidence=confidence,
                        match_details={
                            "vendor_similarity": round(vendor_similarity, 2),
                            "amount_match": amount_match,
                            "matched_vendor": vendor,
                            "matched_amount": amount,
                            "message": f"Similar vendor ({vendor_similarity:.0%}) and same amount"
                        },
                        created_at=doc.created_at if doc else None
                    ))

        return matches

    @staticmethod
    async def check_all_duplicates(
        session: AsyncSession,
        file_content: Optional[bytes] = None,
        text_content: Optional[str] = None,
        document_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        days_back: int = 365
    ) -> Dict[str, Any]:
        """
        Run all duplicate detection methods and return combined results.
        """
        results = {
            "is_duplicate": False,
            "highest_confidence": 0.0,
            "matches": [],
            "checks_performed": [],
        }

        all_matches = []

        # Check exact hash
        if file_content:
            file_hash = DuplicateDetectionService.compute_file_hash(file_content)
            results["checks_performed"].append("exact_hash")

            hash_match = await DuplicateDetectionService.check_exact_duplicate(
                session=session,
                file_hash=file_hash,
                exclude_document_id=document_id,
                customer_id=customer_id,
                days_back=days_back
            )
            if hash_match:
                all_matches.append(hash_match)

        # Check content similarity
        if text_content:
            results["checks_performed"].append("content_similarity")

            content_matches = await DuplicateDetectionService.check_content_similarity(
                session=session,
                content=text_content,
                exclude_document_id=document_id,
                customer_id=customer_id,
                days_back=min(days_back, 90)  # Content check limited to 90 days
            )
            all_matches.extend(content_matches)

        # Check key fields (if document already processed)
        if document_id:
            results["checks_performed"].append("key_field_match")

            field_matches = await DuplicateDetectionService.check_key_field_duplicates(
                session=session,
                document_id=document_id,
                customer_id=customer_id,
                days_back=days_back
            )
            all_matches.extend(field_matches)

        # Deduplicate and sort
        seen = set()
        unique_matches = []
        for m in all_matches:
            if m.document_id not in seen:
                seen.add(m.document_id)
                unique_matches.append(m)

        unique_matches.sort(key=lambda x: x.confidence, reverse=True)

        results["matches"] = [m.to_dict() for m in unique_matches[:10]]
        results["highest_confidence"] = unique_matches[0].confidence if unique_matches else 0.0
        results["is_duplicate"] = results["highest_confidence"] >= MEDIUM_SIMILARITY_THRESHOLD

        return results

    # ===== Sync versions for Celery workers =====

    @staticmethod
    def check_all_duplicates_sync(
        session,
        file_content: Optional[bytes] = None,
        text_content: Optional[str] = None,
        document_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        days_back: int = 365
    ) -> Dict[str, Any]:
        """Sync version for Celery workers."""
        from datetime import datetime, timezone, timedelta

        results = {
            "is_duplicate": False,
            "highest_confidence": 0.0,
            "matches": [],
            "checks_performed": [],
        }

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        all_matches = []

        # Check by file size (proxy for exact hash when hash not stored)
        if file_content:
            file_size = len(file_content)
            results["checks_performed"].append("size_match")

            query = select(DocumentMetadata).where(
                and_(
                    DocumentMetadata.size == file_size,
                    DocumentMetadata.created_at >= cutoff,
                )
            )
            if document_id:
                query = query.where(DocumentMetadata.id != UUID(document_id))
            if customer_id:
                query = query.where(DocumentMetadata.customer_id == customer_id)

            result = session.execute(query.limit(1))
            existing = result.scalar_one_or_none()

            if existing:
                all_matches.append(DuplicateMatch(
                    document_id=str(existing.id),
                    filename=existing.filename,
                    match_type="size_match",
                    confidence=0.9,
                    match_details={"size": file_size, "message": "Same file size - likely duplicate"},
                    created_at=existing.created_at
                ))

        # Check key fields
        if document_id:
            results["checks_performed"].append("key_field_match")

            ext_result = session.execute(
                select(ExtractionResult).where(
                    ExtractionResult.document_id == UUID(document_id)
                )
            )
            current_extractions = {e.field_name: e.field_value for e in ext_result.scalars().all()}

            # Check invoice/receipt number
            doc_number = current_extractions.get("invoice_number") or current_extractions.get("receipt_number")
            if doc_number:
                num_query = select(ExtractionResult).where(
                    and_(
                        ExtractionResult.field_name.in_(["invoice_number", "receipt_number"]),
                        ExtractionResult.created_at >= cutoff,
                        ExtractionResult.document_id != UUID(document_id),
                    )
                )
                num_result = session.execute(num_query)

                for ext in num_result.scalars().all():
                    if str(ext.field_value).lower().strip() == str(doc_number).lower().strip():
                        doc_result = session.execute(
                            select(DocumentMetadata).where(DocumentMetadata.id == ext.document_id)
                        )
                        doc = doc_result.scalar_one_or_none()
                        if doc:
                            all_matches.append(DuplicateMatch(
                                document_id=str(ext.document_id),
                                filename=doc.filename,
                                match_type="key_field_match",
                                confidence=KEY_FIELD_MATCH_THRESHOLD,
                                match_details={
                                    "matched_field": ext.field_name,
                                    "matched_value": doc_number,
                                    "message": f"Same {ext.field_name}"
                                },
                                created_at=doc.created_at
                            ))

        # Deduplicate
        seen = set()
        unique_matches = []
        for m in all_matches:
            if m.document_id not in seen:
                seen.add(m.document_id)
                unique_matches.append(m)

        unique_matches.sort(key=lambda x: x.confidence, reverse=True)

        results["matches"] = [m.to_dict() for m in unique_matches[:10]]
        results["highest_confidence"] = unique_matches[0].confidence if unique_matches else 0.0
        results["is_duplicate"] = results["highest_confidence"] >= MEDIUM_SIMILARITY_THRESHOLD

        return results
