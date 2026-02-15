"""
Trade Document Extraction Service

Uses structured prompts to extract comprehensive trade/customs data from documents.
This service produces output suitable for the medallion architecture:
- Bronze: Raw JSON extraction
- Silver: Normalized parties, products, addresses
- Gold: Shipments, entries, invoices
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Load the extraction prompt template
PROMPT_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "trade-documents" / "extraction_prompt.txt"


class TradeDocumentExtractionService:
    """
    Service for extracting structured data from trade documents using LLM.
    
    Uses domain-specific prompts to identify document types and extract
    all relevant fields for customs brokerage operations.
    """
    
    def __init__(self):
        self.client = None
        self.prompt_template = None
        self._load_prompt_template()
    
    def _load_prompt_template(self):
        """Load the extraction prompt template from file."""
        try:
            if PROMPT_TEMPLATE_PATH.exists():
                self.prompt_template = PROMPT_TEMPLATE_PATH.read_text()
                logger.info(f"Loaded trade document extraction prompt ({len(self.prompt_template)} chars)")
            else:
                logger.warning(f"Prompt template not found at {PROMPT_TEMPLATE_PATH}")
                self.prompt_template = self._get_fallback_prompt()
        except Exception as e:
            logger.error(f"Error loading prompt template: {e}")
            self.prompt_template = self._get_fallback_prompt()
    
    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if template file not available."""
        return """
        Extract all structured data from this trade document.
        Return valid JSON with: document_metadata, parties, shipment, cargo, financials.
        Document: <<DOCUMENT_CONTENT>>
        """
    
    async def _get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self.client is None:
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self.client
    
    async def extract_document(
        self,
        document_text: str,
        filename: Optional[str] = None,
        file_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract structured data from a trade document.
        
        Args:
            document_text: The text content of the document
            filename: Optional filename for context
            file_type: Optional file type hint
            
        Returns:
            Structured extraction result as a dictionary
        """
        if not document_text or len(document_text.strip()) < 50:
            return {
                "status": "error",
                "error": "Document text too short or empty",
                "document_metadata": {"document_type": "Unknown", "confidence_score": 0}
            }
        
        # Prepare the prompt
        prompt = self.prompt_template.replace("<<DOCUMENT_CONTENT>>", document_text)
        
        # Add filename hint if available
        if filename:
            prompt = prompt.replace(
                "DOCUMENT TO ANALYZE",
                f"DOCUMENT TO ANALYZE\nFilename hint: {filename}"
            )
        
        try:
            client = await self._get_client()
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective for structured extraction
                messages=[
                    {
                        "role": "system",
                        "content": "You are a trade document analyst. Return ONLY valid JSON, no other text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                result = json.loads(result_text)
                result["status"] = "success"
                result["extraction_timestamp"] = datetime.utcnow().isoformat()
                result["source_filename"] = filename
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse extraction JSON: {e}")
                return {
                    "status": "error",
                    "error": f"Invalid JSON response: {e}",
                    "raw_response": result_text[:500]
                }
                
        except Exception as e:
            logger.error(f"Trade document extraction failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def map_to_bronze_layer(self, extraction: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert the structured extraction to Bronze layer records (extraction_results).
        
        This flattens the nested JSON into individual field extractions
        suitable for storing in the extraction_results table.
        """
        results = []
        
        if extraction.get("status") != "success":
            return results
        
        # Document metadata
        doc_meta = extraction.get("document_metadata", {})
        if doc_meta:
            results.append({
                "field_name": "document_type",
                "field_value": doc_meta.get("document_type"),
                "confidence": doc_meta.get("confidence_score", 0.9),
                "extraction_type": "llm_structured"
            })
        
        # Parties
        parties = extraction.get("parties", {})
        for role, party_data in parties.items():
            if party_data and isinstance(party_data, dict):
                if party_data.get("name"):
                    results.append({
                        "field_name": role,
                        "field_value": party_data.get("name"),
                        "confidence": 0.95,
                        "extraction_type": "llm_structured",
                        "metadata": party_data
                    })
        
        # Shipment identifiers
        shipment = extraction.get("shipment", {})
        for field in ["master_bl_number", "house_bl_number", "booking_number", "vessel_name"]:
            if shipment.get(field):
                results.append({
                    "field_name": field,
                    "field_value": shipment.get(field),
                    "confidence": 0.95,
                    "extraction_type": "llm_structured"
                })
        
        # Containers
        containers = shipment.get("containers", [])
        for i, container in enumerate(containers):
            if container.get("number"):
                results.append({
                    "field_name": f"container_{i+1}",
                    "field_value": container.get("number"),
                    "confidence": 0.95,
                    "extraction_type": "llm_structured",
                    "metadata": container
                })
        
        # Cargo items with HTS codes
        cargo = extraction.get("cargo", {})
        items = cargo.get("items", [])
        for i, item in enumerate(items):
            if item.get("description"):
                results.append({
                    "field_name": f"cargo_item_{i+1}",
                    "field_value": item.get("description"),
                    "confidence": 0.9,
                    "extraction_type": "llm_structured",
                    "metadata": {
                        "hs_code": item.get("hs_code"),
                        "hts_code": item.get("hts_code_10_digit"),
                        "country_of_origin": item.get("country_of_origin"),
                        "quantity": item.get("quantity"),
                        "unit_price": item.get("unit_price"),
                        "total_value": item.get("total_value"),
                        "gross_weight_kg": item.get("gross_weight_kg")
                    }
                })
        
        # Financials
        financials = extraction.get("financials", {})
        if financials.get("invoice_number"):
            results.append({
                "field_name": "invoice_number",
                "field_value": financials.get("invoice_number"),
                "confidence": 0.95,
                "extraction_type": "llm_structured"
            })
        if financials.get("total_invoice_value"):
            results.append({
                "field_name": "total_invoice_value",
                "field_value": str(financials.get("total_invoice_value")),
                "confidence": 0.9,
                "extraction_type": "llm_structured",
                "metadata": {
                    "currency": financials.get("currency"),
                    "cif_value": financials.get("cif_value")
                }
            })
        
        # Deadlines (critical for operations)
        deadlines = extraction.get("deadlines_and_risks", {})
        if deadlines.get("last_free_day"):
            results.append({
                "field_name": "last_free_day",
                "field_value": deadlines.get("last_free_day"),
                "confidence": 0.95,
                "extraction_type": "llm_structured"
            })
        
        # Customs entry data
        customs = extraction.get("customs_entry", {})
        if customs.get("entry_number"):
            results.append({
                "field_name": "entry_number",
                "field_value": customs.get("entry_number"),
                "confidence": 0.95,
                "extraction_type": "llm_structured",
                "metadata": customs
            })
        
        return results
    
    def map_to_silver_layer(self, extraction: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Convert the structured extraction to Silver layer entities.
        
        Returns dict with keys: parties, products, addresses ready for 
        insertion into Silver tables.
        """
        silver = {
            "parties": [],
            "products": [],
            "addresses": []
        }
        
        if extraction.get("status") != "success":
            return silver
        
        # Parties with roles
        parties = extraction.get("parties", {})
        for role, party_data in parties.items():
            if party_data and isinstance(party_data, dict) and party_data.get("name"):
                silver["parties"].append({
                    "canonical_name": party_data.get("name"),
                    "party_type": role,
                    "tax_id": party_data.get("tax_id") or party_data.get("importer_of_record_number"),
                    "aliases": [party_data.get("name")],
                    "contact_info": {
                        "contact": party_data.get("contact"),
                        "country": party_data.get("country")
                    }
                })
                
                # Extract address if present
                if party_data.get("address"):
                    silver["addresses"].append({
                        "party_name": party_data.get("name"),
                        "street": party_data.get("address"),
                        "country": party_data.get("country"),
                        "normalized_address": party_data.get("address")
                    })
        
        # Products from cargo
        cargo = extraction.get("cargo", {})
        for item in cargo.get("items", []):
            if item.get("description"):
                silver["products"].append({
                    "description": item.get("description"),
                    "hs_code": item.get("hts_code_10_digit") or item.get("hs_code"),
                    "country_of_origin": item.get("country_of_origin"),
                    "unit_of_measure": item.get("unit_of_measure"),
                    "aliases": [item.get("description")]
                })
        
        return silver
    
    def map_to_gold_layer(self, extraction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert the structured extraction to Gold layer business objects.
        
        Returns dict with shipment, invoice, entry data ready for 
        Gold layer tables.
        """
        gold = {
            "shipment": None,
            "invoice": None,
            "entry": None
        }
        
        if extraction.get("status") != "success":
            return gold
        
        shipment = extraction.get("shipment", {})
        if shipment.get("master_bl_number") or shipment.get("house_bl_number"):
            gold["shipment"] = {
                "primary_key_type": "master_bl" if shipment.get("master_bl_number") else "house_bl",
                "primary_key_value": shipment.get("master_bl_number") or shipment.get("house_bl_number"),
                "vessel_name": shipment.get("vessel_name"),
                "voyage_number": shipment.get("voyage_number"),
                "port_of_origin": shipment.get("port_of_loading"),
                "port_of_destination": shipment.get("port_of_discharge"),
                "estimated_arrival": shipment.get("eta"),
                "importer_name": extraction.get("parties", {}).get("consignee", {}).get("name"),
                "container_numbers": [c.get("number") for c in shipment.get("containers", []) if c.get("number")]
            }
        
        financials = extraction.get("financials", {})
        if financials.get("invoice_number"):
            gold["invoice"] = {
                "invoice_number": financials.get("invoice_number"),
                "invoice_date": financials.get("invoice_date"),
                "currency": financials.get("currency"),
                "total_amount": financials.get("total_invoice_value"),
                "vendor_name": extraction.get("parties", {}).get("shipper", {}).get("name"),
                "buyer_name": extraction.get("parties", {}).get("consignee", {}).get("name")
            }
        
        customs = extraction.get("customs_entry", {})
        if customs.get("entry_number"):
            gold["entry"] = {
                "entry_number": customs.get("entry_number"),
                "entry_type": customs.get("entry_type"),
                "entry_date": customs.get("entry_date"),
                "port_code": customs.get("entry_port"),
                "duty_amount": financials.get("duty_amount"),
                "mpf_amount": financials.get("mpf_amount"),
                "hmf_amount": financials.get("hmf_amount"),
                "total_duty": financials.get("total_taxes_and_duties")
            }
        
        return gold


# Singleton instance
_service_instance = None

def get_trade_extraction_service() -> TradeDocumentExtractionService:
    """Get the singleton trade document extraction service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = TradeDocumentExtractionService()
    return _service_instance
