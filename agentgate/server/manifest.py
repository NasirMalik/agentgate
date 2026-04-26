from __future__ import annotations

import inspect
from typing import Any, get_type_hints

from pydantic import TypeAdapter

from agentgate.server.decorators import _Registry, StepEntry
from agentgate.shared.manifest import (
    AuthDef,
    FlowDef,
    IntentDef,
    Manifest,
    StepDef,
)
from agentgate.shared.protocol import INTENTS_BASE, FLOWS_BASE


def _schema_for_type(annotation) -> dict:
    if annotation is inspect.Parameter.empty or annotation is None:
        return {}
    try:
        adapter = TypeAdapter(annotation)
        return adapter.json_schema()
    except Exception:
        return {"type": "object"}


def _input_schema_for_sig(sig: inspect.Signature) -> dict:
    props = {}
    required = []
    for name, param in sig.parameters.items():
        if name in ("self", "session"):
            continue
        schema = _schema_for_type(param.annotation)
        props[name] = schema
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


def _step_next(step: StepEntry, all_steps: list[StepEntry]) -> list[str]:
    return [s.name for s in all_steps if s.after == step.name]


def build_manifest(
    registry: _Registry,
    title: str,
    description: str,
    version: str,
    base_url: str,
    auth: AuthDef,
) -> Manifest:
    intents: list[IntentDef] = []
    for entry in registry.intents.values():
        hints = get_type_hints(entry.fn)
        return_type = hints.get("return")
        intents.append(
            IntentDef(
                name=entry.name,
                description=entry.description,
                endpoint=f"{INTENTS_BASE}/{entry.name}",
                input_schema=_input_schema_for_sig(entry.sig),
                output_schema=_schema_for_type(return_type),
            )
        )

    flows: list[FlowDef] = []
    for flow_entry in registry.flows.values():
        step_defs: list[StepDef] = []
        for s in flow_entry.steps:
            hints = get_type_hints(s.fn)
            return_type = hints.get("return")
            step_defs.append(
                StepDef(
                    name=s.name,
                    description=s.description,
                    entry=s.entry,
                    next_steps=_step_next(s, flow_entry.steps),
                    input_schema=_input_schema_for_sig(s.sig),
                    output_schema=_schema_for_type(return_type),
                )
            )
        flows.append(
            FlowDef(
                name=flow_entry.name,
                description=flow_entry.description,
                orchestration=flow_entry.orchestration,
                steps=step_defs,
            )
        )

    return Manifest(
        name=title,
        description=description,
        base_url=base_url,
        auth=auth,
        intents=intents,
        flows=flows,
    )
