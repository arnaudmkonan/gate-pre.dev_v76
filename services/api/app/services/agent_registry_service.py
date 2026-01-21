"""
Service for managing agent registry and agent discovery.
Handles agent registration, lookup by file type/MIME, and status management.
"""

import logging
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_registry import AgentRegistry, AgentStatus

logger = logging.getLogger(__name__)


class AgentRegistryService:
    """Service for managing agent registry and discovery."""

    @staticmethod
    async def register_agent(
        session: AsyncSession,
        agent_id: str,
        agent_name: str,
        handler_name: str,
        file_extensions: List[str],
        mime_types: List[str],
        priority: str = "normal",
        metadata: Optional[dict] = None,
        supports_content_sniffer: bool = False,
    ) -> AgentRegistry:
        """
        Register a new agent in the registry.

        Args:
            session: Database session
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            handler_name: Name of handler method/function
            file_extensions: List of supported file extensions
            mime_types: List of supported MIME types
            priority: Agent priority (low, normal, high)
            metadata: Optional agent-specific configuration
            supports_content_sniffer: Whether agent supports content sniffing

        Returns:
            Created AgentRegistry record
        """
        try:
            agent = AgentRegistry(
                agent_id=agent_id,
                agent_name=agent_name,
                handler_name=handler_name,
                file_extensions=file_extensions,
                mime_types=mime_types,
                priority=priority,
                metadata=metadata or {},
                supports_content_sniffer=supports_content_sniffer,
                status=AgentStatus.ACTIVE,
            )
            session.add(agent)
            await session.commit()
            logger.info(f"Registered agent: {agent_id}")
            return agent
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to register agent {agent_id}: {e}")
            raise

    @staticmethod
    async def list_agents(
        session: AsyncSession,
        status: Optional[str] = None,
    ) -> List[AgentRegistry]:
        """
        List all agents, optionally filtered by status.

        Args:
            session: Database session
            status: Optional status filter

        Returns:
            List of AgentRegistry records
        """
        try:
            query = select(AgentRegistry)
            if status:
                query = query.where(AgentRegistry.status == status)
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            raise

    @staticmethod
    async def get_agent_by_id(
        session: AsyncSession,
        agent_id: str,
    ) -> Optional[AgentRegistry]:
        """
        Get agent by ID.

        Args:
            session: Database session
            agent_id: Agent identifier

        Returns:
            AgentRegistry record or None if not found
        """
        try:
            query = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            raise

    @staticmethod
    async def get_agents_by_extension(
        session: AsyncSession,
        extension: str,
        active_only: bool = True,
    ) -> List[AgentRegistry]:
        """
        Get agents supporting a specific file extension.

        Args:
            session: Database session
            extension: File extension (without dot)
            active_only: Only return active agents

        Returns:
            List of matching AgentRegistry records
        """
        try:
            # PostgreSQL array contains operator
            query = select(AgentRegistry).where(
                AgentRegistry.file_extensions.contains([extension])
            )
            if active_only:
                query = query.where(AgentRegistry.status == AgentStatus.ACTIVE)
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get agents for extension {extension}: {e}")
            raise

    @staticmethod
    async def get_agents_by_mime_type(
        session: AsyncSession,
        mime_type: str,
        active_only: bool = True,
    ) -> List[AgentRegistry]:
        """
        Get agents supporting a specific MIME type.

        Args:
            session: Database session
            mime_type: MIME type string
            active_only: Only return active agents

        Returns:
            List of matching AgentRegistry records
        """
        try:
            # PostgreSQL array contains operator
            query = select(AgentRegistry).where(
                AgentRegistry.mime_types.contains([mime_type])
            )
            if active_only:
                query = query.where(AgentRegistry.status == AgentStatus.ACTIVE)
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get agents for MIME {mime_type}: {e}")
            raise

    @staticmethod
    async def get_agents_by_content_type(
        session: AsyncSession,
        content_type: str,
        active_only: bool = True,
    ) -> List[AgentRegistry]:
        """
        Get agents supporting a specific content type (extension OR MIME).

        Args:
            session: Database session
            content_type: Extension or MIME type
            active_only: Only return active agents

        Returns:
            List of matching AgentRegistry records
        """
        try:
            from sqlalchemy import or_

            query = select(AgentRegistry).where(
                or_(
                    AgentRegistry.file_extensions.contains([content_type]),
                    AgentRegistry.mime_types.contains([content_type]),
                )
            )
            if active_only:
                query = query.where(AgentRegistry.status == AgentStatus.ACTIVE)
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get agents for content type {content_type}: {e}")
            raise

    @staticmethod
    async def update_agent_status(
        session: AsyncSession,
        agent_id: str,
        status: str,
    ) -> Optional[AgentRegistry]:
        """
        Update agent status.

        Args:
            session: Database session
            agent_id: Agent identifier
            status: New status value

        Returns:
            Updated AgentRegistry record or None if not found
        """
        try:
            agent = await AgentRegistryService.get_agent_by_id(session, agent_id)
            if not agent:
                return None

            agent.status = status
            await session.commit()
            logger.info(f"Updated agent {agent_id} status to {status}")
            return agent
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to update agent {agent_id} status: {e}")
            raise

    @staticmethod
    async def get_agents_by_priority(
        session: AsyncSession,
        priority: str,
        active_only: bool = True,
    ) -> List[AgentRegistry]:
        """
        Get agents by priority.

        Args:
            session: Database session
            priority: Priority level (low, normal, high)
            active_only: Only return active agents

        Returns:
            List of matching AgentRegistry records
        """
        try:
            query = select(AgentRegistry).where(AgentRegistry.priority == priority)
            if active_only:
                query = query.where(AgentRegistry.status == AgentStatus.ACTIVE)
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get agents by priority {priority}: {e}")
            raise
