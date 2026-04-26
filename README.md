# agentgate

**The agent-native web protocol. Give AI agents a structured API instead of a website.**

---

When an AI agent visits `foodpanda.com` today, it downloads HTML meant for human eyes — navigation menus, ad banners, modals — and burns context window and compute trying to parse it into actions. `agentgate` fixes this at the source.

Website operators add `agentgate` to their FastAPI backend in an afternoon. From that point on, any AI agent that sends `X-Agent-Request: true` gets back a machine-readable manifest describing exactly what the site can do and how to do it — no HTML, no scraping, no prompt engineering around DOM structure.

```
Agent  ──→  GET /.well-known/agent-manifest.json  ──→  {intents, flows, schemas}
Agent  ──→  POST /agent/flows/order_food/start     ──→  {session_id, entry_step}
Agent  ──→  POST /agent/flows/order_food/step/...  ──→  {result, next_steps}
```

---

## Why not MCP?

[Model Context Protocol](https://modelcontextprotocol.io) (MCP) is excellent at what it does: connecting an LLM to **tools and resources in a local or operator-controlled environment** — file systems, databases, internal APIs, development tools. It is a client-side protocol designed to expand what a model can do inside a session.

`agentgate` solves a different problem: **any website on the public internet becoming natively callable by agents without prior integration work**.

| | MCP | agentgate |
|---|---|---|
| **Where it lives** | Sidecar process, stdio or SSE | Embedded in your existing web server |
| **Who configures it** | The LLM client / operator | The website operator |
| **Discovery** | Pre-configured — agent must know the server exists | Universal: `GET /.well-known/agent-manifest.json` on any domain |
| **Primary purpose** | Expand LLM tool access (files, DBs, APIs) | Make any website natively callable by agents |
| **Multi-step workflows** | Manual — agent orchestrates with raw tool calls | Built-in: `server` and `client` orchestration modes |
| **Session / state** | Not part of the protocol | First-class: server holds state across steps |
| **Transport** | stdio, SSE, HTTP (custom) | Standard HTTP — works with any `httpx`/`requests` client |
| **Existing website** | Requires separate MCP server process | `app.mount(fastapi_app)` — one line |
| **Agent compatibility** | Requires MCP-aware client | Any HTTP client; no framework required |
| **Open web scale** | Designed for closed, operator-controlled tools | Designed for the open web — discover any domain at runtime |

MCP and `agentgate` are **complementary, not competing**. An agent can use MCP to access its own tools (memory, code execution, calendar) while using `agentgate` to interact with external websites (e-commerce, booking, search).

---

## How it works

```
┌─────────────────────────────────────────────────────────────┐
│  Website (FastAPI)                                          │
│                                                             │
│   agentgate.mount()  ──adds──▶  /.well-known/agent-manifest │
│                                 /agent/intents/{name}        │
│                                 /agent/flows/{name}/start    │
│                                 /agent/flows/{name}/step/... │
│                                                             │
│   Normal routes are untouched — browsers see no change      │
└─────────────────────────────────────────────────────────────┘
         ▲
         │  X-Agent-Request: true
         │
┌─────────────────────┐
│  AI Agent           │
│                     │
│  client.discover()  │  ──▶  fetches manifest, understands capabilities
│  site.intents.*()   │  ──▶  one-shot structured calls
│  site.flows.*.start()──▶  starts stateful multi-step workflows
│  session.step(...)  │  ──▶  advances flow, server validates transitions
└─────────────────────┘
```

1. **Discover**: Agent fetches `/.well-known/agent-manifest.json`. The manifest lists every intent (single-step call) and flow (multi-step workflow) the site exposes, with full JSON Schema for inputs and outputs. No prior knowledge needed.
2. **Call intents**: Single-purpose actions (search, lookup, translate) — one request, one response.
3. **Execute flows**: Multi-step processes (order food, book a flight, register an account). Two modes:
   - **Server-orchestrated**: The server holds session state and enforces valid step transitions. The agent cannot skip steps or jump ahead — the server validates everything.
   - **Client-orchestrated**: Each step is an independent, stateless endpoint. The agent manages data chaining. Simpler for the server; suited for idempotent or read-heavy workflows.

---

## Installation

```bash
pip install agentgate
```

For running the development server:

```bash
pip install "agentgate[server]"   # includes uvicorn
```

**Requirements**: Python 3.10+, FastAPI, Pydantic v2, httpx

---

## Quick start — server side

Add `agentgate` to an existing FastAPI app in four steps.

### 1. Create an `AgentApp`

```python
from agentgate import AgentApp, AuthDef, step
from fastapi import FastAPI

agent_app = AgentApp(
    title="MyShop",
    description="E-commerce API for AI agents",
    version="1.0",
    auth=AuthDef(type="api_key", header="X-API-Key"),
)
```

### 2. Register intents (single-step capabilities)

Decorate any async function. Input and output schemas are auto-generated from type hints using Pydantic.

```python
from pydantic import BaseModel

class Product(BaseModel):
    id: str
    name: str
    price: float

@agent_app.intent("search_products", description="Search products by keyword")
async def search_products(query: str, max_results: int = 10) -> list[Product]:
    # your existing business logic
    return db.search(query, limit=max_results)
```

### 3. Register flows (multi-step workflows)

Use `@agent_app.flow` on a class and `@step` on its methods.

**Server-orchestrated** — the server holds session state and enforces step order:

```python
class CartItem(BaseModel):
    product_id: str
    quantity: int

class OrderConfirmation(BaseModel):
    order_id: str
    total: float
    eta_minutes: int

@agent_app.flow("checkout", orchestration="server", description="Add to cart and place order")
class CheckoutFlow:

    @step(entry=True, description="Add a product to the cart")
    async def add_to_cart(self, product_id: str, quantity: int) -> dict:
        return {"cart_id": cart.create(product_id, quantity)}

    @step(after="add_to_cart", description="Confirm and place the order")
    async def place_order(self, cart_id: str, address: str) -> OrderConfirmation:
        order = orders.create(cart_id, address)
        return OrderConfirmation(order_id=order.id, total=order.total, eta_minutes=30)
```

**Client-orchestrated** — each step is stateless and independent:

```python
@agent_app.flow("track_order", orchestration="client", description="Track an existing order")
class TrackOrderFlow:

    @step(entry=True, description="Initiate tracking for an order")
    async def initiate(self, order_id: str) -> dict:
        return {"tracking_id": tracking.start(order_id)}

    @step(after="initiate", description="Poll for current status")
    async def get_status(self, tracking_id: str) -> dict:
        return {"status": tracking.get(tracking_id)}
```

### 4. Mount onto your FastAPI app

```python
fastapi_app = FastAPI(title="MyShop")
agent_app.mount(fastapi_app, base_url="https://myshop.com")
```

That's it. Your existing routes are completely untouched. Agents that send `X-Agent-Request: true` get the agent API; regular browsers see nothing different.

**Start the server:**

```bash
uvicorn myapp:fastapi_app --reload
```

---

## Quick start — agent / client side

```python
import asyncio
from agentgate import AgentClient

async def main():
    client = AgentClient(
        agent_id="my-shopping-agent",
        api_key="sk-...",       # injected automatically based on manifest auth type
    )

    # Discover capabilities at runtime — no prior knowledge of the API needed
    site = await client.discover("https://myshop.com")
    print(site)
    # <DiscoveredSite 'MyShop' intents=['search_products'] flows=['checkout', 'track_order']>

    # Call a single intent
    products = await site.intents.search_products(query="wireless headphones", max_results=5)

    # Execute a server-orchestrated flow
    session = await site.flows.checkout.start()
    cart = await session.step("add_to_cart", product_id=products[0]["id"], quantity=1)
    order = await session.step("place_order", cart_id=cart["cart_id"], address="Berlin, DE")
    print(order)          # {"order_id": "...", "total": 79.99, "eta_minutes": 30}
    print(session.is_complete)  # True

    # Execute a client-orchestrated flow
    tracking = await site.flows.track_order.steps.initiate(order_id=order["order_id"])
    status = await site.flows.track_order.steps.get_status(tracking_id=tracking["tracking_id"])
    print(status)

asyncio.run(main())
```

---

## Full example — FoodPanda

The `examples/` directory contains a complete server + client pair:

```bash
# Terminal 1 — start the server
uvicorn examples.foodpanda_server:fastapi_app --reload

# Terminal 2 — run the agent
python examples/agent_client.py
```

[examples/foodpanda_server.py](examples/foodpanda_server.py) — FoodPanda-style backend with search intent, server-orchestrated ordering flow, and client-orchestrated tracking flow.

[examples/agent_client.py](examples/agent_client.py) — Agent that discovers, calls intents, and executes both flow types end-to-end.

---

## Core concepts

### The manifest

Every agentgate-enabled site serves `GET /.well-known/agent-manifest.json`. This is the contract between the site and any agent. The manifest is **auto-generated from your type annotations** — you don't write JSON Schema by hand.

```json
{
  "agent_api_version": "1.0",
  "name": "MyShop",
  "description": "E-commerce API for AI agents",
  "base_url": "https://myshop.com",
  "auth": {
    "type": "api_key",
    "header": "X-API-Key"
  },
  "intents": [
    {
      "name": "search_products",
      "description": "Search products by keyword",
      "endpoint": "/agent/intents/search_products",
      "method": "POST",
      "input_schema": {
        "type": "object",
        "properties": {
          "query": { "type": "string" },
          "max_results": { "type": "integer" }
        },
        "required": ["query"]
      },
      "output_schema": { ... }
    }
  ],
  "flows": [
    {
      "name": "checkout",
      "orchestration": "server",
      "steps": [
        {
          "name": "add_to_cart",
          "entry": true,
          "next_steps": ["place_order"],
          "input_schema": { ... },
          "output_schema": { ... }
        },
        {
          "name": "place_order",
          "entry": false,
          "next_steps": [],
          "input_schema": { ... },
          "output_schema": { ... }
        }
      ]
    }
  ]
}
```

### Intents

An intent is a single-step, stateless capability. Use intents for lookups, searches, calculations — anything that takes inputs and returns a result in one call.

```python
@agent_app.intent("convert_currency", description="Convert between currencies")
async def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    rate = fx.get_rate(from_currency, to_currency)
    return {"converted": amount * rate, "rate": rate}
```

Agents call it as:
```
POST /agent/intents/convert_currency
{"amount": 100, "from_currency": "USD", "to_currency": "EUR"}
```

### Flows

A flow is a named, ordered sequence of steps. Use flows for multi-step business processes — booking, ordering, registration, configuration wizards.

Each `@step` decorator links steps by name:
- `entry=True` — this is the first step agents must call
- `after="step_name"` — this step becomes available after `step_name` completes

**Choosing between server and client orchestration:**

| | Server-orchestrated | Client-orchestrated |
|---|---|---|
| State lives in | Server session store | Agent / caller |
| Step enforcement | Server validates transitions | Agent responsible |
| Best for | Orders, payments, multi-stage forms | Status polling, idempotent reads |
| Session header | `X-Session-ID` required | Not needed |

### Authentication

Set auth policy on `AgentApp`. The client SDK injects credentials automatically based on what the manifest declares.

```python
# API key (injected as X-API-Key header)
auth=AuthDef(type="api_key", header="X-API-Key")

# Bearer token (injected as Authorization: Bearer ...)
auth=AuthDef(type="bearer")

# No auth required
auth=AuthDef(type="none")
```

On the client:
```python
client = AgentClient(agent_id="my-agent", api_key="sk-...")
# api_key is injected automatically based on what the manifest says
```

### Custom session store

The default `MemorySessionStore` is suitable for development. In production, implement the `SessionStore` protocol to back sessions with Redis, a database, or any other store.

```python
from agentgate.server.session import SessionStore, FlowSession

class RedisSessionStore:
    async def create(self, flow_name: str, entry_step: str, allowed_next: list[str]) -> FlowSession: ...
    async def get(self, session_id: str) -> FlowSession: ...
    async def update(self, session: FlowSession) -> None: ...

agent_app = AgentApp(
    title="MyShop",
    session_store=RedisSessionStore(),
)
```

---

## HTTP protocol reference

### Agent identification headers

Sent by the client on every request:

| Header | Value | Required |
|---|---|---|
| `X-Agent-Request` | `true` | Yes |
| `X-Agent-ID` | Any string identifier for the agent | No |
| `X-Agent-Version` | `1.0` | No |

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/.well-known/agent-manifest.json` | Discover capabilities |
| `POST` | `/agent/intents/{name}` | Execute an intent |
| `POST` | `/agent/flows/{name}/start` | Start a server-orchestrated flow session |
| `POST` | `/agent/flows/{name}/step/{step_name}` | Advance a server-orchestrated step (requires `X-Session-ID`) |
| `GET` | `/agent/flows/{name}/session/{session_id}` | Inspect a server-orchestrated session |
| `POST` | `/agent/flows/{name}/steps/{step_name}` | Execute a client-orchestrated step (stateless) |

### Flow start response

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "entry_step": "add_to_cart",
  "allowed_next_steps": ["add_to_cart"],
  "input_schema": { ... }
}
```

### Step response

```json
{
  "result": { ... },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "current_step": "add_to_cart",
  "allowed_next_steps": ["place_order"],
  "flow_complete": false
}
```

### Error response

All errors follow a standard shape:

```json
{
  "error": "step_not_allowed",
  "message": "Step 'place_order' cannot follow ''. Allowed next: ['add_to_cart']",
  "current_step": "",
  "allowed_next_steps": ["add_to_cart"]
}
```

| HTTP status | Meaning |
|---|---|
| `400` | Missing required header (e.g. `X-Session-ID`) |
| `401` | Authentication failed |
| `404` | Intent, flow, or session not found |
| `422` | Invalid step transition or bad input |

---

## Error handling — client side

```python
from agentgate import (
    ManifestNotFoundError,   # site does not support agentgate
    StepTransitionError,     # tried to skip a step
    SessionNotFoundError,    # session expired or invalid
    IntentError,             # intent execution failed
    FlowNotFoundError,       # flow name not in manifest
)

try:
    site = await client.discover("https://example.com")
except ManifestNotFoundError:
    print("This site does not support agentgate")

try:
    await session.step("place_order", ...)
except StepTransitionError as e:
    print(f"Can't go there yet. Allowed: {e.allowed}")
```

---

## Package structure

```
agentgate/
├── shared/
│   ├── manifest.py      # Pydantic models: Manifest, IntentDef, FlowDef, StepDef, AuthDef
│   ├── protocol.py      # Protocol constants: headers, paths, version
│   └── errors.py        # Exception hierarchy
├── server/
│   ├── app.py           # AgentApp — main entry point for website operators
│   ├── decorators.py    # @app.intent, @app.flow, @step
│   ├── manifest.py      # Auto-generation from type hints via Pydantic + inspect
│   ├── router.py        # FastAPI APIRouter wiring all agent endpoints
│   ├── middleware.py    # AgentDetectionMiddleware
│   └── session.py       # FlowSession dataclass, SessionStore protocol, MemorySessionStore
└── client/
    ├── client.py        # AgentClient — main entry point for AI agents
    ├── discovery.py     # Manifest fetching + TTL cache
    ├── site.py          # DiscoveredSite with .intents and .flows dynamic namespaces
    └── executor.py      # IntentExecutor, ServerFlowSession, ClientFlowStepProxy
```

---

## Roadmap

- [ ] Django and Starlette adapters
- [ ] OAuth2 and JWT built-in auth support
- [ ] Streaming step responses (Server-Sent Events)
- [ ] Manifest versioning and changelog
- [ ] Official `agentgate.json` registry — a public directory of agent-native sites
- [ ] OpenAPI → agentgate manifest migration tool

---

## Running the tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT
