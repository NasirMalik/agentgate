from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from agentgate.shared.errors import SessionNotFoundError


@dataclass
class StepRecord:
    step_name: str
    input: dict
    output: Any


@dataclass
class FlowSession:
    session_id: str
    flow_name: str
    current_step: str
    allowed_next_steps: list[str]
    history: list[StepRecord] = field(default_factory=list)
    data: dict = field(default_factory=dict)


@runtime_checkable
class SessionStore(Protocol):
    async def create(self, flow_name: str, entry_step: str, allowed_next: list[str]) -> FlowSession: ...
    async def get(self, session_id: str) -> FlowSession: ...
    async def update(self, session: FlowSession) -> None: ...


class MemorySessionStore:
    def __init__(self):
        self._store: dict[str, FlowSession] = {}

    async def create(self, flow_name: str, entry_step: str, allowed_next: list[str]) -> FlowSession:
        session = FlowSession(
            session_id=str(uuid.uuid4()),
            flow_name=flow_name,
            current_step=entry_step,
            allowed_next_steps=allowed_next,
        )
        self._store[session.session_id] = session
        return session

    async def get(self, session_id: str) -> FlowSession:
        if session_id not in self._store:
            raise SessionNotFoundError(session_id)
        return self._store[session_id]

    async def update(self, session: FlowSession) -> None:
        self._store[session.session_id] = session
