"""
LLM-Powered Agent Framework for Document Processing.

This module provides a base agent class and utilities for creating
autonomous AI agents that can reason about documents, extract information,
and make decisions using LLM capabilities.
"""

import logging
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from uuid import UUID
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Context passed to agents during execution."""
    
    document_id: str
    filename: str
    file_type: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    previous_results: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "content_length": len(self.content),
            "content_preview": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "metadata": self.metadata,
        }


@dataclass
class AgentResult:
    """Result from an agent execution."""
    
    agent_name: str
    success: bool
    output: Dict[str, Any]
    reasoning: Optional[str] = None
    confidence: float = 0.0
    tokens_used: int = 0
    execution_time_ms: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "success": self.success,
            "output": self.output,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "tokens_used": self.tokens_used,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


@dataclass
class Tool:
    """A tool that an agent can use."""
    
    name: str
    description: str
    function: Callable
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class BaseAgent(ABC):
    """
    Base class for LLM-powered agents.
    
    Agents are autonomous entities that can:
    - Analyze document content using LLM reasoning
    - Use tools to gather additional information
    - Make decisions based on their analysis
    - Chain with other agents for complex workflows
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ):
        self.name = name
        self.description = description
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools: List[Tool] = []
        self._client = None
        
    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=settings.openai_api_key)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise
        return self._client
    
    def register_tool(self, tool: Tool):
        """Register a tool for this agent to use."""
        self.tools.append(tool)
        logger.info(f"Agent {self.name} registered tool: {tool.name}")
        
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        pass
    
    @abstractmethod
    def get_user_prompt(self, context: AgentContext) -> str:
        """Get the user prompt for a specific context."""
        pass
    
    @abstractmethod
    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        """Parse the LLM response into structured output."""
        pass
    
    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute the agent on the given context.
        
        This method:
        1. Builds prompts from context
        2. Calls the LLM
        3. Handles tool calls if needed
        4. Parses and returns the result
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            system_prompt = self.get_system_prompt()
            user_prompt = self.get_user_prompt(context)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            
            # Prepare tools for OpenAI
            tools_param = None
            if self.tools:
                tools_param = [t.to_openai_format() for t in self.tools]
            
            # Call LLM
            response = await asyncio.to_thread(
                self._call_llm,
                messages=messages,
                tools=tools_param,
            )
            
            # Handle tool calls if any
            if response.get("tool_calls"):
                response = await self._handle_tool_calls(
                    response["tool_calls"],
                    messages,
                    context,
                )
            
            # Parse response
            content = response.get("content", "")
            output = self.parse_response(content, context)
            
            execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            return AgentResult(
                agent_name=self.name,
                success=True,
                output=output,
                reasoning=response.get("reasoning"),
                confidence=output.get("confidence", 0.8),
                tokens_used=response.get("tokens_used", 0),
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            logger.error(f"Agent {self.name} execution failed: {e}")
            execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return AgentResult(
                agent_name=self.name,
                success=False,
                output={},
                error=str(e),
                execution_time_ms=execution_time,
            )
    
    def _call_llm(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Call the LLM with messages and optional tools."""
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**kwargs)
            
            message = response.choices[0].message
            
            result = {
                "content": message.content or "",
                "tokens_used": response.usage.total_tokens if response.usage else 0,
            }
            
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in message.tool_calls
                ]
            
            return result
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    async def _handle_tool_calls(
        self,
        tool_calls: List[Dict],
        messages: List[Dict],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Handle tool calls from the LLM."""
        # Add assistant message with tool calls
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    }
                }
                for tc in tool_calls
            ]
        })
        
        # Execute each tool and add results
        for tc in tool_calls:
            tool = next((t for t in self.tools if t.name == tc["name"]), None)
            
            if tool:
                try:
                    args = json.loads(tc["arguments"])
                    result = await asyncio.to_thread(tool.function, **args)
                    tool_result = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                except Exception as e:
                    tool_result = f"Error executing tool: {e}"
            else:
                tool_result = f"Unknown tool: {tc['name']}"
            
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })
        
        # Call LLM again with tool results
        return self._call_llm(messages)


class AgentOrchestrator:
    """
    Orchestrates multiple agents in a pipeline.
    
    Can run agents:
    - Sequentially: Each agent sees previous results
    - In parallel: Agents run independently
    - Conditionally: Based on previous results
    """
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.pipeline: List[str] = []
        
    def register_agent(self, agent: BaseAgent):
        """Register an agent with the orchestrator."""
        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")
        
    def set_pipeline(self, agent_names: List[str]):
        """Set the execution pipeline order."""
        self.pipeline = agent_names
        
    async def execute_pipeline(self, context: AgentContext) -> Dict[str, AgentResult]:
        """Execute all agents in the pipeline sequentially."""
        results = {}
        current_context = context
        
        for agent_name in self.pipeline:
            agent = self.agents.get(agent_name)
            if not agent:
                logger.warning(f"Agent not found: {agent_name}")
                continue
                
            logger.info(f"Executing agent: {agent_name}")
            result = await agent.execute(current_context)
            results[agent_name] = result
            
            # Add result to context for next agent
            current_context.previous_results[agent_name] = result.to_dict()
            
            # Stop if agent failed and it's critical
            if not result.success and agent_name in ["classifier", "quality_reviewer"]:
                logger.warning(f"Critical agent {agent_name} failed, stopping pipeline")
                break
        
        return results
    
    async def execute_parallel(
        self,
        context: AgentContext,
        agent_names: Optional[List[str]] = None,
    ) -> Dict[str, AgentResult]:
        """Execute specified agents in parallel."""
        names = agent_names or list(self.agents.keys())
        
        tasks = []
        for name in names:
            agent = self.agents.get(name)
            if agent:
                tasks.append((name, agent.execute(context)))
        
        results = {}
        for name, task in tasks:
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Agent {name} failed: {e}")
                results[name] = AgentResult(
                    agent_name=name,
                    success=False,
                    output={},
                    error=str(e),
                )
        
        return results
