"""
SQLite Database Operations for Task Persistence

This module handles all database operations for storing and retrieving
long-running task states and results.
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

# Database path - configurable via environment variable for Docker
# In Docker, this points to a shared volume between API and worker
DATABASE_PATH = os.getenv("DATABASE_PATH", "tasks.db")


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database and create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                progress TEXT,
                execution_strategy TEXT,
                result TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def create_task(task_id: str, query: str) -> dict:
    """
    Create a new task entry in the database.

    Args:
        task_id: Unique identifier for the task
        query: The user's query to process

    Returns:
        Dictionary with task_id and initial status
    """
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO tasks (task_id, query, status, created_at, updated_at)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (task_id, query, datetime.now(), datetime.now())
        )
        conn.commit()

    return {"task_id": task_id, "status": "pending"}


def update_task_status(
    task_id: str,
    status: str,
    progress: Optional[str] = None,
    execution_strategy: Optional[str] = None
):
    """
    Update the status and progress of a task.

    Args:
        task_id: Task identifier
        status: New status (pending, running, completed, failed)
        progress: Optional progress description
        execution_strategy: Optional execution strategy (sequential, parallel)
    """
    with get_connection() as conn:
        if execution_strategy:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, progress = ?, execution_strategy = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (status, progress, execution_strategy, datetime.now(), task_id)
            )
        else:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, progress = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (status, progress, datetime.now(), task_id)
            )
        conn.commit()


def save_task_result(task_id: str, result: dict):
    """
    Save the final result of a completed task.

    Args:
        task_id: Task identifier
        result: Dictionary containing the task result
    """
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET status = 'completed', result = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (json.dumps(result), datetime.now(), task_id)
        )
        conn.commit()


def save_task_error(task_id: str, error: str):
    """
    Save error information for a failed task.

    Args:
        task_id: Task identifier
        error: Error message
    """
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET status = 'failed', error = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (error, datetime.now(), task_id)
        )
        conn.commit()


def get_task(task_id: str) -> Optional[dict]:
    """
    Retrieve a task by its ID.

    Args:
        task_id: Task identifier

    Returns:
        Task dictionary or None if not found
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "task_id": row["task_id"],
            "query": row["query"],
            "status": row["status"],
            "progress": row["progress"],
            "execution_strategy": row["execution_strategy"],
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }


def get_task_result(task_id: str) -> Optional[dict]:
    """
    Retrieve the result of a completed task.

    Args:
        task_id: Task identifier

    Returns:
        Result dictionary or None if not found/not completed
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT result, status FROM tasks WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()

        if row is None:
            return None

        if row["status"] != "completed":
            return None

        if row["result"]:
            return json.loads(row["result"])

        return None
