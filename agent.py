"""LLM integration and command interpretation."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from actions import ALLOWED_ACTIONS, log_event
from models import AgentCommand

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """
You are the command interpreter for Safe Student Productivity Agent.

Return only valid JSON with exactly these top-level fields:
{
  "action": "one approved action",
  "parameters": {},
  "explanation": "brief explanation",
  "requires_confirmation": false
}

Approved actions and parameters:
- create_note: {"filename": "notes.txt", "content": "text"}
- read_file: {"filename": "notes.txt"}
- list_files: {}
- add_task: {"title": "task text", "due_date": "optional date or null"}
- list_tasks: {}
- summarize_text: {"text": "text to summarize"}
- create_folder: {"folder_name": "folder name"}

Rules:
1. Never invent an action outside the approved list.
2. Never create shell commands.
3. Never select a delete action because deletion is not supported.
4. Use relative filenames only. Do not use absolute paths or paths containing ..
5. If the request is unclear, choose no approved action and explain what information is missing.
6. Set requires_confirmation to true for any destructive action. The current approved actions are non-destructive.
""".strip()


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=api_key)


def _demo_command(request: str) -> AgentCommand:
    """Provide predictable sample behavior when no API key is configured."""
    lowered = request.lower()
    if any(word in lowered for word in ("list", "show", "display", "see")) and "file" in lowered:
        return AgentCommand(action="list_files", explanation="Demo mode selected file listing.")
    if any(word in lowered for word in ("list", "show", "display", "see")) and "task" in lowered:
        return AgentCommand(action="list_tasks", explanation="Demo mode selected task listing.")
    if "add" in lowered and "task" in lowered:
        title = request.split("task", 1)[-1].strip(" :.-") or "Study programming languages"
        return AgentCommand(
            action="add_task",
            parameters={"title": title, "due_date": None},
            explanation="Demo mode selected task creation.",
        )
    if "folder" in lowered:
        return AgentCommand(
            action="create_folder",
            parameters={"folder_name": "exam_notes"},
            explanation="Demo mode selected folder creation.",
        )
    if "summarize" in lowered or "summary" in lowered:
        text = request.split(":", 1)[-1].strip() if ":" in request else request
        return AgentCommand(
            action="summarize_text",
            parameters={"text": text},
            explanation="Demo mode selected text summarization; an API key is required to call the LLM.",
        )
    return AgentCommand(
        action="create_note",
        parameters={
            "filename": "demo_note.txt",
            "content": f"Demo note created from request: {request}",
        },
        explanation="Demo mode selected note creation.",
    )


def interpret_request(request: str) -> AgentCommand:
    """Ask the LLM for a command and validate the returned JSON."""
    if not request.strip():
        raise ValueError("Request cannot be empty.")

    if not os.getenv("GEMINI_API_KEY"):
        command = _demo_command(request)
        log_event("interpreted_demo", request=request, command=command.model_dump())
        return command

    try:
        client = get_client()
        response = client.models.generate_content(
            model=MODEL,
            contents=request,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=AgentCommand,
                temperature=0,
            ),
        )
        if getattr(response, "parsed", None) is not None:
            command = AgentCommand.model_validate(response.parsed)
        else:
            raw_content = getattr(response, "text", "") or ""
            command = AgentCommand.model_validate_json(raw_content)
        if command.action.strip().lower() not in ALLOWED_ACTIONS:
            raise ValueError(f"The LLM selected an unsupported action: {command.action}")
        command.action = command.action.strip().lower()
        log_event("interpreted", request=request, command=command.model_dump())
        return command
    except ValidationError as exc:
        log_event("llm_error", request=request, error=str(exc))
        raise RuntimeError(f"The LLM returned an invalid command: {exc}") from exc
    except Exception as exc:
        log_event("llm_error", request=request, error=str(exc))
        raise RuntimeError(f"The Gemini request failed: {exc}") from exc


def summarize_text(text: str) -> str:
    """Summarize text through the same configured LLM."""
    client = get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction="Summarize the user's text in three concise sentences or fewer.",
            temperature=0.2,
        ),
    )
    return getattr(response, "text", None) or "No summary was returned."
