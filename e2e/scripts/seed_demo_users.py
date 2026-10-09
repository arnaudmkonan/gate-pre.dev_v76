"""Seed login users matching LoginPage demo buttons (idempotent)."""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.client import Client, ClientStatus
from app.models.client_portal import ClientUser, ClientUserRole, ClientUserStatus

USERS = [
    ("admin@example.com", "adminpassword", ClientUserRole.ADMIN.value),
    ("demo@example.com", "demopassword", ClientUserRole.USER.value),
]
CLIENT_NAME = "E2E Test Broker"


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Client).where(Client.name == CLIENT_NAME))
        client = result.scalar_one_or_none()
        if not client:
            client = Client(name=CLIENT_NAME, status=ClientStatus.ACTIVE.value)
            session.add(client)
            await session.flush()

        for email, password, role in USERS:
            existing = await session.execute(
                select(ClientUser).where(ClientUser.email == email)
            )
            if existing.scalar_one_or_none():
                continue
            user = ClientUser(
                email=email,
                first_name="E2E",
                last_name=role,
                role=role,
                status=ClientUserStatus.ACTIVE.value,
                client_id=client.id,
            )
            user.set_password(password)
            session.add(user)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
