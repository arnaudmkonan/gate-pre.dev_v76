"""
Quality Review Agent.

This agent reviews the quality of document processing and provides
validation, scoring, and improvement suggestions.
"""

import json
import logging
from typing import Dict, Any, List

from app.agents.base_agent import BaseAgent, AgentContext

logger = logging.getLogger(__name__)


class QualityReviewAgent(BaseAgent):
    """
    Agent that reviews and validates document processing quality.
    
    Capabilities:
    - Validates extracted entities for accuracy
    - Checks summary completeness
    - Identifies potential errors or omissions
    - Provides quality scores
    - Suggests improvements
    """
    
    def __init__(self):
        super().__init__(
            name="quality_reviewer",
            description="Reviews and validates document processing quality",
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=2000,
        )
    
    def get_system_prompt(self) -> str:
        return """You are a quality assurance agent for document processing. You review the work of other agents and ensure accuracy.

## Your Responsibilities:
1. Verify entity extractions are accurate and complete
2. Check if summaries capture key information
3. Validate classification decisions
4. Identify any errors or inconsistencies
5. Suggest improvements

## Scoring Criteria:
- **Accuracy**: Are extractions correct?
- **Completeness**: Is anything important missing?
- **Consistency**: Do results align with each other?
- **Relevance**: Are the outputs useful?

## Output Format (JSON):
{
    "overall_score": 0.85,
    "accuracy_score": 0.9,
    "completeness_score": 0.8,
    "consistency_score": 0.85,
    "issues": [
        {
            "type": "missing_entity|incorrect_value|inconsistency|other",
            "description": "Description of the issue",
            "severity": "high|medium|low",
            "suggestion": "How to fix or improve"
        }
    ],
    "validation_summary": "Brief summary of quality assessment",
    "approved": true,
    "requires_human_review": false,
    "human_review_reason": ""
}
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        # Compile previous results for review
        previous_results = {}
        for agent_name, result in context.previous_results.items():
            if isinstance(result, dict) and "output" in result:
                previous_results[agent_name] = result["output"]
        
        results_str = json.dumps(previous_results, indent=2, default=str)
        
        return f"""Review the quality of document processing:

**Original Document:**
Filename: {context.filename}
Content (first 2000 chars):
{context.content[:2000]}

**Processing Results to Review:**
{results_str}

Evaluate accuracy, completeness, and consistency. Identify any issues."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(response)
            
            return {
                "overall_score": min(max(float(result.get("overall_score", 0.5)), 0), 1),
                "accuracy_score": min(max(float(result.get("accuracy_score", 0.5)), 0), 1),
                "completeness_score": min(max(float(result.get("completeness_score", 0.5)), 0), 1),
                "consistency_score": min(max(float(result.get("consistency_score", 0.5)), 0), 1),
                "issues": result.get("issues", []),
                "issue_count": len(result.get("issues", [])),
                "validation_summary": result.get("validation_summary", ""),
                "approved": result.get("approved", False),
                "requires_human_review": result.get("requires_human_review", False),
                "human_review_reason": result.get("human_review_reason", ""),
            }
            
        except json.JSONDecodeError:
            return {
                "overall_score": 0.5,
                "accuracy_score": 0.5,
                "completeness_score": 0.5,
                "consistency_score": 0.5,
                "issues": [{"type": "other", "description": "Failed to parse QA response", "severity": "medium"}],
                "issue_count": 1,
                "validation_summary": "Quality review parsing failed",
                "approved": False,
                "requires_human_review": True,
                "human_review_reason": "Automated quality review failed",
            }


class ComplianceCheckAgent(BaseAgent):
    """
    Agent that checks documents for compliance requirements.
    
    Capabilities:
    - Checks for required fields/sections
    - Validates against regulatory patterns
    - Identifies sensitive data handling
    - Verifies document structure
    """
    
    COMPLIANCE_CHECKS = {
        "pii_handling": "Check for proper handling of personally identifiable information",
        "data_classification": "Verify document has proper classification markings",
        "retention_policy": "Check for retention/expiration dates if required",
        "signature_requirements": "Verify required signatures are present",
        "regulatory_references": "Check for required regulatory citations",
    }
    
    def __init__(self, enabled_checks: List[str] = None):
        super().__init__(
            name="compliance_checker",
            description="Checks documents for compliance with requirements",
            model="gpt-4o-mini",
            temperature=0.0,
            max_tokens=2000,
        )
        
        self.enabled_checks = enabled_checks or list(self.COMPLIANCE_CHECKS.keys())
    
    def get_system_prompt(self) -> str:
        checks_str = "\n".join([f"- {k}: {v}" for k, v in self.COMPLIANCE_CHECKS.items() 
                                if k in self.enabled_checks])
        
        return f"""You are a compliance checking agent. You verify documents meet required standards.

## Checks to Perform:
{checks_str}

## Instructions:
1. Examine the document for each compliance requirement
2. Note whether each check passes, fails, or is not applicable
3. Identify any compliance risks
4. Suggest remediation for failures

## Output Format (JSON):
{{
    "compliance_results": [
        {{
            "check": "pii_handling",
            "status": "pass|fail|not_applicable",
            "findings": "Description of what was found",
            "risk_level": "high|medium|low|none",
            "remediation": "How to fix if failed"
        }}
    ],
    "overall_compliance": true,
    "risk_summary": "Summary of compliance risks",
    "critical_issues": ["List of critical issues"],
    "recommendations": ["Recommendation 1", "Recommendation 2"]
}}
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        doc_category = "unknown"
        if "document_classifier" in context.previous_results:
            doc_category = context.previous_results["document_classifier"].get("output", {}).get("category", "unknown")
        
        return f"""Check this document for compliance:

**Document:** {context.filename}
**Category:** {doc_category}

**Content:**
{context.content[:4000]}

Perform compliance checks and report findings."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(response)
            
            compliance_results = result.get("compliance_results", [])
            passed = sum(1 for r in compliance_results if r.get("status") == "pass")
            failed = sum(1 for r in compliance_results if r.get("status") == "fail")
            
            return {
                "compliance_results": compliance_results,
                "checks_passed": passed,
                "checks_failed": failed,
                "overall_compliance": result.get("overall_compliance", failed == 0),
                "risk_summary": result.get("risk_summary", ""),
                "critical_issues": result.get("critical_issues", []),
                "recommendations": result.get("recommendations", []),
            }
            
        except json.JSONDecodeError:
            return {
                "compliance_results": [],
                "checks_passed": 0,
                "checks_failed": 0,
                "overall_compliance": False,
                "risk_summary": "Failed to complete compliance check",
                "critical_issues": ["Compliance check failed to execute"],
                "recommendations": ["Re-run compliance check"],
            }
