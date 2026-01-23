"""
LLM-Powered Agent Framework for Document Processing.

This package provides autonomous AI agents that use LLM capabilities
to intelligently process, analyze, and extract insights from documents.

## Available Agents:

### Classification
- DocumentClassifierAgent: Categorizes documents into predefined types
### Classification
- DocumentClassifierAgent: Categorizes documents into predefined types
- MultiLabelClassifierAgent: Assigns multiple labels to documents
- TriagistAgent: Routes files to optimal processing path (A/B/C)

### Entity Extraction
- EntityExtractionAgent: Extracts structured entities (people, orgs, dates, etc.)
- RelationshipExtractionAgent: Identifies relationships between entities

### Summarization
- SummarizationAgent: Creates intelligent summaries
- QAGenerationAgent: Generates Q&A pairs from documents
- KeyInsightsAgent: Extracts strategic insights

### Quality Assurance
- QualityReviewAgent: Validates processing quality
- ComplianceCheckAgent: Checks compliance requirements

## Usage:

```python
from app.agents import (
    AgentOrchestrator,
    AgentContext,
    DocumentClassifierAgent,
    EntityExtractionAgent,
    SummarizationAgent,
    QualityReviewAgent,
)

# Create orchestrator with agents
orchestrator = AgentOrchestrator()
orchestrator.register_agent(DocumentClassifierAgent())
orchestrator.register_agent(EntityExtractionAgent())
orchestrator.register_agent(SummarizationAgent())
orchestrator.register_agent(QualityReviewAgent())

# Set pipeline order
orchestrator.set_pipeline([
    "document_classifier",
    "entity_extractor", 
    "summarizer",
    "quality_reviewer",
])

# Process a document
context = AgentContext(
    document_id="doc-123",
    filename="contract.pdf",
    file_type="pdf",
    content="Document content here...",
)

results = await orchestrator.execute_pipeline(context)
```
"""

# Base framework
from app.agents.base_agent import (
    BaseAgent,
    AgentContext,
    AgentResult,
    Tool,
    AgentOrchestrator,
)

# Classification agents
from app.agents.classifier_agent import (
    DocumentClassifierAgent,
    MultiLabelClassifierAgent,
    DOCUMENT_CATEGORIES,
)
from app.agents.triagist_agent import TriagistAgent


# Entity extraction agents
from app.agents.entity_agent import (
    EntityExtractionAgent,
    RelationshipExtractionAgent,
    Entity,
)

# Summarization agents
from app.agents.summarization_agent import (
    SummarizationAgent,
    QAGenerationAgent,
    KeyInsightsAgent,
)

# Quality assurance agents
from app.agents.quality_agent import (
    QualityReviewAgent,
    ComplianceCheckAgent,
)

# Template-based extraction agents
from app.agents.template_agent import (
    TemplateMatchingAgent,
    TemplateExtractionAgent,
)


# Schema Mapping Agent
from app.agents.schema_mapping_agent import SchemaMappingAgent


__all__ = [
    # Base
    "BaseAgent",
    "AgentContext",
    "AgentResult",
    "Tool",
    "AgentOrchestrator",
    # Classification
    "DocumentClassifierAgent",
    "MultiLabelClassifierAgent",
    "TriagistAgent",
    "DOCUMENT_CATEGORIES",
    # Entity Extraction
    "EntityExtractionAgent",
    "RelationshipExtractionAgent",
    "Entity",
    # Summarization
    "SummarizationAgent",
    "QAGenerationAgent",
    "KeyInsightsAgent",
    # Quality
    "QualityReviewAgent",
    "ComplianceCheckAgent",
    # Template-based extraction
    "TemplateMatchingAgent",
    "TemplateExtractionAgent",
    # Schema Mapping
    "SchemaMappingAgent",
    # Preconfigured
    "create_standard_pipeline",
    "create_analysis_pipeline",
    "create_mapping_pipeline",
    "create_triage_pipeline",
]



def create_standard_pipeline() -> AgentOrchestrator:
    """
    Create a standard document processing pipeline.
    
    Pipeline:
    1. Classify the document
    2. Extract entities
    3. Generate summary
    4. Review quality
    
    Returns:
        Configured AgentOrchestrator ready to process documents.
    """
    orchestrator = AgentOrchestrator()
    
    # Register agents
    orchestrator.register_agent(DocumentClassifierAgent())
    orchestrator.register_agent(EntityExtractionAgent())
    orchestrator.register_agent(SummarizationAgent(summary_style="executive"))
    orchestrator.register_agent(QualityReviewAgent())
    
    # Set pipeline order
    orchestrator.set_pipeline([
        "document_classifier",
        "entity_extractor",
        "summarizer",
        "quality_reviewer",
    ])
    
    return orchestrator


def create_analysis_pipeline() -> AgentOrchestrator:
    """
    Create an in-depth analysis pipeline.
    
    Pipeline:
    1. Classify and label the document
    2. Extract entities and relationships
    3. Generate summary and insights
    4. Generate Q&A pairs
    5. Check compliance
    6. Final quality review
    
    Returns:
        Configured AgentOrchestrator for deep analysis.
    """
    orchestrator = AgentOrchestrator()
    
    # Register all agents
    orchestrator.register_agent(DocumentClassifierAgent())
    orchestrator.register_agent(MultiLabelClassifierAgent())
    orchestrator.register_agent(EntityExtractionAgent())
    orchestrator.register_agent(RelationshipExtractionAgent())
    orchestrator.register_agent(SummarizationAgent(summary_style="executive"))
    orchestrator.register_agent(KeyInsightsAgent())
    orchestrator.register_agent(QAGenerationAgent(num_questions=5))
    orchestrator.register_agent(ComplianceCheckAgent())
    orchestrator.register_agent(QualityReviewAgent())
    
    # Set comprehensive pipeline
    orchestrator.set_pipeline([
        "document_classifier",
        "multi_label_classifier",
        "entity_extractor",
        "relationship_extractor",
        "summarizer",
        "insights_extractor",
        "qa_generator",
        "compliance_checker",
        "quality_reviewer",
    ])
    
    return orchestrator


def create_mapping_pipeline() -> AgentOrchestrator:
    """
    Create a pipeline for Path B (Schema Mapping).
    
    Pipeline:
    1. Schema Mapping Agent
    
    Returns:
        Configured AgentOrchestrator.
    """
    orchestrator = AgentOrchestrator()
    orchestrator.register_agent(SchemaMappingAgent())
    orchestrator.set_pipeline(["schema_mapping_agent"])
    return orchestrator


def create_triage_pipeline() -> AgentOrchestrator:
    """
    Create a pipeline for document triage.
    
    Pipeline:
    1. Triagist Agent (Path Selection & Priority)
    
    Returns:
        Configured AgentOrchestrator.
    """
    orchestrator = AgentOrchestrator()
    orchestrator.register_agent(TriagistAgent())
    orchestrator.set_pipeline(["triagist_agent"])
    return orchestrator

