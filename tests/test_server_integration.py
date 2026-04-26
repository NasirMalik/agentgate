"""Integration tests using FastAPI TestClient (async httpx transport)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from agentgate import AgentApp, AuthDef, step
from agentgate.shared.protocol import (
    HEADER_AGENT_REQUEST,
    HEADER_SESSION_ID,
    MANIFEST_PATH,
)


class Meal(BaseModel):
    name: str
    price: float


def _build_test_app() -> FastAPI:
    agent_app = AgentApp(title="TestShop", auth=AuthDef(type="none"))

    @agent_app.intent("get_meals", description="list meals")
    async def get_meals(cuisine: str) -> list[Meal]:
        return [Meal(name="Pizza", price=10.0)]

    @agent_app.flow("order", orchestration="server")
    class OrderFlow:
        @step(entry=True)
        async def pick(self, item: str) -> dict:
            return {"picked": item}

        @step(after="pick")
        async def pay(self, method: str) -> dict:
            return {"paid": True, "method": method}

    @agent_app.flow("track", orchestration="client")
    class TrackFlow:
        @step(entry=True)
        async def init(self, order_id: str) -> dict:
            return {"tracking_id": f"TRK-{order_id}"}

        @step(after="init")
        async def status(self, tracking_id: str) -> dict:
            return {"status": "on_the_way"}

    fastapi_app = FastAPI()
    agent_app.mount(fastapi_app)
    return fastapi_app


AGENT_HEADERS = {HEADER_AGENT_REQUEST: "true"}


@pytest.fixture
def app() -> FastAPI:
    return _build_test_app()


@pytest.fixture
def transport(app):
    return ASGITransport(app=app)


async def test_manifest_endpoint(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(MANIFEST_PATH, headers=AGENT_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "TestShop"
    assert any(i["name"] == "get_meals" for i in data["intents"])
    assert any(f["name"] == "order" for f in data["flows"])


async def test_intent_execution(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/agent/intents/get_meals",
            json={"cuisine": "Italian"},
            headers=AGENT_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Pizza"


async def test_server_flow_full(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # start
        start = await client.post("/agent/flows/order/start", headers=AGENT_HEADERS)
        assert start.status_code == 200
        session_id = start.json()["session_id"]
        assert start.json()["entry_step"] == "pick"

        # step: pick
        pick = await client.post(
            "/agent/flows/order/step/pick",
            json={"item": "burger"},
            headers={**AGENT_HEADERS, HEADER_SESSION_ID: session_id},
        )
        assert pick.status_code == 200
        assert pick.json()["result"]["picked"] == "burger"
        assert "pay" in pick.json()["allowed_next_steps"]

        # step: pay
        pay = await client.post(
            "/agent/flows/order/step/pay",
            json={"method": "card"},
            headers={**AGENT_HEADERS, HEADER_SESSION_ID: session_id},
        )
        assert pay.status_code == 200
        assert pay.json()["result"]["paid"] is True
        assert pay.json()["flow_complete"] is True


async def test_invalid_step_transition(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start = await client.post("/agent/flows/order/start", headers=AGENT_HEADERS)
        session_id = start.json()["session_id"]

        # try to jump to 'pay' before 'pick'
        resp = await client.post(
            "/agent/flows/order/step/pay",
            json={"method": "card"},
            headers={**AGENT_HEADERS, HEADER_SESSION_ID: session_id},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "step_not_allowed"


async def test_client_flow(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        init = await client.post(
            "/agent/flows/track/steps/init",
            json={"order_id": "42"},
            headers=AGENT_HEADERS,
        )
        assert init.status_code == 200
        tracking_id = init.json()["tracking_id"]

        status = await client.post(
            "/agent/flows/track/steps/status",
            json={"tracking_id": tracking_id},
            headers=AGENT_HEADERS,
        )
        assert status.status_code == 200
        assert status.json()["status"] == "on_the_way"


async def test_missing_session_header(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/agent/flows/order/step/pick",
            json={"item": "burger"},
            headers=AGENT_HEADERS,
        )
    assert resp.status_code == 400
