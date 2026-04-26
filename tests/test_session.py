from __future__ import annotations

import pytest

from agentgate.server.session import FlowSession, MemorySessionStore
from agentgate.shared.errors import SessionNotFoundError


@pytest.fixture
def store() -> MemorySessionStore:
    return MemorySessionStore()


async def test_create_and_get(store):
    session = await store.create("order_food", "search", ["select"])
    assert session.flow_name == "order_food"
    assert session.current_step == "search"
    assert session.allowed_next_steps == ["select"]

    fetched = await store.get(session.session_id)
    assert fetched.session_id == session.session_id


async def test_update(store):
    session = await store.create("order_food", "search", ["select"])
    session.current_step = "select"
    session.allowed_next_steps = ["checkout"]
    await store.update(session)

    updated = await store.get(session.session_id)
    assert updated.current_step == "select"
    assert updated.allowed_next_steps == ["checkout"]


async def test_not_found(store):
    with pytest.raises(SessionNotFoundError):
        await store.get("nonexistent-id")


async def test_unique_session_ids(store):
    s1 = await store.create("f", "a", [])
    s2 = await store.create("f", "a", [])
    assert s1.session_id != s2.session_id
