"""
Entity Extraction Agent.

This agent uses LLM reasoning to extract structured entities from documents,
including people, organizations, dates, monetary values, and custom entity types.
"""

import json
import logging
from typing import Dict, Any, List
from dataclasses import dataclass, field

from app.agents.base_agent import BaseAgent, AgentContext, Tool

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Represents an extracted entity."""
    
    entity_type: str
    value: str
    confidence: float = 0.0
    context: str = ""  # Surrounding text
    normalized_value: str = ""  # Standardized form
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.entity_type,
            "value": self.value,
            "confidence": self.confidence,
            "context": self.context,
            "normalized_value": self.normalized_value or self.value,
            "metadata": self.metadata,
        }


class EntityExtractionAgent(BaseAgent):
    """
    Agent that extracts structured entities from documents.
    
    Capabilities:
    - Extracts people names, organizations, locations
    - Identifies dates, times, and temporal expressions
    - Finds monetary values and currencies
    - Extracts emails, phone numbers, URLs
    - Identifies custom domain-specific entities
    - Resolves and normalizes entity values
    """
    
    ENTITY_TYPES = {
        "person": "Names of people, including titles (Dr., Mr., CEO)",
        "organization": "Company names, institutions, agencies, teams",
        "location": "Cities, countries, addresses, geographic locations",
        "date": "Dates, date ranges, temporal expressions (Q4 2025, next week)",
        "money": "Monetary amounts with currencies ($10,000, €500, 1M USD)",
        "email": "Email addresses",
        "phone": "Phone numbers in any format",
        "url": "Web URLs and links",
        "product": "Product names, SKUs, model numbers",
        "document_id": "Reference numbers, invoice IDs, contract numbers",
        "percentage": "Percentages and ratios",
        "quantity": "Numeric quantities with units (100kg, 50 units)",
    }
    
    def __init__(self, custom_entity_types: Dict[str, str] = None):
        super().__init__(
            name="entity_extractor",
            description="Extracts and normalizes entities from document content",
            model="gpt-4o-mini",
            temperature=0.0,  # Deterministic for consistency
            max_tokens=3000,
        )
        
        self.entity_types = {**self.ENTITY_TYPES}
        if custom_entity_types:
            self.entity_types.update(custom_entity_types)
        
        # Register tools
        self.register_tool(Tool(
            name="normalize_date",
            description="Normalize a date expression to ISO format",
            function=self._normalize_date,
            parameters={
                "type": "object",
                "properties": {
                    "date_string": {"type": "string", "description": "The date to normalize"},
                },
                "required": ["date_string"],
            }
        ))
    
    @staticmethod
    def _normalize_date(date_string: str) -> str:
        """Tool: Normalize date to ISO format."""
        from datetime import datetime
        import re
        
        # Try common formats
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%Y/%m/%d",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_string.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        return date_string  # Return original if can't parse
    
    def get_system_prompt(self) -> str:
        types_str = "\n".join([f"- **{k}**: {v}" for k, v in self.entity_types.items()])
        
        return f"""You are an expert entity extraction agent. Your job is to identify and extract structured entities from documents with high precision.

## Entity Types to Extract:
{types_str}

## Instructions:
1. Read the document carefully and thoroughly
2. Extract ALL instances of each entity type found
3. For each entity, provide:
   - The exact text as it appears in the document
   - A normalized/standardized form when applicable
   - Confidence score (0-1) based on clarity
   - Brief context (surrounding words)
4. Be precise - don't extract partial entities
5. Resolve references (e.g., "the company" → actual company name if known)
6. For dates, normalize to YYYY-MM-DD when possible
7. For money, normalize to numeric value with currency code

