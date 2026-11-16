"""Pydantic models used to validate LLM commands and action results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentCommand(BaseModel):
    """The only shape of command accepted from the LLM."""

    action: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(default="", max_length=500)
    requires_confirmation: bool = False


class ActionResult(BaseModel):
    """A consistent result returned to the user interface."""

    success: bool
    message: str
    data: Any = None
