from __future__ import annotations

import time
from typing import Any

import httpx

from agentgate.shared.errors import ManifestNotFoundError
from agentgate.shared.manifest import Manifest
from agentgate.shared.protocol import (
    HEADER_AGENT_ID,
    HEADER_AGENT_REQUEST,
    HEADER_AGENT_VERSION,
    AGENT_API_VERSION,
    MANIFEST_PATH,
)


class _CacheEntry:
    __slots__ = ("manifest", "expires_at")

    def __init__(self, manifest: Manifest, ttl: float):
        self.manifest = manifest
        self.expires_at = time.monotonic() + ttl


class ManifestDiscovery:
    def __init__(self, agent_id: str, cache_ttl: float = 300.0):
        self._agent_id = agent_id
        self._cache_ttl = cache_ttl
        self._cache: dict[str, _CacheEntry] = {}

    def _agent_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            HEADER_AGENT_REQUEST: "true",
            HEADER_AGENT_ID: self._agent_id,
            HEADER_AGENT_VERSION: AGENT_API_VERSION,
        }
        if extra:
            headers.update(extra)
        return headers

    async def discover(self, base_url: str) -> Manifest:
        base_url = base_url.rstrip("/")
        entry = self._cache.get(base_url)
        if entry and time.monotonic() < entry.expires_at:
            return entry.manifest

        url = f"{base_url}{MANIFEST_PATH}"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, headers=self._agent_headers(), follow_redirects=True)
            except httpx.RequestError as exc:
                raise ManifestNotFoundError(url) from exc

        if resp.status_code == 404:
            raise ManifestNotFoundError(url)
        resp.raise_for_status()

        manifest = Manifest.model_validate(resp.json())
        manifest.base_url = manifest.base_url or base_url
        self._cache[base_url] = _CacheEntry(manifest, self._cache_ttl)
        return manifest
