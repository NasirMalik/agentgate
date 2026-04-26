from __future__ import annotations

from agentgate.client.discovery import ManifestDiscovery
from agentgate.client.site import DiscoveredSite
from agentgate.shared.protocol import (
    HEADER_AGENT_ID,
    HEADER_AGENT_REQUEST,
    HEADER_AGENT_VERSION,
    HEADER_API_KEY,
    AGENT_API_VERSION,
)


class AgentClient:
    """
    Main entry point for AI agents.

    Usage::

        client = AgentClient(agent_id="my-agent", api_key="sk-...")
        site = await client.discover("https://foodpanda.com")
        results = await site.intents.search_restaurants(query="pizza", location="Berlin")
    """

    def __init__(
        self,
        agent_id: str,
        api_key: str | None = None,
        manifest_cache_ttl: float = 300.0,
    ):
        self._agent_id = agent_id
        self._api_key = api_key
        self._discovery = ManifestDiscovery(agent_id=agent_id, cache_ttl=manifest_cache_ttl)

    def _build_headers(self, manifest_auth_type: str | None) -> dict[str, str]:
        headers: dict[str, str] = {
            HEADER_AGENT_REQUEST: "true",
            HEADER_AGENT_ID: self._agent_id,
            HEADER_AGENT_VERSION: AGENT_API_VERSION,
        }
        if manifest_auth_type == "api_key" and self._api_key:
            headers[HEADER_API_KEY] = self._api_key
        elif manifest_auth_type == "bearer" and self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def discover(self, base_url: str) -> DiscoveredSite:
        manifest = await self._discovery.discover(base_url)
        base_headers = self._build_headers(manifest.auth.type)
        return DiscoveredSite(
            manifest=manifest,
            base_url=base_url.rstrip("/"),
            base_headers=base_headers,
        )
