from __future__ import annotations

from typing import Callable, Literal

from fastapi import FastAPI

from agentgate.server.decorators import _Registry, step  # re-export step
from agentgate.server.manifest import build_manifest
from agentgate.server.middleware import AgentDetectionMiddleware
from agentgate.server.router import build_router
from agentgate.server.session import MemorySessionStore, SessionStore
from agentgate.shared.manifest import AuthDef


class AgentApp:
    """
    Main entry point for website operators.

    Usage::

        app = AgentApp(title="MyService", description="...", version="1.0")

        @app.intent("search")
        async def search(query: str) -> list[str]: ...

        @app.flow("checkout", orchestration="server")
        class CheckoutFlow:
            @step(entry=True)
            async def cart(self, item_id: str) -> dict: ...

        fastapi_app = FastAPI()
        app.mount(fastapi_app)
    """

    def __init__(
        self,
        title: str,
        description: str = "",
        version: str = "1.0",
        auth: AuthDef | None = None,
        session_store: SessionStore | None = None,
    ):
        self.title = title
        self.description = description
        self.version = version
        self.auth = auth or AuthDef()
        self._registry = _Registry()
        self._session_store: SessionStore = session_store or MemorySessionStore()

    # ── Decorators ───────────────────────────────────────────────────────────

    def intent(self, name: str, description: str = ""):
        def decorator(fn: Callable) -> Callable:
            self._registry.register_intent(name, description, fn)
            return fn
        return decorator

    def flow(
        self,
        name: str,
        orchestration: Literal["server", "client"] = "server",
        description: str = "",
    ):
        def decorator(cls: type) -> type:
            self._registry.register_flow(name, description, orchestration, cls)
            return cls
        return decorator

    # ── Mount ────────────────────────────────────────────────────────────────

    def mount(self, fastapi_app: FastAPI, base_url: str = ""):
        manifest = build_manifest(
            registry=self._registry,
            title=self.title,
            description=self.description,
            version=self.version,
            base_url=base_url,
            auth=self.auth,
        )
        router = build_router(self._registry, self._session_store, manifest)
        fastapi_app.include_router(router)
        fastapi_app.add_middleware(AgentDetectionMiddleware)
