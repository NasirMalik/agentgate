from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from agentgate.server.decorators import _Registry, FlowEntry, StepEntry
from agentgate.server.session import FlowSession, SessionStore, StepRecord
from agentgate.shared.errors import SessionNotFoundError, StepTransitionError
from agentgate.shared.manifest import Manifest
from agentgate.shared.protocol import HEADER_SESSION_ID


def _find_step(flow: FlowEntry, name: str) -> StepEntry | None:
    return next((s for s in flow.steps if s.name == name), None)


def _next_steps(flow: FlowEntry, current: str) -> list[str]:
    return [s.name for s in flow.steps if s.after == current]


def build_router(
    registry: _Registry,
    session_store: SessionStore,
    manifest: Manifest,
) -> APIRouter:
    router = APIRouter()

    @router.get("/.well-known/agent-manifest.json")
    async def get_manifest():
        return JSONResponse(manifest.model_dump())

    # ── Intents ──────────────────────────────────────────────────────────────

    for intent_name, entry in registry.intents.items():

        async def _intent_handler(request: Request, _name: str = intent_name, _entry=entry):
            body = await request.json() if await request.body() else {}
            try:
                result = await _entry.fn(**body) if _is_async(_entry.fn) else _entry.fn(**body)
            except TypeError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            return _serialize(result)

        router.add_api_route(
            f"/agent/intents/{intent_name}",
            _intent_handler,
            methods=["POST"],
        )

    # ── Flows ─────────────────────────────────────────────────────────────────

    for flow_name, flow in registry.flows.items():

        if flow.orchestration == "server":
            entry_step = next((s for s in flow.steps if s.entry), None)

            async def _flow_start(_flow=flow, _entry_step=entry_step):
                if _entry_step is None:
                    raise HTTPException(status_code=500, detail="No entry step defined")
                session = await session_store.create(_flow.name, "", [_entry_step.name])
                return {
                    "session_id": session.session_id,
                    "entry_step": _entry_step.name,
                    "allowed_next_steps": session.allowed_next_steps,
                    "input_schema": next(
                        (s for s in manifest.flows if s.name == _flow.name), None
                    ) and _get_step_input_schema(manifest, _flow.name, _entry_step.name),
                }

            router.add_api_route(
                f"/agent/flows/{flow_name}/start",
                _flow_start,
                methods=["POST"],
            )

            async def _flow_session(session_id: str):
                try:
                    session = await session_store.get(session_id)
                except SessionNotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc))
                return session

            router.add_api_route(
                f"/agent/flows/{flow_name}/session/{{session_id}}",
                _flow_session,
                methods=["GET"],
            )

            for step_entry in flow.steps:

                async def _step_handler(
                    request: Request,
                    _flow=flow,
                    _step=step_entry,
                    x_session_id: str | None = Header(default=None, alias=HEADER_SESSION_ID),
                ):
                    if x_session_id is None:
                        raise HTTPException(status_code=400, detail=f"{HEADER_SESSION_ID} header required")
                    try:
                        session = await session_store.get(x_session_id)
                    except SessionNotFoundError as exc:
                        raise HTTPException(status_code=404, detail=str(exc))

                    if _step.name not in session.allowed_next_steps:
                        raise HTTPException(
                            status_code=422,
                            detail={
                                "error": "step_not_allowed",
                                "message": f"Step '{_step.name}' cannot follow '{session.current_step}'. Allowed next: {session.allowed_next_steps}",
                                "current_step": session.current_step,
                                "allowed_next_steps": session.allowed_next_steps,
                            },
                        )

                    body = await request.json() if await request.body() else {}
                    instance = _flow.cls()
                    try:
                        result = (
                            await _step.fn(instance, session=session, **body)
                            if _is_async(_step.fn)
                            else _step.fn(instance, session=session, **body)
                        )
                    except TypeError:
                        result = (
                            await _step.fn(instance, **body)
                            if _is_async(_step.fn)
                            else _step.fn(instance, **body)
                        )

                    nexts = _next_steps(_flow, _step.name)
                    session.history.append(StepRecord(step_name=_step.name, input=body, output=result))
                    session.current_step = _step.name
                    session.allowed_next_steps = nexts
                    await session_store.update(session)

                    return {
                        "result": _serialize(result),
                        "session_id": session.session_id,
                        "current_step": session.current_step,
                        "allowed_next_steps": nexts,
                        "flow_complete": len(nexts) == 0,
                    }

                router.add_api_route(
                    f"/agent/flows/{flow_name}/step/{step_entry.name}",
                    _step_handler,
                    methods=["POST"],
                )

        else:  # client-orchestrated
            for step_entry in flow.steps:

                async def _client_step(
                    request: Request,
                    _flow=flow,
                    _step=step_entry,
                ):
                    body = await request.json() if await request.body() else {}
                    instance = _flow.cls()
                    try:
                        result = (
                            await _step.fn(instance, **body)
                            if _is_async(_step.fn)
                            else _step.fn(instance, **body)
                        )
                    except TypeError as exc:
                        raise HTTPException(status_code=422, detail=str(exc))
                    return _serialize(result)

                router.add_api_route(
                    f"/agent/flows/{flow_name}/steps/{step_entry.name}",
                    _client_step,
                    methods=["POST"],
                )

    return router


def _is_async(fn) -> bool:
    import asyncio
    return asyncio.iscoroutinefunction(fn)


def _serialize(value) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def _get_step_input_schema(manifest: Manifest, flow_name: str, step_name: str) -> dict:
    flow = next((f for f in manifest.flows if f.name == flow_name), None)
    if flow is None:
        return {}
    step = next((s for s in flow.steps if s.name == step_name), None)
    return step.input_schema if step else {}
