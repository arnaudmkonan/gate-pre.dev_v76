"""
Template-Based Extraction Agents.

These agents use extraction templates to guide field extraction from documents,
providing more accurate and consistent results for known document types.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from app.agents.base_agent import BaseAgent, AgentContext

logger = logging.getLogger(__name__)


class TemplateMatchingAgent(BaseAgent):
    """
    Agent that matches documents to extraction templates.

    Given a document and a list of available templates, this agent
    determines which template(s) are most appropriate based on:
    - Document classification
    - Content keywords
    - Document structure
    """

    def __init__(self, templates: List[Dict[str, Any]]):
        """
        Initialize with available templates.

        Args:
            templates: List of template dictionaries with at least:
                - id: Template ID
                - name: Template name
                - document_type: Target document type
                - matching_keywords: List of keywords
                - classification_categories: List of document categories
        """
        super().__init__(
            name="template_matcher",
            description="Matches documents to extraction templates",
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=1500,
        )
        self.templates = templates

    def get_system_prompt(self) -> str:
        return """You are a document template matching agent. Your job is to analyze a document and determine which extraction template(s) would be most appropriate for extracting structured data from it.

## Instructions:
1. Analyze the document content, structure, and type
2. Compare against available templates based on:
   - Document type match (invoice, contract, form, etc.)
   - Presence of keywords associated with templates
   - Structural similarity to template expectations
3. Return ranked matches with confidence scores

## Output Format (JSON only):
{
    "matches": [
        {
            "template_id": "uuid",
            "template_name": "Template Name",
            "confidence": 0.85,
            "match_reasons": ["reason1", "reason2"]
        }
    ],
    "recommended_template_id": "uuid or null",
    "document_type_detected": "invoice|contract|form|report|other",
    "no_template_match": false,
    "reasoning": "Brief explanation of matching logic"
}

Be selective - only match templates that are clearly appropriate. Set no_template_match=true if no template fits well."""

    def get_user_prompt(self, context: AgentContext) -> str:
        # Build template descriptions
        template_descriptions = []
        for t in self.templates:
            desc = f"- **{t.get('name')}** (ID: {t.get('id')})"
            desc += f"\n  Document Type: {t.get('document_type', 'unknown')}"
            if t.get('matching_keywords'):
                desc += f"\n  Keywords: {', '.join(t['matching_keywords'][:5])}"
            if t.get('classification_categories'):
                desc += f"\n  Categories: {', '.join(t['classification_categories'])}"
            if t.get('field_count'):
                desc += f"\n  Fields: {t['field_count']}"
            template_descriptions.append(desc)

        templates_str = "\n".join(template_descriptions) if template_descriptions else "No templates available"

        # Get classification from previous results if available
        classification = ""
        if context.previous_results.get("document_classifier"):
            cls_result = context.previous_results["document_classifier"]
            if cls_result.get("output", {}).get("category"):
                classification = f"\n\nPrevious Classification: {cls_result['output']['category']}"

        return f"""## Document Information
Filename: {context.filename}
File Type: {context.file_type}
{classification}

## Document Content (Preview):
{context.content[:3000]}

## Available Templates:
{templates_str}

Analyze this document and determine which template(s) would be best for extraction. Return JSON only."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
                return {
                    "matches": result.get("matches", []),
                    "recommended_template_id": result.get("recommended_template_id"),
                    "document_type_detected": result.get("document_type_detected", "unknown"),
                    "no_template_match": result.get("no_template_match", False),
                    "reasoning": result.get("reasoning", ""),
                    "confidence": result["matches"][0]["confidence"] if result.get("matches") else 0.0,
                }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse template matching response: {e}")

        return {
            "matches": [],
            "recommended_template_id": None,
            "no_template_match": True,
            "confidence": 0.0,
        }


