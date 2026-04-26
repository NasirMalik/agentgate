"""
FoodPanda-style server example.

Run with:
    pip install -e ".[server]"
    uvicorn examples.foodpanda_server:fastapi_app --reload
"""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import FastAPI

from agentgate import AgentApp, AuthDef, step


# ── Domain models ────────────────────────────────────────────────────────────

class Restaurant(BaseModel):
    id: str
    name: str
    cuisine: str
    rating: float


class MenuItem(BaseModel):
    id: str
    name: str
    price: float


class CartItem(BaseModel):
    item_id: str
    quantity: int


class OrderConfirmation(BaseModel):
    order_id: str
    status: str
    estimated_minutes: int


class TrackingInfo(BaseModel):
    tracking_id: str
    order_id: str
    status: str


class StatusUpdate(BaseModel):
    tracking_id: str
    status: str
    estimated_arrival: str


# ── AgentApp setup ────────────────────────────────────────────────────────────

agent_app = AgentApp(
    title="FoodPanda",
    description="Food delivery platform — agent-native API",
    version="1.0",
    auth=AuthDef(type="api_key", header="X-API-Key"),
)


# ── Single intent: search ─────────────────────────────────────────────────────

@agent_app.intent("search_restaurants", description="Search restaurants by query and city")
async def search_restaurants(query: str, location: str) -> list[Restaurant]:
    return [
        Restaurant(id="r1", name="Pizza Palace", cuisine="Italian", rating=4.5),
        Restaurant(id="r2", name="Burger Barn", cuisine="American", rating=4.2),
    ]


# ── Server-orchestrated flow: order food ─────────────────────────────────────

@agent_app.flow("order_food", orchestration="server", description="End-to-end food ordering")
class OrderFoodFlow:

    @step(entry=True, description="Search for restaurants")
    async def search(self, query: str, location: str) -> list[Restaurant]:
        return [
            Restaurant(id="r1", name="Pizza Palace", cuisine="Italian", rating=4.5),
        ]

    @step(after="search", description="View menu for a selected restaurant")
    async def select_restaurant(self, restaurant_id: str) -> list[MenuItem]:
        return [
            MenuItem(id="m1", name="Margherita", price=12.50),
            MenuItem(id="m2", name="Pepperoni", price=14.00),
        ]

    @step(after="select_restaurant", description="Place the order")
    async def checkout(self, items: list[CartItem], delivery_address: str) -> OrderConfirmation:
        return OrderConfirmation(
            order_id="ORD-001",
            status="confirmed",
            estimated_minutes=35,
        )


# ── Client-orchestrated flow: track delivery ──────────────────────────────────

@agent_app.flow("track_delivery", orchestration="client", description="Track a placed order")
class TrackDeliveryFlow:

    @step(entry=True, description="Start tracking — returns a tracking_id")
    async def initiate(self, order_id: str) -> TrackingInfo:
        return TrackingInfo(tracking_id="TRK-001", order_id=order_id, status="preparing")

    @step(after="initiate", description="Get current delivery status")
    async def get_status(self, tracking_id: str) -> StatusUpdate:
        return StatusUpdate(
            tracking_id=tracking_id,
            status="on_the_way",
            estimated_arrival="18:45",
        )


# ── Mount to FastAPI ──────────────────────────────────────────────────────────

fastapi_app = FastAPI(title="FoodPanda")
agent_app.mount(fastapi_app, base_url="http://localhost:8000")
