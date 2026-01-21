"""
Routing service for file-to-agent delegation.
Implements precedence logic: extension → MIME → content sniffer → fallback.
"""

import logging
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_registry_service import AgentRegistryService
from app.utils.content_sniffer import sniff_file_type, get_canonical_type
from app.models.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)


class RoutingDecision:
    """Represents a routing decision."""

    def __init__(
        self,
        agent: AgentRegistry,
        file_type: str,
        confidence: float,
        decision_method: str,
    ):
        self.agent = agent
        self.file_type = file_type
        self.confidence = confidence
        self.decision_method = decision_method  # "extension", "mime", "sniffer", "fallback"


class RouterService:
    """Service for routing files to appropriate agents."""

    # Precedence order for routing methods
    PRECEDENCE = {
        "extension": 1,
        "mime": 2,
        "sniffer": 3,
        "fallback": 4,
    }

    @staticmethod
    async def route_file(
        session: AsyncSession,
        filename: str,
        file_content: bytes,
        mime_type: Optional[str] = None,
    ) -> Optional[RoutingDecision]:
        """
        Route file to appropriate agent based on precedence logic.

        Precedence:
        1. File extension (highest)
        2. MIME type
        3. Content sniffer
        4. Fallback agent (lowest)

        Args:
            session: Database session
            filename: Original filename with extension
            file_content: Raw file bytes
            mime_type: Optional MIME type from request headers

        Returns:
            RoutingDecision with selected agent and confidence, or None if no match
        """
        # Extract extension
        extension = None
        if "." in filename:
            extension = filename.rsplit(".", 1)[-1].lower()

        decisions = {}

        # Method 1: Extension matching (highest priority)
        if extension:
            agents = await AgentRegistryService.get_agents_by_extension(
                session, extension
            )
            if agents:
                agent = RouterService._select_best_agent(agents)
                decisions["extension"] = RoutingDecision(
                    agent=agent,
                    file_type=extension,
                    confidence=0.95,
                    decision_method="extension",
                )

        # Method 2: MIME type matching
        if mime_type:
            agents = await AgentRegistryService.get_agents_by_mime_type(
                session, mime_type
            )
            if agents:
                agent = RouterService._select_best_agent(agents)
                decisions["mime"] = RoutingDecision(
                    agent=agent,
                    file_type=mime_type,
                    confidence=0.85,
                    decision_method="mime",
                )

        # Method 3: Content sniffer
        if extension or mime_type:  # Only sniff if we have some hint
            detected_type, sniff_confidence = sniff_file_type(
                file_content, filename, mime_type
            )
            if detected_type and sniff_confidence > 0.5:
                canonical = get_canonical_type(detected_type)
                agents = await AgentRegistryService.get_agents_by_extension(
                    session, canonical
                )
                if agents:
                    agent = RouterService._select_best_agent(agents)
                    decisions["sniffer"] = RoutingDecision(
                        agent=agent,
                        file_type=canonical,
                        confidence=sniff_confidence,
                        decision_method="sniffer",
                    )

        # Fallback: Get any active agent
        if not decisions:
            agents = await AgentRegistryService.list_agents(
                session, status="active"
            )
            if agents:
                agent = RouterService._select_best_agent(agents)
                decisions["fallback"] = RoutingDecision(
                    agent=agent,
                    file_type="unknown",
                    confidence=0.30,
                    decision_method="fallback",
                )

        if not decisions:
            logger.warning(f"No agents available for routing file: {filename}")
            return None

        # Select highest precedence decision
        best_decision = max(
            decisions.values(),
            key=lambda d: RouterService.PRECEDENCE[d.decision_method],
        )

        logger.info(
            f"Routed file {filename} to agent {best_decision.agent.agent_id} "
            f"(method={best_decision.decision_method}, confidence={best_decision.confidence:.2f})"
        )

        return best_decision

    @staticmethod
    def _select_best_agent(agents: list) -> AgentRegistry:
        """
        Select best agent from list based on priority.

        Args:
            agents: List of AgentRegistry objects

        Returns:
            Selected agent
        """
        if not agents:
            return None

        # Priority order
        priority_order = {"high": 0, "normal": 1, "low": 2}

        best = agents[0]
        for agent in agents[1:]:
            agent_priority = priority_order.get(agent.priority, 999)
            best_priority = priority_order.get(best.priority, 999)

            if agent_priority < best_priority:
                best = agent

        return best

    @staticmethod
    async def get_routing_candidates(
        session: AsyncSession,
        filename: str,
        file_content: bytes,
        mime_type: Optional[str] = None,
    ) -> dict:
        """
        Get all candidate agents and their scores for a file.
        Useful for admin override UI.

        Args:
            session: Database session
            filename: Original filename
            file_content: Raw file bytes
            mime_type: Optional MIME type

        Returns:
            Dict with candidates by method:
            {
                'extension': [{'agent': AgentRegistry, 'confidence': 0.95}, ...],
                'mime': [...],
                'sniffer': [...],
                'fallback': [...]
            }
        """
        candidates = {}

        extension = None
        if "." in filename:
            extension = filename.rsplit(".", 1)[-1].lower()

        # Extension candidates
        if extension:
            agents = await AgentRegistryService.get_agents_by_extension(
                session, extension
            )
            candidates["extension"] = [
                {"agent": a, "confidence": 0.95, "type": extension} for a in agents
            ]

        # MIME candidates
        if mime_type:
            agents = await AgentRegistryService.get_agents_by_mime_type(
                session, mime_type
            )
            candidates["mime"] = [
                {"agent": a, "confidence": 0.85, "type": mime_type} for a in agents
            ]

        # Sniffer candidates
        detected_type, sniff_confidence = sniff_file_type(
            file_content, filename, mime_type
        )
        if detected_type and sniff_confidence > 0.5:
            canonical = get_canonical_type(detected_type)
            agents = await AgentRegistryService.get_agents_by_extension(
                session, canonical
            )
            candidates["sniffer"] = [
                {"agent": a, "confidence": sniff_confidence, "type": canonical}
                for a in agents
            ]

        # Fallback candidates
        agents = await AgentRegistryService.list_agents(session, status="active")
        candidates["fallback"] = [
            {"agent": a, "confidence": 0.30, "type": "unknown"} for a in agents
        ]

        return candidates