class TemplateExtractionAgent(BaseAgent):
    """
    Agent that extracts fields from documents using a specific template.

    Uses the template's field definitions to guide extraction, providing:
    - Targeted extraction of defined fields
    - Consistent output schema
    - Field-specific validation hints
    - Few-shot examples if available
    """

    def __init__(self, template: Dict[str, Any]):
        """
        Initialize with a specific extraction template.

        Args:
            template: Template dictionary with:
                - name: Template name
                - field_definitions: List of field specs
                - extraction_prompt: Optional custom system prompt
                - few_shot_examples: Optional examples for few-shot learning
        """
        super().__init__(
            name="template_extractor",
            description=f"Extracts fields using template: {template.get('name', 'unknown')}",
            model="gpt-4o-mini",
            temperature=0.0,  # Deterministic for consistency
            max_tokens=3000,
        )
        self.template = template
        self.template_name = template.get("name", "Unknown Template")
        self.field_definitions = template.get("field_definitions", [])
        self.extraction_prompt = template.get("extraction_prompt")
        self.few_shot_examples = template.get("few_shot_examples", [])

    def get_system_prompt(self) -> str:
        # Use custom prompt if provided
        if self.extraction_prompt:
            return self.extraction_prompt

        # Build field descriptions
        field_descriptions = []
        for field in self.field_definitions:
            name = field.get("field_name", "")
            display = field.get("display_name", name)
            desc = field.get("description", "")
            field_type = field.get("field_type", "string")
            required = field.get("required", False)
            hints = field.get("extraction_hints", [])

            field_line = f"- **{display}** (`{name}`): {desc}"
            field_line += f" [type: {field_type}]"
            if required:
                field_line += " **[REQUIRED]**"
            if hints:
                field_line += f"\n  Hints: {', '.join(hints)}"
            field_descriptions.append(field_line)

        fields_str = "\n".join(field_descriptions) if field_descriptions else "No fields defined"

        return f"""You are an expert document extraction agent using the "{self.template_name}" template.

## Fields to Extract:
{fields_str}

## Instructions:
1. Extract ONLY the fields defined above
2. For each field:
   - Look for the value in the document
   - Provide the raw value as found
   - Normalize if applicable (dates to YYYY-MM-DD, money to numeric)
   - Assign a confidence score (0-1)
3. If a field is not found, set value to null
4. Required fields must have values if present in the document

## Output Format (JSON only):
{{
    "extractions": [
        {{
            "field_name": "field_name_here",
            "value": "extracted value",
            "raw_value": "value as found in document",
            "normalized_value": "standardized value if applicable",
            "confidence": 0.95,
            "found": true,
            "context": "surrounding text snippet"
        }}
    ],
    "template_name": "{self.template_name}",
    "fields_found": 5,
    "fields_missing": ["list", "of", "missing", "required", "fields"],
    "extraction_quality": 0.85,
    "notes": "any relevant observations"
}}"""

    def get_user_prompt(self, context: AgentContext) -> str:
        # Build few-shot examples if available
        examples_str = ""
        if self.few_shot_examples:
            examples_parts = []
            for i, example in enumerate(self.few_shot_examples[:3], 1):
                input_text = example.get("input", "")[:500]
                output_text = json.dumps(example.get("output", {}), indent=2)
                examples_parts.append(f"Example {i}:\nInput: {input_text}...\nOutput: {output_text}")
            examples_str = "\n\n## Examples:\n" + "\n\n".join(examples_parts)

        return f"""## Document to Process
Filename: {context.filename}
File Type: {context.file_type}

## Document Content:
{context.content}
{examples_str}

Extract the defined fields from this document. Return JSON only."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])

                extractions = result.get("extractions", [])
                fields_found = len([e for e in extractions if e.get("found", True)])

                # Calculate overall confidence
                confidences = [e.get("confidence", 0) for e in extractions if e.get("found", True)]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

                return {
                    "extractions": extractions,
                    "template_name": self.template_name,
                    "template_id": str(self.template.get("id", "")),
                    "fields_found": fields_found,
                    "fields_total": len(self.field_definitions),
                    "fields_missing": result.get("fields_missing", []),
                    "extraction_quality": result.get("extraction_quality", avg_confidence),
                    "notes": result.get("notes", ""),
                    "confidence": avg_confidence,
                }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse template extraction response: {e}")

        return {
            "extractions": [],
            "template_name": self.template_name,
            "fields_found": 0,
            "fields_total": len(self.field_definitions),
            "confidence": 0.0,
            "error": "Failed to parse extraction response",
        }

    def get_field_names(self) -> List[str]:
        """Get list of field names this agent extracts."""
        return [f.get("field_name", "") for f in self.field_definitions]

    def get_required_fields(self) -> List[str]:
        """Get list of required field names."""
        return [f.get("field_name", "") for f in self.field_definitions if f.get("required", False)]
