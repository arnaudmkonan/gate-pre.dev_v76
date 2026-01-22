"""
Summarization Agent.

This agent creates intelligent summaries of documents using LLM reasoning.
It can generate different types of summaries based on the document type
and user requirements.
"""

import json
import logging
from typing import Dict, Any, List

from app.agents.base_agent import BaseAgent, AgentContext

logger = logging.getLogger(__name__)


class SummarizationAgent(BaseAgent):
    """
    Agent that creates intelligent document summaries.
    
    Capabilities:
    - Creates executive summaries for business documents
    - Generates technical abstracts for documentation
    - Produces action item lists from meeting notes
    - Creates TL;DR summaries with key points
    - Adapts summary style to document type
    """
    
    SUMMARY_STYLES = {
        "executive": "High-level summary for executives, focusing on key decisions and impacts",
        "technical": "Detailed technical summary with specifications and implementation details",
        "bullet_points": "Key points as a bulleted list",
        "abstract": "Academic-style abstract summarizing purpose, methods, and conclusions",
        "action_items": "Focus on action items, deadlines, and responsibilities",
        "tldr": "Very brief 1-2 sentence summary",
    }
    
    def __init__(self, summary_style: str = "executive"):
        super().__init__(
            name="summarizer",
            description="Creates intelligent summaries of documents",
            model="gpt-4o-mini",
            temperature=0.3,  # Slightly creative for natural summaries
            max_tokens=2000,
        )
        
        self.summary_style = summary_style if summary_style in self.SUMMARY_STYLES else "executive"
    
    def get_system_prompt(self) -> str:
        style_desc = self.SUMMARY_STYLES[self.summary_style]
        
        return f"""You are an expert document summarization agent. You create clear, accurate, and useful summaries.

## Summary Style: {self.summary_style.upper()}
{style_desc}

## Instructions:
1. Read and understand the document thoroughly
2. Identify the main purpose and key information
3. Extract the most important points
4. Write a summary that captures the essence of the document
5. Adapt your language to match the summary style
6. Include any critical dates, numbers, or decisions
7. Keep the summary concise but comprehensive

## Output Format (JSON):
{{
    "title": "Generated title for the document",
    "summary": "The main summary text",
    "key_points": ["point 1", "point 2", "point 3"],
    "word_count": 150,
    "important_dates": ["2025-01-15: deadline for X"],
    "key_figures": ["$50,000 budget", "100 employees"],
    "action_items": ["Action 1", "Action 2"],
    "tone": "formal/informal/technical/urgent"
}}
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        # Use classification if available
        doc_type = ""
        if "document_classifier" in context.previous_results:
            cat = context.previous_results["document_classifier"].get("output", {})
            doc_type = f"\n**Document Category:** {cat.get('category', 'unknown')}"
            doc_type += f"\n**Classification Reasoning:** {cat.get('reasoning', '')}"
        
        return f"""Summarize this document:

**Filename:** {context.filename}
**File Type:** {context.file_type}{doc_type}

**Document Content:**
{context.content[:6000]}

{"[Content truncated - document continues...]" if len(context.content) > 6000 else ""}

Create a {self.summary_style} summary."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(response)
            
            return {
                "title": result.get("title", context.filename),
                "summary": result.get("summary", ""),
                "key_points": result.get("key_points", []),
                "word_count": len(result.get("summary", "").split()),
                "important_dates": result.get("important_dates", []),
                "key_figures": result.get("key_figures", []),
                "action_items": result.get("action_items", []),
                "tone": result.get("tone", "formal"),
                "summary_style": self.summary_style,
            }
            
        except json.JSONDecodeError:
            # Return raw text if JSON parsing fails
            return {
                "title": context.filename,
                "summary": response[:2000],
                "key_points": [],
                "word_count": len(response.split()),
                "important_dates": [],
                "key_figures": [],
                "action_items": [],
                "tone": "unknown",
                "summary_style": self.summary_style,
            }


