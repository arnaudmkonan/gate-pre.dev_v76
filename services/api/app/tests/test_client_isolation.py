"""Cross-tenant access checks for client-scoped APIs."""
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.startup.client_access import assert_user_can_access_client, portal_user_client_id


def test_admin_can_access_any_client():
    admin = {"role": "admin", "client_id": str(uuid4())}
    asyncio.run(assert_user_can_access_client(admin, uuid4()))


def test_user_cannot_access_other_client():
    own = uuid4()
    user = {"role": "user", "client_id": str(own)}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(assert_user_can_access_client(user, uuid4()))
    assert exc.value.status_code == 403


def test_user_can_access_own_client():
    own = uuid4()
    user = {"role": "user", "client_id": str(own)}
    asyncio.run(assert_user_can_access_client(user, own))


def test_portal_user_client_id_for_non_admin():
    own = uuid4()
    user = {"role": "user", "client_id": str(own)}
    assert portal_user_client_id(user) == own


def test_portal_user_client_id_none_for_admin():
    assert portal_user_client_id({"role": "admin", "client_id": str(uuid4())}) is None
