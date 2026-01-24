"""
Key Extractor Service - Extracts linking identifiers from document content.

Uses regex patterns for standard formats and LLM for complex extraction.
Extracted keys are used by the Auto-Linker to group documents into shipments.
"""
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_key import DocumentKey, KeyType, ExtractionMethod, KEY_PRIORITY

logger = logging.getLogger(__name__)


# ============================================================================
# REGEX PATTERNS FOR KEY EXTRACTION
# ============================================================================

KEY_PATTERNS: Dict[KeyType, List[str]] = {
    KeyType.ENTRY_NUM: [
        r'\b(\d{3}[-\s]?\d{7}[-\s]?\d{1})\b',  # Standard: 123-4567890-1
        r'Entry\s*(?:#|No\.?|Number)?[:.\s]*(\d{11,12})',
        r'Entry\s*(?:#|No\.?)?\s*[:.\s]*(\d{3}[-\s]?\d{7}[-\s]?\d)',
    ],
    KeyType.BOL_NUM: [
        r'\b([A-Z]{4}\d{7,12})\b',  # MAEU1234567890
        r'B/?L\s*(?:#|No\.?)?[:.\s]*([A-Z0-9]{10,})',
        r'Bill\s+of\s+Lading\s*(?:#|No\.?)?[:.\s]*([A-Z0-9]{8,})',
        r'Master\s+B/?L\s*(?:#|No\.?)?[:.\s]*([A-Z0-9]{8,})',
        r'House\s+B/?L\s*(?:#|No\.?)?[:.\s]*([A-Z0-9]{8,})',
    ],
    KeyType.AWB_NUM: [
        r'\b(\d{3}[-\s]?\d{8})\b',  # AWB format: 123-12345678
        r'AWB\s*(?:#|No\.?)?[:.\s]*(\d{3}[-\s]?\d{8})',
        r'Air\s*Waybill\s*(?:#|No\.?)?[:.\s]*([A-Z0-9]{10,})',
        r'MAWB\s*(?:#|No\.?)?[:.\s]*(\d{3}[-\s]?\d{8})',
        r'HAWB\s*(?:#|No\.?)?[:.\s]*([A-Z0-9]{8,})',
    ],
    KeyType.CONTAINER_NUM: [
        r'\b([A-Z]{4}\d{7})\b',  # MSDU1234567
        r'Container\s*(?:#|No\.?)?[:.\s]*([A-Z]{4}\d{7})',
    ],
    KeyType.PO_NUM: [
        # More specific patterns to avoid false positives
        r'(?:Purchase\s+Order|P\.?O\.?)\s*(?:#|No\.?|Number)?[:.\s]+([A-Z0-9][-A-Z0-9]{3,19})',
        r'\bPO[-#:\s]+(\d{4,20})\b',  # PO-12345 or PO#12345
    ],
    KeyType.INVOICE_NUM: [
        r'Invoice\s*(?:#|No\.?|Number)?[:.\s]*([A-Z0-9][-A-Z0-9]{3,30})',
        r'Inv\.?\s*(?:#|No\.?)?[:.\s]*([A-Z0-9][-A-Z0-9]{3,20})',
        r'Commercial\s+Invoice\s*(?:#|No\.?)?[:.\s]*([A-Z0-9][-A-Z0-9]{3,30})',
    ],
    KeyType.HTS_CODE: [
        r'\b(\d{4}\.\d{2}\.\d{2,4})\b',  # 8542.31.0000
        r'\b(\d{10})\b',  # 8542310000 (10 digits without dots)
        r'HTS(?:US)?\s*(?:#|No\.?)?[:.\s]*(\d{4}\.?\d{2}\.?\d{2,4})',
        r'Tariff\s*(?:#|No\.?)?[:.\s]*(\d{4}\.?\d{2}\.?\d{2,4})',
    ],
    KeyType.COUNTRY_ORIGIN: [
        r'Country\s+of\s+Origin[:.\s]*([A-Z]{2})\b',
        r'Origin[:.\s]*([A-Z]{2})\b',
        r'COO[:.\s]*([A-Z]{2})\b',
        r'Made\s+in[:.\s]*([A-Z]{2})\b',
    ],
}

# Words that should NOT be extracted as PO numbers (false positives)
PO_FALSE_POSITIVES = {'box', 'export', 'expo', 'port', 'position', 'postal', 'post', 'depot'}


