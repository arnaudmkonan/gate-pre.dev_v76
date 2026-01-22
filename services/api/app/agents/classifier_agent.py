"""
Document Classification Agent.

This agent analyzes document content and classifies it into categories
using LLM reasoning. It provides confidence scores and reasoning for
its classification decisions.
"""

import json
import logging
from typing import Dict, Any, List

from app.agents.base_agent import BaseAgent, AgentContext, Tool

logger = logging.getLogger(__name__)


# Document categories with descriptions
DOCUMENT_CATEGORIES = {
    "contract": "Legal contracts, agreements, terms of service, NDAs",
    "invoice": "Invoices, bills for services rendered, payment requests from vendors",
    "receipt": "Store receipts, purchase receipts, transaction records, point-of-sale documents showing items bought and payment made",
    "bill_of_lading": "Bills of lading, BOL, shipping documents, freight documents, cargo manifests",
    "shipping": "Shipping labels, packing slips, delivery receipts, waybills, tracking documents",
    "report": "Business reports, analytics, quarterly reports, annual reports",
    "correspondence": "Emails, letters, memos, internal communications",
    "technical": "Technical documentation, API docs, manuals, specifications",
    "hr_document": "Employee records, handbooks, policies, job descriptions",
    "financial": "Financial statements, budgets, expense reports, tax documents",
    "marketing": "Marketing materials, brochures, presentations, campaigns",
    "legal": "Legal briefs, court documents, regulations, compliance docs",
    "product": "Product catalogs, feature lists, datasheets, SKU lists",
    "configuration": "Configuration files, settings, environment configs",
    "data": "Data files, spreadsheets, CSV, structured data exports",
    "other": "Documents that don't fit other categories",
}


class DocumentClassifierAgent(BaseAgent):
    """
    Agent that classifies documents into predefined categories.
    
    Capabilities:
    - Analyzes document content and structure
    - Identifies document type and purpose
    - Provides confidence scores for classifications
    - Explains reasoning for classification decisions
    """
    
    def __init__(self):
        super().__init__(
            name="document_classifier",
            description="Classifies documents into categories based on content analysis",
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=1500,
        )
        
        # Register tools
        self.register_tool(Tool(
            name="get_categories",
            description="Get the list of available document categories",
            function=self._get_categories,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            }
        ))
    
    @staticmethod
    def _get_categories() -> Dict[str, str]:
        """Tool: Get available document categories."""
        return DOCUMENT_CATEGORIES
    
    def get_system_prompt(self) -> str:
        categories_str = "\n".join([f"- {k}: {v}" for k, v in DOCUMENT_CATEGORIES.items()])
        
        return f"""You are an expert document classification agent. Your job is to analyze documents and classify them into the most appropriate category.

## Available Categories:
{categories_str}

## Instructions:
1. Carefully analyze the document content, structure, and purpose
2. Consider the vocabulary, formatting, and typical patterns
3. Select the SINGLE most appropriate category
4. If multiple categories could apply, choose the primary purpose
5. Provide a confidence score (0-1) based on how certain you are
6. Explain your reasoning briefly

## Output Format:
You MUST respond with valid JSON only, no other text:
{{
    "category": "category_name",
    "confidence": 0.85,
    "reasoning": "Brief explanation of why this category was chosen",
    "alternative_categories": ["other_possible_category"],
    "key_indicators": ["indicator1", "indicator2"]
}}
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        return f"""Classify the following document:

**Filename:** {context.filename}
**File Type:** {context.file_type}

**Document Content:**
{context.content[:4000]}

{"[Content truncated - document continues...]" if len(context.content) > 4000 else ""}

Analyze this document and provide your classification in JSON format."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        """Parse the classification response."""
        try:
            # Try to extract JSON from response
            response = response.strip()
            
            # Handle markdown code blocks
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(response)
            
            # Validate required fields
            category = result.get("category", "other")
            if category not in DOCUMENT_CATEGORIES:
                category = "other"
            
            return {
                "category": category,
                "confidence": min(max(float(result.get("confidence", 0.5)), 0), 1),
                "reasoning": result.get("reasoning", ""),
                "alternative_categories": result.get("alternative_categories", []),
                "key_indicators": result.get("key_indicators", []),
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse classification response: {e}")
            # Attempt basic extraction
            return {
                "category": "other",
                "confidence": 0.3,
                "reasoning": f"Failed to parse response: {response[:200]}",
                "alternative_categories": [],
                "key_indicators": [],
            }


class MultiLabelClassifierAgent(BaseAgent):
    """
    Agent that assigns multiple labels/tags to documents.
    
    Unlike the single-category classifier, this agent can identify
    multiple applicable labels for a document.
    """
    
    AVAILABLE_LABELS = [
        "confidential",
        "urgent",
        "requires_review",
        "contains_pii",
        "contains_financial_data",
        "external_facing",
        "internal_only",
        "draft",
        "final",
        "archived",
        "action_required",
        "informational",
        "regulatory",
        "customer_facing",
        "technical",
        "business_critical",
    ]
    
    def __init__(self):
        super().__init__(
            name="multi_label_classifier",
            description="Assigns multiple labels to documents based on content analysis",
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=1500,
        )
    
    def get_system_prompt(self) -> str:
        labels_str = ", ".join(self.AVAILABLE_LABELS)
        
        return f"""You are a document labeling agent. Your job is to analyze documents and assign ALL applicable labels.

## Available Labels:
{labels_str}

## Instructions:
1. Read the document carefully
2. Identify ALL labels that apply (can be 0 to many)
3. For each label, provide a confidence score
4. Look for indicators like:
   - "CONFIDENTIAL" markers → confidential
   - Personal info (SSN, addresses) → contains_pii
   - Dollar amounts, financial terms → contains_financial_data
   - "DRAFT" watermark → draft
   - Action items, deadlines → action_required

## Output Format (JSON only):
{{
    "labels": [
        {{"label": "confidential", "confidence": 0.9, "evidence": "Header marked CONFIDENTIAL"}},
        {{"label": "contains_pii", "confidence": 0.8, "evidence": "Contains employee SSNs"}}
    ],
    "summary": "Brief description of document characteristics"
}}
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        return f"""Analyze and label this document:

**Filename:** {context.filename}

**Content:**
{context.content[:3500]}

{"[Truncated...]" if len(context.content) > 3500 else ""}

Identify all applicable labels."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(response)
            
            # Validate labels
            valid_labels = []
            for label_info in result.get("labels", []):
                if label_info.get("label") in self.AVAILABLE_LABELS:
                    valid_labels.append({
                        "label": label_info["label"],
                        "confidence": min(max(float(label_info.get("confidence", 0.5)), 0), 1),
                        "evidence": label_info.get("evidence", ""),
                    })
            
            return {
                "labels": valid_labels,
                "label_names": [l["label"] for l in valid_labels],
                "summary": result.get("summary", ""),
            }
            
        except json.JSONDecodeError:
            return {
                "labels": [],
                "label_names": [],
                "summary": "Failed to parse labels",
            }
