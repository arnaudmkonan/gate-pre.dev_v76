"""
Post-Extraction Compliance Service.

Orchestrates compliance checks after document template extraction:
- HTS code validation
- OFAC SDN party screening
- NAICS code classification

This service integrates extracted data with reference data to provide
automated compliance validation and risk flagging.
"""

import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reference_data import OFACSdn, HTSCode, NAICSCode, ComplianceScreen
from app.models.document_metadata import DocumentMetadata
from app.services.reference_data_service import ReferenceDataService

logger = logging.getLogger(__name__)


class ComplianceCheckType(str, Enum):
    """Types of compliance checks performed."""
    HTS_VALIDATION = "hts_validation"
    OFAC_SCREENING = "ofac_screening"
    NAICS_CLASSIFICATION = "naics_classification"


class RiskLevel(str, Enum):
    """Risk levels from compliance checks."""
    CLEAR = "clear"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HTSValidationResult:
    """Result of HTS code validation."""
    hts_code: str
    is_valid: bool
    found_in_database: bool
    description: Optional[str] = None
    duty_rate: Optional[str] = None
    duty_rate_percent: Optional[float] = None
    chapter: Optional[int] = None
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hts_code": self.hts_code,
            "is_valid": self.is_valid,
            "found_in_database": self.found_in_database,
            "description": self.description,
            "duty_rate": self.duty_rate,
            "duty_rate_percent": self.duty_rate_percent,
            "chapter": self.chapter,
            "suggestions": self.suggestions,
            "error": self.error,
        }


@dataclass
class PartyScreeningResult:
    """Result of OFAC party screening."""
    party_name: str
    party_type: str  # seller, buyer, importer, consignee, manufacturer
    risk_level: RiskLevel
    matches_found: int
    matches: List[Dict[str, Any]] = field(default_factory=list)
    screened_at: Optional[datetime] = None
    compliance_screen_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "party_name": self.party_name,
            "party_type": self.party_type,
            "risk_level": self.risk_level.value,
            "matches_found": self.matches_found,
            "matches": self.matches,
            "screened_at": self.screened_at.isoformat() if self.screened_at else None,
            "compliance_screen_id": self.compliance_screen_id,
        }


@dataclass
class NAICSClassificationResult:
    """Result of NAICS classification."""
    suggested_codes: List[Dict[str, Any]]
    confidence: float
    based_on: str  # What data was used for classification

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggested_codes": self.suggested_codes,
            "confidence": self.confidence,
            "based_on": self.based_on,
        }


@dataclass
class PostExtractionResult:
    """Complete result of post-extraction compliance checks."""
    document_id: str
    template_name: Optional[str]
    hts_validations: List[HTSValidationResult] = field(default_factory=list)
    party_screenings: List[PartyScreeningResult] = field(default_factory=list)
    naics_classifications: List[NAICSClassificationResult] = field(default_factory=list)
    overall_risk_level: RiskLevel = RiskLevel.CLEAR
    issues_found: List[Dict[str, Any]] = field(default_factory=list)
    processed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "template_name": self.template_name,
            "hts_validations": [v.to_dict() for v in self.hts_validations],
            "party_screenings": [s.to_dict() for s in self.party_screenings],
            "naics_classifications": [c.to_dict() for c in self.naics_classifications],
            "overall_risk_level": self.overall_risk_level.value,
            "issues_found": self.issues_found,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