## Output Format (JSON only):
{{
    "entities": [
        {{
            "type": "person",
            "value": "John Smith",
            "normalized_value": "John Smith",
            "confidence": 0.95,
            "context": "signed by John Smith, CEO"
        }},
        {{
            "type": "money",
            "value": "$50,000",
            "normalized_value": "50000 USD",
            "confidence": 0.99,
            "context": "total amount of $50,000"
        }}
    ],
    "entity_count": 2,
    "extraction_notes": "Document contains clear entity markers"
}}
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        # Check if previous classification exists
        classification = ""
        if "document_classifier" in context.previous_results:
            cat = context.previous_results["document_classifier"].get("output", {})
            classification = f"\n**Document Category:** {cat.get('category', 'unknown')}"
        
        return f"""Extract all entities from this document:

**Filename:** {context.filename}
**File Type:** {context.file_type}{classification}

**Document Content:**
{context.content[:5000]}

{"[Content truncated...]" if len(context.content) > 5000 else ""}

Extract all entities with their types, values, and confidence scores."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(response)
            
            # Process entities
            entities = []
            entity_by_type: Dict[str, List] = {}
            
            for entity_data in result.get("entities", []):
                entity_type = entity_data.get("type", "unknown")
                
                entity = Entity(
                    entity_type=entity_type,
                    value=entity_data.get("value", ""),
                    confidence=min(max(float(entity_data.get("confidence", 0.5)), 0), 1),
                    context=entity_data.get("context", ""),
                    normalized_value=entity_data.get("normalized_value", ""),
                )
                
                entities.append(entity.to_dict())
                
                if entity_type not in entity_by_type:
                    entity_by_type[entity_type] = []
                entity_by_type[entity_type].append(entity.value)
            
            return {
                "entities": entities,
                "entity_count": len(entities),
                "entities_by_type": entity_by_type,
                "extraction_notes": result.get("extraction_notes", ""),
                "confidence": sum(e["confidence"] for e in entities) / len(entities) if entities else 0,
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse entity extraction response: {e}")
            return {
                "entities": [],
                "entity_count": 0,
                "entities_by_type": {},
                "extraction_notes": f"Parse error: {str(e)}",
                "confidence": 0,
            }


class RelationshipExtractionAgent(BaseAgent):
    """
    Agent that extracts relationships between entities.
    
    After entities are extracted, this agent identifies how they
    relate to each other (e.g., "John Smith works for Acme Corp").
    """
    
    RELATIONSHIP_TYPES = [
        "works_for",
        "owns",
        "signed_by",
        "dated",
        "amount_of",
        "located_in",
        "reported_to",
        "partner_of",
        "subsidiary_of",
        "contracted_with",
        "received_from",
        "sent_to",
    ]
    
    def __init__(self):
        super().__init__(
            name="relationship_extractor",
            description="Extracts relationships between entities",
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=2000,
        )
    
    def get_system_prompt(self) -> str:
        relationships = ", ".join(self.RELATIONSHIP_TYPES)
        
        return f"""You are a relationship extraction agent. Given entities extracted from a document, identify relationships between them.

## Relationship Types:
{relationships}

## Instructions:
1. Analyze how entities are connected in the document
2. Identify explicit relationships stated in text
3. Infer implicit relationships when strongly indicated
4. For each relationship, specify source entity, target entity, and type

## Output Format (JSON):
{{
    "relationships": [
        {{
            "source": "John Smith",
            "source_type": "person",
            "relationship": "works_for",
            "target": "Acme Corporation",
            "target_type": "organization",
            "confidence": 0.9,
            "evidence": "John Smith, CEO of Acme Corporation"
        }}
    ]
}}
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        entities = []
        if "entity_extractor" in context.previous_results:
            entities = context.previous_results["entity_extractor"].get("output", {}).get("entities", [])
        
        entities_str = json.dumps(entities, indent=2) if entities else "No entities provided"
        
        return f"""Find relationships between these entities:

**Entities:**
{entities_str}

**Document Context:**
{context.content[:3000]}

Identify all relationships between the entities."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(response)
            
            relationships = []
            for rel in result.get("relationships", []):
                relationships.append({
                    "source": rel.get("source", ""),
                    "source_type": rel.get("source_type", "unknown"),
                    "relationship": rel.get("relationship", "related_to"),
                    "target": rel.get("target", ""),
                    "target_type": rel.get("target_type", "unknown"),
                    "confidence": min(max(float(rel.get("confidence", 0.5)), 0), 1),
                    "evidence": rel.get("evidence", ""),
                })
            
            return {
                "relationships": relationships,
                "relationship_count": len(relationships),
            }
            
        except json.JSONDecodeError:
            return {
                "relationships": [],
                "relationship_count": 0,
            }
