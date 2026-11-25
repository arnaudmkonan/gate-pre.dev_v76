"""Resolve Client rows for shipments/entries (IOR name, EIN, fuzzy)."""
from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, ClientStatus


def _normalize_name(name: str) -> str:
    n = name.strip().lower()
    n = re.sub(r"[.,]", " ", n)
    n = re.sub(
        r"\b(incorporated|inc|llc|l\.l\.c|corp|corporation|co|company|ltd|limited)\b",
        " ",
        n,
    )
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _normalize_ein(ein: str) -> str:
    return re.sub(r"[^0-9]", "", ein or "")


async def resolve_client_id(
    db: AsyncSession,
    *,
    importer_name: Optional[str] = None,
    ein: Optional[str] = None,
    ior_number: Optional[str] = None,
) -> Optional[UUID]:
    """
    Best-effort Client.id for an importer.
    Prefer EIN/IOR exact match, then exact name, then normalized name.
    """
    ein_digits = _normalize_ein(ein or "") or _normalize_ein(ior_number or "")
    if ein_digits:
        # Compare stripped digits in Python after fetch — portable vs DB dialect
        rows = (
            await db.execute(
                select(Client.id, Client.ein, Client.ior_number).where(
                    or_(Client.ein.isnot(None), Client.ior_number.isnot(None))
                ).limit(1000)
            )
        ).all()
        for row in rows:
            if _normalize_ein(row.ein or "") == ein_digits:
                return row.id
            if _normalize_ein(row.ior_number or "") == ein_digits:
                return row.id

    if importer_name and importer_name.strip():
        name = importer_name.strip()
        result = await db.execute(
            select(Client.id).where(
                or_(
                    Client.name.ilike(name),
                    Client.dba_name.ilike(name),
                    Client.legal_name.ilike(name),
                )
            ).limit(1)
        )
        found = result.scalar_one_or_none()
        if found:
            return found

        rows = (
            await db.execute(
                select(Client.id, Client.name, Client.dba_name, Client.legal_name).where(
                    Client.status.in_(
                        [
                            ClientStatus.ACTIVE.value,
                            ClientStatus.ONBOARDING.value,
                            "active",
                            "onboarding",
                        ]
                    )
                ).limit(500)
            )
        ).all()
        target = _normalize_name(name)
        if target:
            for row in rows:
                for cand in (row.name, row.dba_name, row.legal_name):
                    if cand and _normalize_name(cand) == target:
                        return row.id
            for row in rows:
                for cand in (row.name, row.dba_name):
                    if not cand:
                        continue
                    cn = _normalize_name(cand)
                    if target in cn or cn in target:
                        if min(len(target), len(cn)) >= 8:
                            return row.id

    return None
