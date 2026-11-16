"""Small SQLite data layer for student tasks."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tasks.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


def add_task(title: str, due_date: str | None = None) -> dict[str, Any]:
    title = title.strip()
    if not title:
        raise ValueError("Task title cannot be empty.")
    if len(title) > 300:
        raise ValueError("Task title is too long.")

    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, due_date, created_at) VALUES (?, ?, ?)",
            (title, due_date, created_at),
        )
        task_id = cursor.lastrowid
    return {"id": task_id, "title": title, "due_date": due_date, "created_at": created_at}


def list_tasks() -> list[dict[str, Any]]:
    initialize_database()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, due_date, created_at FROM tasks ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]
