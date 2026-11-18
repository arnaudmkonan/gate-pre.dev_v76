"""Idempotent demo users for local dev and E2E (login page demo buttons)."""
import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.client import Client, ClientStatus
from datetime import datetime, timezone

from app.models.client_portal import ClientUser, ClientUserRole, ClientUserStatus

logger = logging.getLogger(__name__)

DEMO_CLIENT_NAME = "E2E Test Broker"
DEMO_USERS = (
    ("admin@example.com", "adminpassword", ClientUserRole.ADMIN.value),
    ("demo@example.com", "demopassword", ClientUserRole.USER.value),
)


async def seed_demo_users_if_enabled() -> None:
    if not settings.seed_demo_users:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Client).where(Client.name == DEMO_CLIENT_NAME))
        client = result.scalar_one_or_none()
        if not client:
            client = Client(name=DEMO_CLIENT_NAME, status=ClientStatus.ACTIVE.value)
            session.add(client)
            await session.flush()

        created = 0
        for email, password, role in DEMO_USERS:
            existing = await session.execute(select(ClientUser).where(ClientUser.email == email))
            if existing.scalar_one_or_none():
                continue
            user = ClientUser(
                email=email,
                first_name="Demo",
                last_name=role.title(),
                role=role,
                status=ClientUserStatus.ACTIVE.value,
                client_id=client.id,
                email_verified_at=datetime.now(timezone.utc),
            )
            user.set_password(password)
            session.add(user)
            created += 1

        if created:
            await session.commit()
            logger.info("Seeded %s demo portal user(s)", created)