class KeyExtractorService:
    """Service for extracting linking keys from document content."""
    
    def __init__(self, db: AsyncSession, llm_service=None):
        self.db = db
        self.llm_service = llm_service
        self.patterns = KEY_PATTERNS
        self.po_false_positives = PO_FALSE_POSITIVES
    
    async def extract_keys(
        self,
        document_id: UUID,
        text_content: str,
        parsed_data: Dict[str, Any] = None,
        use_llm: bool = False
    ) -> List[DocumentKey]:
        """
        Extract all linking keys from document content.
        
        Args:
            document_id: The document ID (raw_files.id)
            text_content: Raw text content from document
            parsed_data: Structured data from parsing (tables, fields)
            use_llm: Whether to use LLM for complex extraction
            
        Returns:
            List of DocumentKey objects (not yet persisted)
        """
        extracted_keys = []
        
        # Phase 1: Regex extraction (fast, reliable for standard formats)
        regex_keys = self._extract_with_regex(document_id, text_content)
        extracted_keys.extend(regex_keys)
        logger.info(f"Extracted {len(regex_keys)} keys via regex for doc {document_id}")
        
        # Phase 2: Extract from structured parsed data
        if parsed_data:
            structured_keys = self._extract_from_parsed(document_id, parsed_data)
            extracted_keys.extend(structured_keys)
            logger.info(f"Extracted {len(structured_keys)} keys from parsed data for doc {document_id}")
        
        # Phase 3: LLM extraction for complex/entity keys (if enabled and available)
        if use_llm and self.llm_service and text_content:
            llm_keys = await self._extract_with_llm(document_id, text_content)
            extracted_keys.extend(llm_keys)
            logger.info(f"Extracted {len(llm_keys)} keys via LLM for doc {document_id}")
        
        # Deduplicate keys
        unique_keys = self._deduplicate_keys(extracted_keys)
        logger.info(f"Total unique keys for doc {document_id}: {len(unique_keys)}")
        
        return unique_keys
    
    async def extract_and_save(
        self,
        document_id: UUID,
        text_content: str,
        parsed_data: Dict[str, Any] = None,
        use_llm: bool = False
    ) -> List[DocumentKey]:
        """
        Extract keys and save them to the database.
        
        Returns the saved DocumentKey objects.
        """
        keys = await self.extract_keys(document_id, text_content, parsed_data, use_llm)
        
        if keys:
            # Add all keys to session
            for key in keys:
                self.db.add(key)
            
            await self.db.commit()
            
            # Refresh to get IDs
            for key in keys:
                await self.db.refresh(key)
        
        return keys
    
    def _extract_with_regex(self, document_id: UUID, text: str) -> List[DocumentKey]:
        """Extract keys using regex patterns."""
        keys = []
        
        if not text:
            return keys
        
        for key_type, patterns in self.patterns.items():
            for pattern in patterns:
                try:
                    matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        value = match.group(1) if match.groups() else match.group(0)
                        value = self._clean_key_value(value)
                        
                        if value and self._validate_key_value(key_type, value):
                            # Get surrounding context
                            start = max(0, match.start() - 50)
                            end = min(len(text), match.end() + 50)
                            context = text[start:end].strip()
                            
                            keys.append(DocumentKey(
                                document_id=document_id,
                                key_type=key_type.value,
                                key_value=value,
                                key_value_normalized=self._normalize_key_value(value),
                                confidence=0.9,  # High confidence for regex matches
                                extraction_method=ExtractionMethod.REGEX.value,
                                source_text=context[:500]  # Limit context length
                            ))
                except Exception as e:
                    logger.warning(f"Regex error for pattern {pattern}: {e}")
        
        return keys
    
    def _extract_from_parsed(self, document_id: UUID, parsed_data: Dict) -> List[DocumentKey]:
        """Extract keys from structured parsed data."""
        keys = []
        
        # Common field mappings from document schemas
        field_mappings = {
            'entry_number': KeyType.ENTRY_NUM,
            'entry_no': KeyType.ENTRY_NUM,
            'bill_of_lading': KeyType.BOL_NUM,
            'bol': KeyType.BOL_NUM,
            'bol_number': KeyType.BOL_NUM,
            'bl_number': KeyType.BOL_NUM,
            'master_bl': KeyType.BOL_NUM,
            'house_bl': KeyType.BOL_NUM,
            'awb_number': KeyType.AWB_NUM,
            'air_waybill': KeyType.AWB_NUM,
            'container': KeyType.CONTAINER_NUM,
            'container_number': KeyType.CONTAINER_NUM,
            'po_number': KeyType.PO_NUM,
            'purchase_order': KeyType.PO_NUM,
            'invoice_number': KeyType.INVOICE_NUM,
            'invoice_no': KeyType.INVOICE_NUM,
            'hts': KeyType.HTS_CODE,
            'hts_code': KeyType.HTS_CODE,
            'tariff_code': KeyType.HTS_CODE,
            'hs_code': KeyType.HTS_CODE,
            'country_of_origin': KeyType.COUNTRY_ORIGIN,
            'origin': KeyType.COUNTRY_ORIGIN,
            'importer': KeyType.IMPORTER_NAME,
            'importer_name': KeyType.IMPORTER_NAME,
            'importer_of_record': KeyType.IMPORTER_NAME,
            'consignee': KeyType.IMPORTER_NAME,
            'exporter': KeyType.VENDOR_NAME,
            'exporter_name': KeyType.VENDOR_NAME,
            'vendor': KeyType.VENDOR_NAME,
            'vendor_name': KeyType.VENDOR_NAME,
            'seller': KeyType.VENDOR_NAME,
            'shipper': KeyType.VENDOR_NAME,
            'manufacturer': KeyType.MANUFACTURER_NAME,
            'manufacturer_name': KeyType.MANUFACTURER_NAME,
        }
        
        def extract_from_dict(d: Dict, prefix: str = ""):
            for key, value in d.items():
                if isinstance(value, dict):
                    extract_from_dict(value, f"{prefix}{key}.")
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            extract_from_dict(item, f"{prefix}{key}[{i}].")
                        elif isinstance(item, str) and item.strip():
                            check_and_add(key, item)
                elif isinstance(value, str) and value.strip():
                    check_and_add(key, value)
        
        def check_and_add(field_name: str, value: str):
            field_lower = field_name.lower().replace(' ', '_').replace('-', '_')
            if field_lower in field_mappings:
                key_type = field_mappings[field_lower]
                clean_value = self._clean_key_value(value)
                if clean_value and self._validate_key_value(key_type, clean_value):
                    keys.append(DocumentKey(
                        document_id=document_id,
                        key_type=key_type.value,
                        key_value=clean_value,
                        key_value_normalized=self._normalize_key_value(clean_value),
                        confidence=0.95,  # Higher confidence for structured data
                        extraction_method=ExtractionMethod.STRUCTURED.value,
                        source_text=f"Field: {field_name}"
                    ))
        
        extract_from_dict(parsed_data)
        return keys
    
    async def _extract_with_llm(self, document_id: UUID, text: str) -> List[DocumentKey]:
        """Extract complex keys using LLM (entities, ambiguous references)."""
        keys = []
        
        if not self.llm_service:
            return keys
        
        try:
            # Truncate text if too long
            max_chars = 8000
            truncated_text = text[:max_chars] if len(text) > max_chars else text
            
            prompt = f"""Extract key identifiers from this customs/trade document.
Return a JSON array of objects with these fields:
- key_type: One of ENTRY_NUM, BOL_NUM, AWB_NUM, CONTAINER_NUM, PO_NUM, INVOICE_NUM, IMPORTER_NAME, VENDOR_NAME, MANUFACTURER_NAME, HTS_CODE, COUNTRY_ORIGIN
- key_value: The extracted value
- confidence: 0.0 to 1.0 confidence score
- source_text: The text snippet where you found this

Focus on:
1. Entry numbers (11 digits, format XXX-XXXXXXX-X)
2. Bill of Lading numbers (typically starts with carrier code like MAEU, HLCU)
3. Container numbers (4 letters + 7 digits)
4. Company names (importers, exporters, manufacturers)
5. Purchase order and invoice numbers

Document text:
{truncated_text}

Return ONLY a JSON array, no other text."""
            
            response = await self.llm_service.complete(
                prompt,
                temperature=0.1,
                max_tokens=2000
            )
            
            # Parse LLM response
            import json
            try:
                response_text = response.strip()
                if response_text.startswith('```'):
                    response_text = response_text.split('```')[1]
                    if response_text.startswith('json'):
                        response_text = response_text[4:]
                
                extracted = json.loads(response_text)
                
                for item in extracted:
                    key_type_str = item.get('key_type', '').upper()
                    try:
                        key_type = KeyType(key_type_str)
                    except ValueError:
                        continue
                    
                    value = self._clean_key_value(item.get('key_value', ''))
                    if value:
                        keys.append(DocumentKey(
                            document_id=document_id,
                            key_type=key_type.value,
                            key_value=value,
                            key_value_normalized=self._normalize_key_value(value),
                            confidence=float(item.get('confidence', 0.7)),
                            extraction_method=ExtractionMethod.LLM.value,
                            source_text=item.get('source_text', '')[:500]
                        ))
                        
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response: {e}")
                
        except Exception as e:
            logger.error(f"LLM key extraction failed: {e}")
        
        return keys
    
    def _clean_key_value(self, value: str) -> str:
        """Clean and normalize a key value."""
        if not value:
            return ""
        
        # Remove common artifacts
        value = value.strip()
        value = re.sub(r'^[#:\s]+', '', value)
        value = re.sub(r'[#:\s]+$', '', value)
        
        return value
    
    def _normalize_key_value(self, value: str) -> str:
        """Normalize key value for matching (uppercase, no separators)."""
        if not value:
            return ""
        
        # Uppercase, remove separators
        normalized = value.upper()
        normalized = re.sub(r'[-\s#:.]+', '', normalized)
        
        return normalized
    
    def _validate_key_value(self, key_type: KeyType, value: str) -> bool:
        """Validate that a key value is reasonable for its type."""
        if not value or len(value) < 2:
            return False
        
        # Type-specific validation
        if key_type == KeyType.ENTRY_NUM:
            # Should be 11-12 digits
            digits = re.sub(r'\D', '', value)
            return 10 <= len(digits) <= 12
        
        elif key_type == KeyType.CONTAINER_NUM:
            # Should be 4 letters + 7 digits
            clean = re.sub(r'[-\s]', '', value.upper())
            return bool(re.match(r'^[A-Z]{4}\d{7}$', clean))
        
        elif key_type == KeyType.BOL_NUM:
            # Should be alphanumeric, 8+ chars
            return len(value) >= 8 and value.replace('-', '').replace(' ', '').isalnum()
        
        elif key_type == KeyType.AWB_NUM:
            # Should be numeric with dashes, typically 11-12 digits
            digits = re.sub(r'\D', '', value)
            return 8 <= len(digits) <= 12
        
        elif key_type == KeyType.PO_NUM:
            # Filter out common false positives
            value_lower = value.lower()
            for fp in self.po_false_positives:
                if value_lower.startswith(fp) or fp in value_lower.split():
                    return False
            # Should be alphanumeric, at least 4 chars
            clean_value = value.replace('-', '').replace(' ', '').replace('#', '')
            return len(value) >= 4 and clean_value.isalnum()
        
        elif key_type == KeyType.HTS_CODE:
            # Should be numeric with dots, 8-10 digits
            digits = re.sub(r'\D', '', value)
            return 8 <= len(digits) <= 10
        
        elif key_type in [KeyType.IMPORTER_NAME, KeyType.VENDOR_NAME, KeyType.MANUFACTURER_NAME]:
            # Should be at least 3 chars, not just numbers
            return len(value) >= 3 and not value.isdigit()
        
        elif key_type == KeyType.COUNTRY_ORIGIN:
            # Should be 2 letter code
            return len(value) == 2 and value.isalpha()
        
        return True  # Default accept
    
    def _deduplicate_keys(self, keys: List[DocumentKey]) -> List[DocumentKey]:
        """Remove duplicate keys, keeping highest confidence."""
        seen = {}
        
        for key in keys:
            key_id = (key.key_type, key.key_value_normalized or key.key_value)
            
            if key_id not in seen or key.confidence > seen[key_id].confidence:
                seen[key_id] = key
        
        return list(seen.values())
    
    def get_strongest_key(self, keys: List[DocumentKey]) -> Optional[DocumentKey]:
        """Get the strongest (highest priority) link key from a list."""
        if not keys:
            return None
        
        # Sort by priority (lower is stronger)
        sorted_keys = sorted(
            keys,
            key=lambda k: (KEY_PRIORITY.get(KeyType(k.key_type), 99), -k.confidence)
        )
        
        return sorted_keys[0]
    
    async def get_keys_for_document(self, document_id: UUID) -> List[DocumentKey]:
        """Get all extracted keys for a document from database."""
        result = await self.db.execute(
            select(DocumentKey)
            .where(DocumentKey.document_id == document_id)
            .order_by(DocumentKey.key_type)
        )
        return list(result.scalars().all())
    
    async def find_documents_with_key(
        self,
        key_type: str,
        key_value: str,
        exclude_document_id: UUID = None
    ) -> List[UUID]:
        """Find all documents that have a specific key."""
        normalized = self._normalize_key_value(key_value)
        
        query = select(DocumentKey.document_id).where(
            DocumentKey.key_type == key_type,
            DocumentKey.key_value_normalized == normalized
        )
        
        if exclude_document_id:
            query = query.where(DocumentKey.document_id != exclude_document_id)
        
        result = await self.db.execute(query)
        return [row[0] for row in result.all()]


# Factory function
def get_key_extractor(db: AsyncSession, llm_service=None) -> KeyExtractorService:
    """Create a KeyExtractorService instance."""
    return KeyExtractorService(db, llm_service)