class QAGenerationAgent(BaseAgent):
    """
    Agent that generates Q&A pairs from documents.
    
    Creates question-answer pairs that can be used for:
    - FAQ generation
    - Knowledge base creation
    - Training data for retrieval systems
    """
    
    def __init__(self, num_questions: int = 5):
        super().__init__(
            name="qa_generator",
            description="Generates question-answer pairs from documents",
            model="gpt-4o-mini",
            temperature=0.4,
            max_tokens=2500,
        )
        
        self.num_questions = num_questions
    
    def get_system_prompt(self) -> str:
        return f"""You are a Q&A generation agent. You create useful question-answer pairs from documents.

## Instructions:
1. Generate {self.num_questions} diverse questions about the document
2. Include a mix of:
   - Factual questions (who, what, when, where)
   - Explanatory questions (why, how)
   - Summarization questions ("What is the main point of...")
3. Ensure answers are directly supported by the document
4. Make questions specific enough to be useful
5. Include the text span that contains the answer

## Output Format (JSON):
{{
    "qa_pairs": [
        {{
            "question": "What is the total budget for the project?",
            "answer": "The total budget is $50,000 as stated in section 3.",
            "answer_span": "total budget of $50,000",
            "question_type": "factual",
            "difficulty": "easy"
        }}
    ],
    "document_coverage": 0.8
}}
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        return f"""Generate Q&A pairs from this document:

**Filename:** {context.filename}

**Content:**
{context.content[:5000]}

Generate {self.num_questions} question-answer pairs."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(response)
            
            qa_pairs = []
            for qa in result.get("qa_pairs", []):
                qa_pairs.append({
                    "question": qa.get("question", ""),
                    "answer": qa.get("answer", ""),
                    "answer_span": qa.get("answer_span", ""),
                    "question_type": qa.get("question_type", "factual"),
                    "difficulty": qa.get("difficulty", "medium"),
                })
            
            return {
                "qa_pairs": qa_pairs,
                "question_count": len(qa_pairs),
                "document_coverage": result.get("document_coverage", 0.5),
            }
            
        except json.JSONDecodeError:
            return {
                "qa_pairs": [],
                "question_count": 0,
                "document_coverage": 0,
            }


class KeyInsightsAgent(BaseAgent):
    """
    Agent that extracts key insights and takeaways from documents.
    
    Goes beyond summarization to identify:
    - Strategic implications
    - Risks and opportunities
    - Recommendations
    - Trends and patterns
    """
    
    def __init__(self):
        super().__init__(
            name="insights_extractor",
            description="Extracts key insights and strategic takeaways",
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=2000,
        )
    
    def get_system_prompt(self) -> str:
        return """You are a strategic insights agent. You analyze documents to extract valuable insights beyond surface-level information.

## Instructions:
1. Identify key insights that aren't immediately obvious
2. Analyze implications for business or operations
3. Identify potential risks mentioned or implied
4. Spot opportunities that could be leveraged
5. Note any trends or patterns
6. Suggest actionable recommendations

## Output Format (JSON):
{
    "key_insights": [
        {
            "insight": "The insight statement",
            "category": "opportunity|risk|trend|implication",
            "importance": "high|medium|low",
            "evidence": "Supporting quote or reference"
        }
    ],
    "risks": ["Risk 1", "Risk 2"],
    "opportunities": ["Opportunity 1", "Opportunity 2"],
    "recommendations": [
        {
            "recommendation": "What to do",
            "priority": "high|medium|low",
            "rationale": "Why this is recommended"
        }
    ],
    "sentiment": "positive|negative|neutral|mixed"
}
"""

    def get_user_prompt(self, context: AgentContext) -> str:
        # Include previous agent results for richer analysis
        previous = ""
        if context.previous_results:
            if "document_classifier" in context.previous_results:
                cat = context.previous_results["document_classifier"].get("output", {})
                previous += f"\n- Category: {cat.get('category', 'unknown')}"
            if "summarizer" in context.previous_results:
                summary = context.previous_results["summarizer"].get("output", {})
                previous += f"\n- Summary: {summary.get('summary', '')[:300]}"
        
        context_info = f"\n**Previous Analysis:**{previous}" if previous else ""
        
        return f"""Extract strategic insights from this document:

**Filename:** {context.filename}{context_info}

**Content:**
{context.content[:5000]}

Analyze for insights, risks, opportunities, and recommendations."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        try:
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(response)
            
            return {
                "key_insights": result.get("key_insights", []),
                "insight_count": len(result.get("key_insights", [])),
                "risks": result.get("risks", []),
                "opportunities": result.get("opportunities", []),
                "recommendations": result.get("recommendations", []),
                "sentiment": result.get("sentiment", "neutral"),
            }
            
        except json.JSONDecodeError:
            return {
                "key_insights": [],
                "insight_count": 0,
                "risks": [],
                "opportunities": [],
                "recommendations": [],
                "sentiment": "unknown",
            }
