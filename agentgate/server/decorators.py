from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Literal


@dataclass
class IntentEntry:
    name: str
    description: str
    fn: Callable
    sig: inspect.Signature


@dataclass
class StepEntry:
    name: str
    description: str
    fn: Callable
    sig: inspect.Signature
    entry: bool
    after: str | None


@dataclass
class FlowEntry:
    name: str
    description: str
    orchestration: Literal["server", "client"]
    cls: type
    steps: list[StepEntry] = field(default_factory=list)


_STEP_ATTR = "__agentgate_step__"


def step(*, entry: bool = False, after: str | None = None, description: str = ""):
    """Marks a method inside a @flow class as a flow step."""
    def decorator(fn: Callable) -> Callable:
        setattr(fn, _STEP_ATTR, {"entry": entry, "after": after, "description": description})
        return fn
    return decorator


class _Registry:
    def __init__(self):
        self.intents: dict[str, IntentEntry] = {}
        self.flows: dict[str, FlowEntry] = {}

    def register_intent(self, name: str, description: str, fn: Callable):
        self.intents[name] = IntentEntry(
            name=name,
            description=description,
            fn=fn,
            sig=inspect.signature(fn),
        )

    def register_flow(
        self,
        name: str,
        description: str,
        orchestration: Literal["server", "client"],
        cls: type,
    ):
        steps: list[StepEntry] = []
        for attr_name in dir(cls):
            method = getattr(cls, attr_name)
            meta = getattr(method, _STEP_ATTR, None)
            if meta is None:
                continue
            steps.append(
                StepEntry(
                    name=attr_name,
                    description=meta["description"],
                    fn=method,
                    sig=inspect.signature(method),
                    entry=meta["entry"],
                    after=meta["after"],
                )
            )
        self.flows[name] = FlowEntry(
            name=name,
            description=description,
            orchestration=orchestration,
            cls=cls,
            steps=steps,
        )
