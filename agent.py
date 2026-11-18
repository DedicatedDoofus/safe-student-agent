"""LLM integration and command interpretation."""

from __future__ import annotations

import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from actions import ALLOWED_ACTIONS, log_event
from models import AgentCommand, GeminiCommand

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

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
7. Always include the filename for create_note and read_file actions.
8. Always include the folder_name for create_folder actions.
""".strip()


def generate_with_retry(client: genai.Client, *, contents: str, config: types.GenerateContentConfig):
    """Call Gemini again when a temporary capacity or rate-limit error occurs."""
    delays = (2, 4, 8)
    retry_markers = ("429", "500", "502", "503", "504", "UNAVAILABLE", "RESOURCE_EXHAUSTED")

    for attempt in range(len(delays) + 1):
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            message = str(exc)
            is_retryable = any(marker in message for marker in retry_markers)
            if not is_retryable or attempt == len(delays):
                raise
            log_event(
                "llm_retry",
                model=MODEL,
                attempt=attempt + 1,
                error=message,
            )
            time.sleep(delays[attempt])


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


def _extract_named_value(request: str) -> str | None:
    """Extract a simple name after words such as 'named' or 'called'."""
    match = re.search(
        r"\b(?:named|called)\s+[`\"']?([A-Za-z0-9][A-Za-z0-9_.\\/-]*)",
        request,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


def _repair_parameters(action: str, request: str, parameters: dict[str, object]) -> dict[str, object]:
    """Fill required values that an LLM may omit from an otherwise valid command."""
    repaired = dict(parameters)
    named_value = _extract_named_value(request)

    if action in {"create_note", "read_file"} and not repaired.get("filename") and named_value:
        repaired["filename"] = named_value
    elif action == "create_folder" and not repaired.get("folder_name") and named_value:
        repaired["folder_name"] = named_value

    return repaired


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
        response = generate_with_retry(
            client,
            contents=request,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=GeminiCommand,
            ),
        )
        if getattr(response, "parsed", None) is not None:
            parsed = GeminiCommand.model_validate(response.parsed)
        else:
            raw_content = getattr(response, "text", "") or ""
            parsed = GeminiCommand.model_validate_json(raw_content)

        normalized_action = parsed.action.strip().lower()
        parameters = _repair_parameters(
            normalized_action,
            request,
            parsed.parameters.model_dump(exclude_none=True),
        )
        command = AgentCommand(
            action=normalized_action,
            parameters=parameters,
            explanation=parsed.explanation,
            requires_confirmation=parsed.requires_confirmation,
        )
        if command.action not in ALLOWED_ACTIONS:
            raise ValueError(f"The LLM selected an unsupported action: {command.action}")
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
    response = generate_with_retry(
        client,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction="Summarize the user's text in three concise sentences or fewer.",
        ),
    )
    return getattr(response, "text", None) or "No summary was returned."
