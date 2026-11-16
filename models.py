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


class GeminiParameters(BaseModel):
    """Fixed parameter shape used for Gemini structured output.

    Gemini does not accept an unrestricted JSON object with
    ``additionalProperties`` in a response schema, so the LLM-facing model
    lists every parameter supported by the application explicitly.
    """

    filename: str | None = None
    content: str | None = None
    title: str | None = None
    due_date: str | None = None
    text: str | None = None
    folder_name: str | None = None


class GeminiCommand(BaseModel):
    """Gemini-compatible structured command schema."""

    action: str = Field(min_length=1)
    parameters: GeminiParameters = Field(default_factory=GeminiParameters)
    explanation: str = Field(default="", max_length=500)
    requires_confirmation: bool = False


class ActionResult(BaseModel):
    """A consistent result returned to the user interface."""

    success: bool
    message: str
    data: Any = None
