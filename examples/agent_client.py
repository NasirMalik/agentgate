"""
AI agent client example — connects to the FoodPanda example server.

Run the server first:
    uvicorn examples.foodpanda_server:fastapi_app --reload

Then in another terminal:
    python examples/agent_client.py
"""
from __future__ import annotations

import asyncio

from agentgate import AgentClient


async def main():
    client = AgentClient(agent_id="food-ordering-agent-v1", api_key="demo-key")

    # Discover the site — fetches /.well-known/agent-manifest.json
    site = await client.discover("http://localhost:8000")
    print(f"Discovered: {site}")
    print()

    # ── Single intent ─────────────────────────────────────────────────────────
    print("=== Intent: search_restaurants ===")
    results = await site.intents.search_restaurants(query="pizza", location="Berlin")
    print(f"Results: {results}")
    print()

    # ── Server-orchestrated flow ──────────────────────────────────────────────
    print("=== Flow: order_food (server-orchestrated) ===")
    session = await site.flows.order_food.start()
    print(f"Session started: {session.session_id}, first step: {session.current_step}")

    menu = await session.step("search", query="pizza", location="Berlin")
    print(f"Restaurants: {menu}")

    items = await session.step("select_restaurant", restaurant_id="r1")
    print(f"Menu items: {items}")

    order = await session.step(
        "checkout",
        items=[{"item_id": "m1", "quantity": 2}],
        delivery_address="Alexanderplatz 1, Berlin",
    )
    print(f"Order placed: {order}")
    print(f"Flow complete: {session.is_complete}")
    print()

    # ── Client-orchestrated flow ──────────────────────────────────────────────
    print("=== Flow: track_delivery (client-orchestrated) ===")
    tracking = await site.flows.track_delivery.steps.initiate(order_id="ORD-001")
    print(f"Tracking started: {tracking}")

    status = await site.flows.track_delivery.steps.get_status(
        tracking_id=tracking["tracking_id"]
    )
    print(f"Status: {status}")


if __name__ == "__main__":
    asyncio.run(main())
