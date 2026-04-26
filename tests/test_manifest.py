from __future__ import annotations

import pytest
from pydantic import BaseModel

from agentgate import AgentApp, AuthDef, step
from agentgate.server.manifest import build_manifest
from agentgate.shared.manifest import Manifest


class Item(BaseModel):
    name: str
    price: float


def _make_app() -> AgentApp:
    app = AgentApp(title="TestApp", description="test", auth=AuthDef(type="api_key", header="X-Key"))

    @app.intent("search", description="search items")
    async def search(query: str, limit: int = 10) -> list[Item]:
        return []

    @app.flow("buy", orchestration="server", description="buy flow")
    class BuyFlow:
        @step(entry=True, description="add to cart")
        async def add(self, item_id: str) -> Item:
            return Item(name="x", price=1.0)

        @step(after="add", description="confirm")
        async def confirm(self, address: str) -> dict:
            return {}

    @app.flow("track", orchestration="client")
    class TrackFlow:
        @step(entry=True)
        async def start(self, order_id: str) -> dict:
            return {}

        @step(after="start")
        async def status(self, tracking_id: str) -> dict:
            return {}

    return app


def test_manifest_structure():
    app = _make_app()
    manifest = build_manifest(
        app._registry, "TestApp", "test", "1.0", "http://test.com", app.auth
    )
    assert isinstance(manifest, Manifest)
    assert manifest.name == "TestApp"
    assert len(manifest.intents) == 1
    assert len(manifest.flows) == 2


def test_intent_schema():
    app = _make_app()
    manifest = build_manifest(app._registry, "T", "", "1.0", "", app.auth)
    intent = manifest.intents[0]
    assert intent.name == "search"
    assert "query" in intent.input_schema["properties"]
    assert "limit" in intent.input_schema["properties"]
    assert "query" in intent.input_schema["required"]
    assert "limit" not in intent.input_schema["required"]


def test_flow_orchestration():
    app = _make_app()
    manifest = build_manifest(app._registry, "T", "", "1.0", "", app.auth)
    flows = {f.name: f for f in manifest.flows}
    assert flows["buy"].orchestration == "server"
    assert flows["track"].orchestration == "client"


def test_flow_step_order():
    app = _make_app()
    manifest = build_manifest(app._registry, "T", "", "1.0", "", app.auth)
    buy = next(f for f in manifest.flows if f.name == "buy")
    add_step = next(s for s in buy.steps if s.name == "add")
    confirm_step = next(s for s in buy.steps if s.name == "confirm")
    assert add_step.entry is True
    assert "confirm" in add_step.next_steps
    assert confirm_step.next_steps == []


def test_manifest_round_trip():
    app = _make_app()
    manifest = build_manifest(app._registry, "T", "", "1.0", "", app.auth)
    data = manifest.model_dump()
    restored = Manifest.model_validate(data)
    assert restored.name == manifest.name
    assert len(restored.intents) == len(manifest.intents)
    assert len(restored.flows) == len(manifest.flows)
