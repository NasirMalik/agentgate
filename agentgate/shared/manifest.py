from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class AuthDef(BaseModel):
    type: Literal["api_key", "bearer", "none"] = "none"
    header: str | None = None


class StepDef(BaseModel):
    name: str
    description: str = ""
    entry: bool = False
    next_steps: list[str] = Field(default_factory=list)
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)


class FlowDef(BaseModel):
    name: str
    description: str = ""
    orchestration: Literal["server", "client"] = "server"
    steps: list[StepDef] = Field(default_factory=list)


class IntentDef(BaseModel):
    name: str
    description: str = ""
    endpoint: str
    method: Literal["POST"] = "POST"
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)


class Manifest(BaseModel):
    agent_api_version: str = "1.0"
    name: str
    description: str = ""
    base_url: str = ""
    auth: AuthDef = Field(default_factory=AuthDef)
    intents: list[IntentDef] = Field(default_factory=list)
    flows: list[FlowDef] = Field(default_factory=list)
