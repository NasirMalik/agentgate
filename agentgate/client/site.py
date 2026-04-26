from __future__ import annotations

from agentgate.client.executor import (
    ClientFlowStepsNamespace,
    IntentExecutor,
    ServerFlowProxy,
)
from agentgate.shared.manifest import FlowDef, IntentDef, Manifest


class _IntentsNamespace:
    def __init__(self, intents: list[IntentDef], base_url: str, base_headers: dict[str, str]):
        self._executors = {
            i.name: IntentExecutor(base_url, i, base_headers)
            for i in intents
        }

    def __getattr__(self, name: str) -> IntentExecutor:
        if name not in self._executors:
            raise AttributeError(f"No intent '{name}' in manifest")
        return self._executors[name]

    def list(self) -> list[str]:
        return list(self._executors.keys())


class _FlowProxy:
    """Unified proxy: .start() for server-orchestrated, .steps.<name>() for client-orchestrated."""

    def __init__(self, flow: FlowDef, base_url: str, base_headers: dict[str, str]):
        self._flow = flow
        if flow.orchestration == "server":
            self._server_proxy = ServerFlowProxy(base_url, flow, base_headers)
        else:
            self.steps = ClientFlowStepsNamespace(base_url, flow, base_headers)

    async def start(self):
        if self._flow.orchestration != "server":
            raise TypeError(
                f"Flow '{self._flow.name}' is client-orchestrated. Use .steps.<step_name>() instead."
            )
        return await self._server_proxy.start()


class _FlowsNamespace:
    def __init__(self, flows: list[FlowDef], base_url: str, base_headers: dict[str, str]):
        self._proxies = {
            f.name: _FlowProxy(f, base_url, base_headers)
            for f in flows
        }

    def __getattr__(self, name: str) -> _FlowProxy:
        if name not in self._proxies:
            raise AttributeError(f"No flow '{name}' in manifest")
        return self._proxies[name]

    def list(self) -> list[str]:
        return list(self._proxies.keys())


class DiscoveredSite:
    """
    Represents a discovered agent-native site. Access capabilities via:
      - site.intents.<intent_name>(...)
      - site.flows.<flow_name>.start()           # server-orchestrated
      - site.flows.<flow_name>.steps.<step>(...)  # client-orchestrated
    """

    def __init__(self, manifest: Manifest, base_url: str, base_headers: dict[str, str]):
        self.manifest = manifest
        self.base_url = base_url
        self.intents = _IntentsNamespace(manifest.intents, base_url, base_headers)
        self.flows = _FlowsNamespace(manifest.flows, base_url, base_headers)

    def __repr__(self) -> str:
        return (
            f"<DiscoveredSite '{self.manifest.name}' "
            f"intents={self.intents.list()} flows={self.flows.list()}>"
        )
