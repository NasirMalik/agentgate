from __future__ import annotations

from typing import Any

import httpx

from agentgate.shared.errors import (
    FlowNotFoundError,
    IntentError,
    SessionNotFoundError,
    StepTransitionError,
)
from agentgate.shared.manifest import FlowDef, IntentDef, Manifest
from agentgate.shared.protocol import (
    FLOWS_BASE,
    HEADER_AGENT_ID,
    HEADER_AGENT_REQUEST,
    HEADER_AGENT_VERSION,
    HEADER_API_KEY,
    HEADER_SESSION_ID,
    AGENT_API_VERSION,
    INTENTS_BASE,
)


class IntentExecutor:
    def __init__(self, base_url: str, intent: IntentDef, base_headers: dict[str, str]):
        self._base_url = base_url.rstrip("/")
        self._intent = intent
        self._headers = {**base_headers, "Content-Type": "application/json"}

    async def __call__(self, **kwargs) -> Any:
        url = f"{self._base_url}{self._intent.endpoint}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=kwargs, headers=self._headers)
        if not resp.is_success:
            raise IntentError(f"Intent '{self._intent.name}' failed [{resp.status_code}]: {resp.text}")
        return resp.json()


class ServerFlowSession:
    """Manages one server-orchestrated flow session."""

    def __init__(
        self,
        base_url: str,
        flow: FlowDef,
        session_id: str,
        current_step: str,
        allowed_next: list[str],
        base_headers: dict[str, str],
    ):
        self._base_url = base_url.rstrip("/")
        self._flow = flow
        self.session_id = session_id
        self.current_step = current_step
        self.allowed_next_steps = allowed_next
        self._headers = {
            **base_headers,
            "Content-Type": "application/json",
            HEADER_SESSION_ID: session_id,
        }

    async def step(self, step_name: str, **kwargs) -> Any:
        if step_name not in self.allowed_next_steps:
            raise StepTransitionError(step_name, self.current_step, self.allowed_next_steps)

        url = f"{self._base_url}{FLOWS_BASE}/{self._flow.name}/step/{step_name}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=kwargs, headers=self._headers)

        if resp.status_code == 404:
            raise SessionNotFoundError(self.session_id)
        resp.raise_for_status()

        data = resp.json()
        self.current_step = data.get("current_step", step_name)
        self.allowed_next_steps = data.get("allowed_next_steps", [])
        self.flow_complete = data.get("flow_complete", False)
        return data.get("result")

    @property
    def is_complete(self) -> bool:
        return len(self.allowed_next_steps) == 0


class ServerFlowProxy:
    """Returned by site.flows.<name> for server-orchestrated flows."""

    def __init__(self, base_url: str, flow: FlowDef, base_headers: dict[str, str]):
        self._base_url = base_url.rstrip("/")
        self._flow = flow
        self._headers = {**base_headers, "Content-Type": "application/json"}

    async def start(self) -> ServerFlowSession:
        url = f"{self._base_url}{FLOWS_BASE}/{self._flow.name}/start"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self._headers)
        resp.raise_for_status()
        data = resp.json()
        return ServerFlowSession(
            base_url=self._base_url,
            flow=self._flow,
            session_id=data["session_id"],
            current_step=data["current_step"],
            allowed_next=data.get("allowed_next_steps", []),
            base_headers=self._headers,
        )


class ClientFlowStepProxy:
    """Proxy for a single client-orchestrated step."""

    def __init__(self, base_url: str, flow_name: str, step_name: str, base_headers: dict[str, str]):
        self._url = f"{base_url.rstrip('/')}{FLOWS_BASE}/{flow_name}/steps/{step_name}"
        self._headers = {**base_headers, "Content-Type": "application/json"}

    async def __call__(self, **kwargs) -> Any:
        async with httpx.AsyncClient() as client:
            resp = await client.post(self._url, json=kwargs, headers=self._headers)
        resp.raise_for_status()
        return resp.json()


class ClientFlowStepsNamespace:
    def __init__(self, base_url: str, flow: FlowDef, base_headers: dict[str, str]):
        self._proxies = {
            s.name: ClientFlowStepProxy(base_url, flow.name, s.name, base_headers)
            for s in flow.steps
        }

    def __getattr__(self, name: str) -> ClientFlowStepProxy:
        if name not in self._proxies:
            raise AttributeError(f"No step '{name}' in this flow")
        return self._proxies[name]