class PostExtractionService:
    """
    Service for running compliance checks after document extraction.

    Orchestrates:
    - HTS code validation against reference data
    - OFAC SDN screening for extracted parties
    - NAICS code suggestions based on product/company data
    """

    # Party field names to look for in template extractions
    PARTY_FIELDS = {
        "seller_name": "seller",
        "seller": "seller",
        "exporter_name": "seller",
        "exporter": "seller",
        "shipper_name": "seller",
        "shipper": "seller",
        "buyer_name": "buyer",
        "buyer": "buyer",
        "importer_name": "importer",
        "importer": "importer",
        "importer_of_record_name": "importer",
        "importer_of_record": "importer",
        "consignee_name": "consignee",
        "consignee": "consignee",
        "ultimate_consignee": "consignee",
        "manufacturer_name": "manufacturer",
        "manufacturer": "manufacturer",
        "vendor_name": "vendor",
        "vendor": "vendor",
    }

    # HTS code field names to look for
    HTS_FIELDS = ["hts_code", "hs_code", "hts_number", "tariff_code", "hts"]

    def __init__(self, db: AsyncSession):
        self.db = db
        self.reference_service = ReferenceDataService(db)

    async def process_extraction_results(
        self,
        document_id: str,
        extraction_results: Dict[str, Any],
        template_name: Optional[str] = None,
        shipment_id: Optional[UUID] = None,
    ) -> PostExtractionResult:
        """
        Process template extraction results and run all compliance checks.

        Args:
            document_id: ID of the document
            extraction_results: Results from template extraction (extractions list)
            template_name: Name of the template used
            shipment_id: Optional shipment ID for linking compliance screens

        Returns:
            PostExtractionResult with all check results
        """
        result = PostExtractionResult(
            document_id=document_id,
            template_name=template_name,
            processed_at=datetime.now(timezone.utc),
        )

        try:
            # Extract data from template results
            extractions = extraction_results.get("extractions", [])
            extraction_map = self._build_extraction_map(extractions)

            # 1. Validate HTS codes
            hts_codes = self._extract_hts_codes(extractions)
            for hts_code in hts_codes:
                validation = await self.validate_hts_code(hts_code)
                result.hts_validations.append(validation)
                if not validation.is_valid:
                    result.issues_found.append({
                        "type": "invalid_hts",
                        "severity": "medium",
                        "description": f"HTS code '{hts_code}' not found in database",
                        "field": "hts_code",
                        "value": hts_code,
                        "suggestions": validation.suggestions,
                    })

            # 2. Screen parties against OFAC
            parties = self._extract_parties(extraction_map)
            for party_name, party_type in parties:
                screening = await self.screen_party(
                    party_name=party_name,
                    party_type=party_type,
                    document_id=document_id,
                    shipment_id=shipment_id,
                )
                result.party_screenings.append(screening)
                if screening.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    result.issues_found.append({
                        "type": "ofac_match",
                        "severity": "critical" if screening.risk_level == RiskLevel.CRITICAL else "high",
                        "description": f"OFAC screening found {screening.matches_found} potential matches for '{party_name}'",
                        "field": f"{party_type}_name",
                        "value": party_name,
                        "matches": screening.matches[:3],  # Top 3 matches
                    })

            # 3. Suggest NAICS codes based on products/items
            product_descriptions = self._extract_product_descriptions(extractions)
            if product_descriptions:
                naics_result = await self.classify_naics(product_descriptions)
                result.naics_classifications.append(naics_result)

            # Calculate overall risk level
            result.overall_risk_level = self._calculate_overall_risk(result)

            logger.info(
                f"Post-extraction compliance check completed for document {document_id}: "
                f"HTS={len(result.hts_validations)}, Parties={len(result.party_screenings)}, "
                f"Risk={result.overall_risk_level.value}"
            )

        except Exception as e:
            logger.error(f"Post-extraction processing failed for {document_id}: {e}")
            result.issues_found.append({
                "type": "processing_error",
                "severity": "high",
                "description": f"Compliance check failed: {str(e)}",
            })

        return result

    async def validate_hts_code(self, hts_code: str) -> HTSValidationResult:
        """
        Validate an HTS code against the database.

        Args:
            hts_code: HTS code to validate (e.g., "8471.30.01")

        Returns:
            HTSValidationResult with validation details
        """
        # Normalize the code
        normalized = self._normalize_hts_code(hts_code)

        if not self._is_valid_hts_format(normalized):
            return HTSValidationResult(
                hts_code=hts_code,
                is_valid=False,
                found_in_database=False,
                error=f"Invalid HTS code format: {hts_code}",
            )

        # Look up in database
        hts_data = await self.reference_service.get_hts_code(normalized)

        if hts_data:
            return HTSValidationResult(
                hts_code=hts_code,
                is_valid=True,
                found_in_database=True,
                description=hts_data.get("description"),
                duty_rate=hts_data.get("duty_rate"),
                duty_rate_percent=hts_data.get("duty_rate_percent"),
                chapter=hts_data.get("chapter"),
            )

        # Not found - try to find suggestions
        suggestions = await self._get_hts_suggestions(normalized)

        return HTSValidationResult(
            hts_code=hts_code,
            is_valid=False,
            found_in_database=False,
            suggestions=suggestions,
        )

    async def screen_party(
        self,
        party_name: str,
        party_type: str,
        document_id: Optional[str] = None,
        shipment_id: Optional[UUID] = None,
        threshold: float = 0.80,
    ) -> PartyScreeningResult:
        """
        Screen a party against the OFAC SDN list.

        Args:
            party_name: Name of the party to screen
            party_type: Type of party (seller, buyer, importer, etc.)
            document_id: Optional document ID for reference
            shipment_id: Optional shipment ID for linking
            threshold: Minimum score for matches (0-1)

        Returns:
            PartyScreeningResult with screening details
        """
        # Clean the party name
        clean_name = self._clean_party_name(party_name)

        if not clean_name or len(clean_name) < 2:
            return PartyScreeningResult(
                party_name=party_name,
                party_type=party_type,
                risk_level=RiskLevel.CLEAR,
                matches_found=0,
                screened_at=datetime.now(timezone.utc),
            )

        # Run screening
        screening_result = await self.reference_service.screen_entity(
            name=clean_name,
            threshold=threshold,
        )

        # Determine risk level
        risk_level = self._determine_risk_level(screening_result)

        # Create compliance screen record if matches found
        compliance_screen_id = None
        if screening_result.get("matches"):
            screen = await self.reference_service.record_screen(
                screen_type="ofac",
                result=screening_result,
                shipment_id=shipment_id,
            )
            compliance_screen_id = str(screen.id)

        return PartyScreeningResult(
            party_name=party_name,
            party_type=party_type,
            risk_level=risk_level,
            matches_found=screening_result.get("matches_found", 0),
            matches=screening_result.get("matches", []),
            screened_at=datetime.now(timezone.utc),
            compliance_screen_id=compliance_screen_id,
        )

    async def classify_naics(
        self,
        product_descriptions: List[str],
        limit: int = 5,
    ) -> NAICSClassificationResult:
        """
        Suggest NAICS codes based on product descriptions.

        Args:
            product_descriptions: List of product/item descriptions
            limit: Maximum number of suggestions

        Returns:
            NAICSClassificationResult with suggested codes
        """
        # Combine descriptions for search
        combined_text = " ".join(product_descriptions[:10])  # Limit to first 10

        # Extract key terms for searching
        search_terms = self._extract_search_terms(combined_text)

        suggested_codes = []
        seen_codes = set()

        for term in search_terms[:5]:  # Search with top 5 terms
            results = await self.reference_service.search_naics_codes(
                query=term,
                limit=3,
            )
            for result in results:
                code = result.get("naics_code")
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    suggested_codes.append({
                        "naics_code": code,
                        "title": result.get("title"),
                        "sector": result.get("sector"),
                        "matched_term": term,
                    })

        # Calculate confidence based on number of matches
        confidence = min(0.9, len(suggested_codes) * 0.15) if suggested_codes else 0.0

        return NAICSClassificationResult(
            suggested_codes=suggested_codes[:limit],
            confidence=confidence,
            based_on=f"Product descriptions ({len(product_descriptions)} items)",
        )

    # ==================== Helper Methods ====================

    def _build_extraction_map(self, extractions: List[Dict]) -> Dict[str, Any]:
        """Build a map of field_name -> value from extractions."""
        result = {}
        for ext in extractions:
            field_name = ext.get("field_name", "").lower()
            if ext.get("found", True) and ext.get("value") is not None:
                result[field_name] = ext.get("value")
        return result

    def _extract_hts_codes(self, extractions: List[Dict]) -> List[str]:
        """Extract all HTS codes from extraction results."""
        hts_codes = []

        for ext in extractions:
            field_name = ext.get("field_name", "").lower()
            value = ext.get("value")

            if not value or not ext.get("found", True):
                continue

            # Check if this is an HTS field
            if any(hts_field in field_name for hts_field in self.HTS_FIELDS):
                if isinstance(value, str):
                    hts_codes.append(value)
                elif isinstance(value, list):
                    hts_codes.extend([v for v in value if isinstance(v, str)])

            # Check nested line items
            if field_name == "line_items" and isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        for hts_field in self.HTS_FIELDS:
                            if hts_field in item and item[hts_field]:
                                hts_codes.append(str(item[hts_field]))

        # Deduplicate while preserving order
        seen = set()
        unique_codes = []
        for code in hts_codes:
            if code not in seen:
                seen.add(code)
                unique_codes.append(code)

        return unique_codes

    def _extract_parties(self, extraction_map: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Extract party names and types from extraction map."""
        parties = []

        for field_name, party_type in self.PARTY_FIELDS.items():
            value = extraction_map.get(field_name)
            if value and isinstance(value, str) and len(value.strip()) > 1:
                parties.append((value.strip(), party_type))

        return parties

    def _extract_product_descriptions(self, extractions: List[Dict]) -> List[str]:
        """Extract product descriptions from extraction results."""
        descriptions = []

        for ext in extractions:
            field_name = ext.get("field_name", "").lower()
            value = ext.get("value")

            if not value or not ext.get("found", True):
                continue

            # Check for description fields
            if any(term in field_name for term in ["description", "item", "product", "goods"]):
                if isinstance(value, str):
                    descriptions.append(value)

            # Check nested line items
            if field_name == "line_items" and isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        desc = item.get("description") or item.get("item_description")
                        if desc:
                            descriptions.append(str(desc))

        return descriptions

    def _normalize_hts_code(self, code: str) -> str:
        """Normalize HTS code by removing non-alphanumeric characters."""
        return re.sub(r'[^0-9]', '', code)

    def _is_valid_hts_format(self, normalized_code: str) -> bool:
        """Check if the normalized code has a valid HTS format (4-10 digits)."""
        return len(normalized_code) >= 4 and len(normalized_code) <= 10 and normalized_code.isdigit()

    async def _get_hts_suggestions(self, normalized_code: str) -> List[Dict[str, Any]]:
        """Get HTS code suggestions based on partial code."""
        # Try prefix matching with first 4-6 digits
        prefix = normalized_code[:4] if len(normalized_code) >= 4 else normalized_code

        suggestions = await self.reference_service.search_hts_codes(
            query=prefix,
            limit=5,
        )

        return suggestions

    def _clean_party_name(self, name: str) -> str:
        """Clean party name for screening."""
        if not name:
            return ""
        # Remove common suffixes and clean
        cleaned = name.strip()
        # Remove common company suffixes for better matching
        suffixes = [" LLC", " Inc.", " Inc", " Corp.", " Corp", " Ltd.", " Ltd", " Co.", " Co"]
        for suffix in suffixes:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)]
        return cleaned.strip()

    def _determine_risk_level(self, screening_result: Dict[str, Any]) -> RiskLevel:
        """Determine risk level from OFAC screening result."""
        risk_str = screening_result.get("risk_level", "clear")

        if risk_str == "confirmed_match":
            return RiskLevel.CRITICAL
        elif risk_str == "possible_match":
            # Check match scores
            matches = screening_result.get("matches", [])
            if matches:
                top_score = matches[0].get("score", 0)
                if top_score >= 0.95:
                    return RiskLevel.HIGH
                elif top_score >= 0.85:
                    return RiskLevel.MEDIUM
                else:
                    return RiskLevel.LOW
            return RiskLevel.LOW

        return RiskLevel.CLEAR

    def _extract_search_terms(self, text: str) -> List[str]:
        """Extract key search terms from text for NAICS classification."""
        # Simple term extraction - could be enhanced with NLP
        words = text.lower().split()
        # Filter out common words and short words
        stop_words = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "from"}
        terms = [w for w in words if len(w) > 3 and w not in stop_words]
        # Return unique terms
        return list(dict.fromkeys(terms))[:10]

    def _calculate_overall_risk(self, result: PostExtractionResult) -> RiskLevel:
        """Calculate overall risk level from all checks."""
        max_risk = RiskLevel.CLEAR

        # Check party screenings
        for screening in result.party_screenings:
            if screening.risk_level.value > max_risk.value:
                max_risk = screening.risk_level

        # Check HTS validations (invalid codes increase risk)
        invalid_hts_count = sum(1 for v in result.hts_validations if not v.is_valid)
        if invalid_hts_count > 0 and max_risk == RiskLevel.CLEAR:
            max_risk = RiskLevel.LOW

        return max_risk


# ==================== Sync versions for Celery workers ====================

class PostExtractionServiceSync:
    """
    Synchronous version of PostExtractionService for Celery workers.
    """

    PARTY_FIELDS = PostExtractionService.PARTY_FIELDS
    HTS_FIELDS = PostExtractionService.HTS_FIELDS

    def __init__(self, db):
        self.db = db

    def process_extraction_results(
        self,
        document_id: str,
        extraction_results: Dict[str, Any],
        template_name: Optional[str] = None,
        shipment_id: Optional[UUID] = None,
    ) -> PostExtractionResult:
        """Synchronous version of process_extraction_results."""
        from difflib import SequenceMatcher

        result = PostExtractionResult(
            document_id=document_id,
            template_name=template_name,
            processed_at=datetime.now(timezone.utc),
        )

        try:
            extractions = extraction_results.get("extractions", [])
            extraction_map = self._build_extraction_map(extractions)

            # 1. Validate HTS codes
            hts_codes = self._extract_hts_codes(extractions)
            for hts_code in hts_codes:
                validation = self._validate_hts_code_sync(hts_code)
                result.hts_validations.append(validation)
                if not validation.is_valid:
                    result.issues_found.append({
                        "type": "invalid_hts",
                        "severity": "medium",
                        "description": f"HTS code '{hts_code}' not found in database",
                        "field": "hts_code",
                        "value": hts_code,
                        "suggestions": validation.suggestions,
                    })

            # 2. Screen parties against OFAC
            parties = self._extract_parties(extraction_map)
            for party_name, party_type in parties:
                screening = self._screen_party_sync(
                    party_name=party_name,
                    party_type=party_type,
                    document_id=document_id,
                    shipment_id=shipment_id,
                )
                result.party_screenings.append(screening)
                if screening.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    result.issues_found.append({
                        "type": "ofac_match",
                        "severity": "critical" if screening.risk_level == RiskLevel.CRITICAL else "high",
                        "description": f"OFAC screening found {screening.matches_found} potential matches for '{party_name}'",
                        "field": f"{party_type}_name",
                        "value": party_name,
                        "matches": screening.matches[:3],
                    })

            # 3. Suggest NAICS codes
            product_descriptions = self._extract_product_descriptions(extractions)
            if product_descriptions:
                naics_result = self._classify_naics_sync(product_descriptions)
                result.naics_classifications.append(naics_result)

            result.overall_risk_level = self._calculate_overall_risk(result)

            logger.info(
                f"Post-extraction compliance check completed for document {document_id}: "
                f"HTS={len(result.hts_validations)}, Parties={len(result.party_screenings)}, "
                f"Risk={result.overall_risk_level.value}"
            )

        except Exception as e:
            logger.error(f"Post-extraction processing failed for {document_id}: {e}")
            result.issues_found.append({
                "type": "processing_error",
                "severity": "high",
                "description": f"Compliance check failed: {str(e)}",
            })

        return result

    def _validate_hts_code_sync(self, hts_code: str) -> HTSValidationResult:
        """Validate HTS code synchronously."""
        normalized = re.sub(r'[^0-9]', '', hts_code)

        if not (len(normalized) >= 4 and len(normalized) <= 10 and normalized.isdigit()):
            return HTSValidationResult(
                hts_code=hts_code,
                is_valid=False,
                found_in_database=False,
                error=f"Invalid HTS code format: {hts_code}",
            )

        # Look up in database
        stmt = select(HTSCode).where(
            func.replace(HTSCode.hts_code, ".", "") == normalized
        )
        db_result = self.db.execute(stmt)
        code = db_result.scalar_one_or_none()

        if code:
            return HTSValidationResult(
                hts_code=hts_code,
                is_valid=True,
                found_in_database=True,
                description=code.description,
                duty_rate=code.duty_rate,
                duty_rate_percent=float(code.duty_rate_percent) if code.duty_rate_percent else None,
                chapter=code.chapter,
            )

        # Get suggestions
        prefix = normalized[:4] if len(normalized) >= 4 else normalized
        suggest_stmt = select(HTSCode).where(
            HTSCode.hts_code.ilike(f"{prefix}%")
        ).limit(5)
        suggest_result = self.db.execute(suggest_stmt)
        suggestions = [
            {
                "hts_code": c.hts_code,
                "description": c.description,
                "duty_rate": c.duty_rate,
            }
            for c in suggest_result.scalars().all()
        ]

        return HTSValidationResult(
            hts_code=hts_code,
            is_valid=False,
            found_in_database=False,
            suggestions=suggestions,
        )

    def _screen_party_sync(
        self,
        party_name: str,
        party_type: str,
        document_id: Optional[str] = None,
        shipment_id: Optional[UUID] = None,
        threshold: float = 0.80,
    ) -> PartyScreeningResult:
        """Screen party against OFAC synchronously."""
        from difflib import SequenceMatcher

        clean_name = party_name.strip()
        suffixes = [" LLC", " Inc.", " Inc", " Corp.", " Corp", " Ltd.", " Ltd", " Co.", " Co"]
        for suffix in suffixes:
            if clean_name.endswith(suffix):
                clean_name = clean_name[:-len(suffix)]
        clean_name = clean_name.strip()

        if not clean_name or len(clean_name) < 2:
            return PartyScreeningResult(
                party_name=party_name,
                party_type=party_type,
                risk_level=RiskLevel.CLEAR,
                matches_found=0,
                screened_at=datetime.now(timezone.utc),
            )

        # Search OFAC
        name_normalized = clean_name.upper()
        prefix = name_normalized[:3] if len(name_normalized) >= 3 else name_normalized

        stmt = select(OFACSdn).where(
            or_(
                func.upper(OFACSdn.sdn_name).like(f"{prefix}%"),
                OFACSdn.aliases.cast(str).ilike(f"%{prefix}%"),
            )
        ).limit(100)

        db_result = self.db.execute(stmt)
        candidates = db_result.scalars().all()

        matches = []
        for sdn in candidates:
            score = SequenceMatcher(None, name_normalized, sdn.sdn_name.upper()).ratio()

            # Check aliases
            alias_scores = []
            for alias in (sdn.aliases or []):
                alias_score = SequenceMatcher(None, name_normalized, alias.upper()).ratio()
                alias_scores.append(alias_score)

            best_alias_score = max(alias_scores) if alias_scores else 0
            best_score = max(score, best_alias_score)

            if best_score >= threshold:
                matches.append({
                    "sdn_id": str(sdn.id),
                    "name": sdn.sdn_name,
                    "type": sdn.sdn_type,
                    "program": sdn.program,
                    "score": round(best_score, 3),
                })

        matches.sort(key=lambda x: x["score"], reverse=True)

        # Determine risk
        if any(m["score"] >= 0.98 for m in matches):
            risk_level = RiskLevel.CRITICAL
        elif any(m["score"] >= 0.95 for m in matches):
            risk_level = RiskLevel.HIGH
        elif any(m["score"] >= 0.85 for m in matches):
            risk_level = RiskLevel.MEDIUM
        elif matches:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.CLEAR

        # Record compliance screen if matches found
        compliance_screen_id = None
        if matches:
            screen = ComplianceScreen(
                shipment_id=shipment_id,
                screen_type="ofac",
                result={
                    "screened_name": party_name,
                    "party_type": party_type,
                    "matches_found": len(matches),
                },
                risk_level=risk_level.value,
                matches=matches[:10],
            )
            self.db.add(screen)
            self.db.commit()
            self.db.refresh(screen)
            compliance_screen_id = str(screen.id)

        return PartyScreeningResult(
            party_name=party_name,
            party_type=party_type,
            risk_level=risk_level,
            matches_found=len(matches),
            matches=matches[:10],
            screened_at=datetime.now(timezone.utc),
            compliance_screen_id=compliance_screen_id,
        )

    def _classify_naics_sync(
        self,
        product_descriptions: List[str],
        limit: int = 5,
    ) -> NAICSClassificationResult:
        """Classify NAICS codes synchronously."""
        combined_text = " ".join(product_descriptions[:10])
        words = combined_text.lower().split()
        stop_words = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "from"}
        terms = [w for w in words if len(w) > 3 and w not in stop_words]
        terms = list(dict.fromkeys(terms))[:10]

        suggested_codes = []
        seen_codes = set()

        for term in terms[:5]:
            stmt = select(NAICSCode).where(
                or_(
                    NAICSCode.naics_code.like(f"{term}%"),
                    NAICSCode.title.ilike(f"%{term}%"),
                    NAICSCode.description.ilike(f"%{term}%"),
                )
            ).limit(3)

            db_result = self.db.execute(stmt)
            for code in db_result.scalars().all():
                if code.naics_code not in seen_codes:
                    seen_codes.add(code.naics_code)
                    suggested_codes.append({
                        "naics_code": code.naics_code,
                        "title": code.title,
                        "sector": code.sector,
                        "matched_term": term,
                    })

        confidence = min(0.9, len(suggested_codes) * 0.15) if suggested_codes else 0.0

        return NAICSClassificationResult(
            suggested_codes=suggested_codes[:limit],
            confidence=confidence,
            based_on=f"Product descriptions ({len(product_descriptions)} items)",
        )

    # Reuse helper methods from async version
    _build_extraction_map = PostExtractionService._build_extraction_map
    _extract_hts_codes = PostExtractionService._extract_hts_codes
    _extract_parties = PostExtractionService._extract_parties
    _extract_product_descriptions = PostExtractionService._extract_product_descriptions
    _calculate_overall_risk = PostExtractionService._calculate_overall_risk
