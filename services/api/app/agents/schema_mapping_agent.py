import logging
import json
from typing import Dict, Any, List, Optional

from app.agents.base_agent import BaseAgent, AgentContext, Tool

logger = logging.getLogger(__name__)


class SchemaMappingAgent(BaseAgent):
    """
    Path B: Schema Mapping & Inference Agent.
    
    Responsibilities:
    1. Infer schema/data types from raw data samples (CSV headers + rows).
    2. Generate Python transformation code to map source data to a target schema.
    
    This agent helps automate the setup of data pipelines for structured files (Path B).
    """
    
    def __init__(self):
        super().__init__(
            name="schema_mapping_agent",
            description="Infers schemas and generates Python mapping code for structured data transformation",
            model="gpt-4o",  # Using high-capability model for code generation
            temperature=0.0,  # Deterministic output for code
            max_tokens=2500,
        )

    def get_system_prompt(self) -> str:
        return """You are an expert Data Engineer and Python Developer specialized in ETL pipelines.
Your goal is to assist in two main tasks:
1. **Schema Inference**: Analyze a sample of data (headers + rows) and infer the data types and meaning of each column.
2. **Mapping Generation**: Generate robust, defensive Python code to transform source data into a strict target schema.

## Instructions for Mapping Generation:
- You will be provided with 'Source Schema' (columns + samples) and 'Target Schema' (required fields).
- Generate a Python function named `transform_record(record: dict) -> dict`.
- The input `record` is a dictionary where keys are source column names.
- The output must be a dictionary matching the Target Schema keys.
- Handle data type conversion (strings to floats/decimals, dates to ISO8601 strings).
- Handle missing values gracefully (.get() or check for None).
- Clean strings (strip whitespace).
- If a target field cannot be mapped, set it to None.
- **Do not use external libraries** other than standard library (datetime, re, json, decimal).
- Valid Python 3.9+ code ONLY. Code should be wrapped in ```python ... ``` block.

## Instructions for Schema Inference:
- return a JSON object listing columns, inferred types (string, integer, decimal, date, boolean), and a brief description/semantic meaning.
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        # Determine task based on metadata
        task = context.metadata.get("task", "infer_schema")
        
        if task == "infer_schema":
            return self._get_inference_prompt(context)
        elif task == "generate_mapping":
            return self._get_mapping_prompt(context)
        else:
            return f"Unknown task: {task}. Please specify 'infer_schema' or 'generate_mapping'."

    def _get_inference_prompt(self, context: AgentContext) -> str:
        """Prompt for inferring schema from data."""
        return f"""Task: Infer Schema
Please analyze the following data sample and infer the schema.

**Filename:** {context.filename}
**File Type:** {context.file_type}

**Data Sample (JSON/CSV representation):**
{context.content[:4000]}

**Output Format (JSON):**
{{
    "columns": [
        {{
            "name": "column_name",
            "inferred_type": "string|integer|decimal|date|boolean",
            "description": "Semantic meaning of the column",
            "confidence": 0.95
        }}
    ],
    "suggested_entity_type": "invoice|shipment|product|other"
}}"""

    def _get_mapping_prompt(self, context: AgentContext) -> str:
        """Prompt for generating mapping code."""
        target_schema = context.metadata.get("target_schema", {})
        target_schema_str = json.dumps(target_schema, indent=2)
        
        return f"""Task: Generate Mapping Code
        
**Goal:** Map the source data to the target schema using a Python function.

**Source Data Sample:**
{context.content[:2000]}

**Target Schema (JSON Schema-like definition):**
{target_schema_str}

**Requirements:**
- Write a function `transform_record(record)` that takes a source record dict and returns a target record dict.
- Ensure all target keys are present (use None if missing).
- Perform necessary casting (e.g. monetary strings '$1,200.00' -> Decimal(1200.00)).
- Parse dates to 'YYYY-MM-DD' format.
- Output ONLY valid Python code inside a code block.
"""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        """Parse response based on task."""
        result = {"raw_response": response}
        
        # Clean markdown code blocks
        clean_response = response.strip()
        
        try:
            # Check if this is a code response (for mapping generation)
            if "def transform_record" in clean_response:
                # Extract code block
                if "```python" in clean_response:
                    code_block = clean_response.split("```python")[1].split("```")[0].strip()
                elif "```" in clean_response:
                    code_block = clean_response.split("```")[1].split("```")[0].strip()
                else:
                    # Heuristic: Find specific function definition
                    start = clean_response.find("def transform_record")
                    code_block = clean_response[start:]
                
                result["generated_code"] = code_block
                result["type"] = "mapping_code"
                return result

            # Otherwise assume JSON (for inference)
            if clean_response.startswith("```"):
                 # Strip any markdown code block indicators
                lines = clean_response.split("\n")
                if lines[0].startswith("```"):
                    clean_response = "\n".join(lines[1:])
                if clean_response.endswith("```"):
                     clean_response = clean_response.rsplit("```", 1)[0]
                
            json_start = clean_response.find("{")
            json_end = clean_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = clean_response[json_start:json_end]
                parsed = json.loads(json_str)
                result.update(parsed)
                result["type"] = "schema_inference"
        
        except Exception as e:
            logger.error(f"Failed to parse response from SchemaMappingAgent: {e}")
            result["error"] = str(e)
            
        return result
