import logging
import json
from typing import Dict, Any, List, Optional
from enum import Enum

from app.agents.base_agent import BaseAgent, AgentContext

logger = logging.getLogger(__name__)


class ProcessingPath(str, Enum):
    PATH_A_SEMANTIC = "path_a_semantic"
    PATH_B_CODE_MAPPING = "path_b_code_mapping"
    PATH_C_STREAM = "path_c_stream"
    UNKNOWN = "unknown"


class TriagistAgent(BaseAgent):
    """
    DM-003: Triagist Agent.
    
    Analyzes incoming files to determine the optimal processing path (A, B, or C)
    and assigns processing priority.
    
    Paths:
    - Path A (Semantic): Unstructured documents (PDF, Docs, Images) requiring OCR/Layout Analysis.
    - Path B (Code Mapping): Structured/Tabular data (CSV, Excel, JSON) requiring deterministic transformation.
    - Path C (Stream): Real-time data streams (not typically handled by file upload agent, but included for completeness).
    """
    
    def __init__(self):
        super().__init__(
            name="triagist_agent",
            description="Analyzes files to determine processing path (Semantic vs Code Mapping) and priority.",
            model="gpt-4o-mini",  # Efficiency is key here
            temperature=0.0,
            max_tokens=500,
        )

    def get_system_prompt(self) -> str:
        return """You are the Triagist Agent for a document ingestion system.
Your goal is to inspect a file's metadata and content preview to determine the best Processing Path.

## Routes:
1. **Path A (Semantic)**: 
   - Use for: Unstructured documents, PDFs, Images, Word Docs, PowerPoints, contracts, invoices, reports, letters.
   - Mechanism: OCR, Layout Analysis (Docling), LLM Extraction.
   
2. **Path B (Code Mapping)**: 
   - Use for: Structured or Semi-structured data, CSVs, Excel spreadsheets, JSON dumps, XML exports, database dumps.
   - Mechanism: Deterministic Python Code Mapping (Pandas/Scripts).
   
3. **Path C (Stream)**:
   - Use for: Raw API payloads (rarely via file upload).

## Priority Assignment:
- **High**: Urgent documents (Invoices, time-sensitive notices), "URGENT" in text.
- **Medium**: Standard business documents (Contracts, Reports).
- **Low**: Archives, logs, background data.

## Output Format (JSON):
{
    "path": "path_a_semantic" | "path_b_code_mapping" | "path_c_stream",
    "priority": "high" | "medium" | "low",
    "document_class": "invoice|contract|data_dump|etc",
    "confidence": 0.95,
    "reasoning": "File is a PDF invoice..."
}
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        return f"""Analyze this file for routing:

**Filename:** {context.filename}
**File Type:** {context.file_type}
**Size:** {context.metadata.get('size', 0)} bytes

**Content Preview:**
{context.content[:2000]}

Determine the Processing Path and Priority. JSON only."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            # Clean possible markdown
            clean_resp = response.strip()
            if clean_resp.startswith("```"):
                clean_resp = clean_resp.split("\n", 1)[1]
                if clean_resp.endswith("```"):
                    clean_resp = clean_resp.rsplit("```", 1)[0]
            
            result = json.loads(clean_resp)
            
            # Validate path
            path = result.get("path", "path_a_semantic")
            if path not in [p.value for p in ProcessingPath]:
                path = ProcessingPath.PATH_A_SEMANTIC.value
                
            return {
                "path": path,
                "priority": result.get("priority", "medium"),
                "document_class": result.get("document_class", "unknown"),
                "confidence": result.get("confidence", 0.5),
                "reasoning": result.get("reasoning", "")
            }
            
        except Exception as e:
            logger.error(f"Failed to parse Triagist response: {e}")
            # Fallback based on extension
            fallback_path = ProcessingPath.PATH_A_SEMANTIC.value
            if context.file_type in ["csv", "xlsx", "json", "xml"]:
                fallback_path = ProcessingPath.PATH_B_CODE_MAPPING.value
                
            return {
                "path": fallback_path,
                "priority": "medium",
                "document_class": "unknown",
                "confidence": 0.3,
                "reasoning": "Fallback due to parse error",
                "error": str(e)
            }
