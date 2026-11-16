"""Allowlisted, validated actions for the student productivity agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database import add_task, initialize_database, list_tasks
from models import ActionResult, AgentCommand


BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / "agent_workspace"
LOG_PATH = BASE_DIR / "action_log.txt"
MAX_TEXT_LENGTH = 100_000

ALLOWED_ACTIONS = {
    "create_note",
    "read_file",
    "list_files",
    "add_task",
    "list_tasks",
    "summarize_text",
    "create_folder",
}


def initialize_storage() -> None:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    initialize_database()


def log_event(event: str, **details: Any) -> None:
    """Write one JSON object per line for auditability."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **details,
    }
    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, default=str) + "\n")


def safe_path(relative_path: str) -> Path:
    """Return a path inside agent_workspace or raise a safety error."""
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("A non-empty relative path is required.")

    candidate_text = relative_path.strip().replace("\\", "/")
    candidate = Path(candidate_text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Unsafe path. Use a relative path inside agent_workspace.")

    resolved_workspace = WORKSPACE_DIR.resolve()
    resolved_candidate = (WORKSPACE_DIR / candidate).resolve()
    try:
        resolved_candidate.relative_to(resolved_workspace)
    except ValueError as exc:
        raise ValueError("Unsafe path outside agent_workspace.") from exc
    return resolved_candidate


def require_string(parameters: dict[str, Any], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Parameter '{name}' must be a non-empty string.")
    return value.strip()


def create_note(parameters: dict[str, Any]) -> ActionResult:
    filename = require_string(parameters, "filename")
    content = parameters.get("content", "")
    if not isinstance(content, str):
        raise ValueError("Parameter 'content' must be text.")
    if len(content) > MAX_TEXT_LENGTH:
        raise ValueError("Note content is too long.")

    path = safe_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return ActionResult(success=True, message=f"Created note: {filename}", data={"path": filename})


def read_file(parameters: dict[str, Any]) -> ActionResult:
    filename = require_string(parameters, "filename")
    path = safe_path(filename)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: {filename}")
    content = path.read_text(encoding="utf-8")
    if len(content) > MAX_TEXT_LENGTH:
        raise ValueError("File is too large to display.")
    return ActionResult(success=True, message=f"Read file: {filename}", data=content)


def list_files(_: dict[str, Any]) -> ActionResult:
    files = sorted(
        str(path.relative_to(WORKSPACE_DIR))
        for path in WORKSPACE_DIR.rglob("*")
        if path.is_file()
    )
    return ActionResult(success=True, message=f"Found {len(files)} file(s).", data=files)


def add_task_action(parameters: dict[str, Any]) -> ActionResult:
    title = require_string(parameters, "title")
    due_date = parameters.get("due_date")
    if due_date is not None and not isinstance(due_date, str):
        raise ValueError("Parameter 'due_date' must be text or null.")
    task = add_task(title, due_date.strip() if due_date else None)
    return ActionResult(success=True, message="Task added.", data=task)


def list_tasks_action(_: dict[str, Any]) -> ActionResult:
    tasks = list_tasks()
    return ActionResult(success=True, message=f"Found {len(tasks)} task(s).", data=tasks)


def summarize_text_action(parameters: dict[str, Any]) -> ActionResult:
    from agent import summarize_text

    text = require_string(parameters, "text")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError("Text to summarize is too long.")
    summary = summarize_text(text)
    return ActionResult(success=True, message="Summary created.", data=summary)


def create_folder(parameters: dict[str, Any]) -> ActionResult:
    folder_name = require_string(parameters, "folder_name")
    path = safe_path(folder_name)
    path.mkdir(parents=True, exist_ok=False)
    return ActionResult(success=True, message=f"Created folder: {folder_name}", data={"path": folder_name})


def execute_action(command: AgentCommand, confirmed: bool = False) -> dict[str, Any]:
    """Validate and execute an allowlisted command."""
    initialize_storage()
    action = command.action.strip().lower()
    if action not in ALLOWED_ACTIONS:
        message = f"Blocked unknown action: {action}"
        log_event("blocked", action=action, reason="not_allowlisted")
        return ActionResult(success=False, message=message).model_dump()

    if command.requires_confirmation and not confirmed:
        message = "Confirmation is required before this action can run."
        log_event("awaiting_confirmation", action=action, parameters=command.parameters)
        return ActionResult(success=False, message=message).model_dump()

    handlers = {
        "create_note": create_note,
        "read_file": read_file,
        "list_files": list_files,
        "add_task": add_task_action,
        "list_tasks": list_tasks_action,
        "summarize_text": summarize_text_action,
        "create_folder": create_folder,
    }

    try:
        result = handlers[action](command.parameters)
        log_event(
            "completed",
            action=action,
            parameters=command.parameters,
            confirmed=confirmed,
            success=result.success,
        )
        return result.model_dump()
    except Exception as exc:
        log_event(
            "error",
            action=action,
            parameters=command.parameters,
            confirmed=confirmed,
            error=str(exc),
        )
        return ActionResult(success=False, message=str(exc)).model_dump()
