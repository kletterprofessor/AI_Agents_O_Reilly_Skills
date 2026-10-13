"""
Task Manager MCP Server - Solution

A complete MCP server that provides tools for managing a task/todo list.

Tools provided:
- add_task: Add a new task with title, priority, and optional due date
- list_tasks: List tasks with optional status filter
- complete_task: Mark a task as completed
- delete_task: Remove a task
- get_task: Get details of a specific task

Run this server:
    python task_manager_server_solution.py
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastmcp import FastMCP


# =============================================================================
# MCP Server Setup
# =============================================================================

mcp = FastMCP(
    name="TaskManager",
    instructions="""You are connected to a Task Manager server that helps manage tasks and todos.
    Use the available tools to add, list, complete, and delete tasks.
    Tasks have priorities (high, medium, low) and can have optional due dates."""
)


# =============================================================================
# Storage Configuration
# =============================================================================

STORAGE_DIR = Path(__file__).parent / "data"
STORAGE_FILE = STORAGE_DIR / "tasks.json"


def _ensure_storage():
    """Ensure the storage directory and file exist."""
    STORAGE_DIR.mkdir(exist_ok=True)
    if not STORAGE_FILE.exists():
        STORAGE_FILE.write_text(json.dumps({"tasks": {}}, indent=2))


def _load_tasks() -> dict:
    """Load tasks from storage."""
    _ensure_storage()
    return json.loads(STORAGE_FILE.read_text())


def _save_tasks(data: dict):
    """Save tasks to storage."""
    _ensure_storage()
    STORAGE_FILE.write_text(json.dumps(data, indent=2))


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool()
def add_task(
    title: str,
    priority: str = "medium",
    due_date: Optional[str] = None
) -> dict:
    """
    Add a new task to the task manager.

    Args:
        title: The title/description of the task
        priority: Priority level - must be "high", "medium", or "low" (default: "medium")
        due_date: Optional due date in YYYY-MM-DD format (e.g., "2025-12-31")

    Returns:
        A dict with:
        - "status": "success" or "error"
        - "message": Description of what happened
        - "task": The created task object (if successful) containing:
            - id: 8-character unique ID
            - title: The task title
            - priority: The priority level
            - due_date: The due date or None
            - completed: False (new tasks start incomplete)
            - created_at: ISO timestamp
    """
    # Validate priority
    valid_priorities = ["high", "medium", "low"]
    if priority not in valid_priorities:
        return {
            "status": "error",
            "message": f"Invalid priority '{priority}'. Must be one of: {valid_priorities}"
        }

    data = _load_tasks()

    task_id = str(uuid4())[:8]
    timestamp = datetime.now().isoformat()

    task = {
        "id": task_id,
        "title": title,
        "priority": priority,
        "due_date": due_date,
        "completed": False,
        "created_at": timestamp
    }

    data["tasks"][task_id] = task
    _save_tasks(data)

    return {
        "status": "success",
        "message": f"Task '{title}' added successfully",
        "task": task
    }


@mcp.tool()
def list_tasks(status_filter: Optional[str] = None) -> dict:
    """
    List all tasks, optionally filtered by completion status.

    Args:
        status_filter: Optional filter - "completed", "pending", or None for all tasks

    Returns:
        A dict with:
        - "status": "success"
        - "total_count": Total number of tasks in storage
        - "returned_count": Number of tasks after filtering
        - "filter_applied": The filter that was used (or None)
        - "tasks": List of task objects sorted by priority (high first)
    """
    data = _load_tasks()
    tasks = list(data["tasks"].values())

    # Apply status filter
    if status_filter == "completed":
        tasks = [t for t in tasks if t["completed"]]
    elif status_filter == "pending":
        tasks = [t for t in tasks if not t["completed"]]

    # Sort by priority (high > medium > low)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    tasks.sort(key=lambda x: priority_order.get(x["priority"], 1))

    return {
        "status": "success",
        "total_count": len(data["tasks"]),
        "returned_count": len(tasks),
        "filter_applied": status_filter,
        "tasks": tasks
    }


@mcp.tool()
def complete_task(task_id: str) -> dict:
    """
    Mark a task as completed.

    Args:
        task_id: The unique identifier of the task to complete

    Returns:
        A dict with:
        - "status": "success" or "error"
        - "message": Description of what happened
        - "task": The updated task object (if successful)
    """
    data = _load_tasks()

    if task_id not in data["tasks"]:
        return {
            "status": "error",
            "message": f"Task with ID '{task_id}' not found"
        }

    task = data["tasks"][task_id]
    task["completed"] = True
    _save_tasks(data)

    return {
        "status": "success",
        "message": f"Task '{task['title']}' marked as completed",
        "task": task
    }


@mcp.tool()
def delete_task(task_id: str) -> dict:
    """
    Delete a task from the task manager.

    Args:
        task_id: The unique identifier of the task to delete

    Returns:
        A dict with:
        - "status": "success" or "error"
        - "message": Description of what happened (include task title if deleted)
    """
    data = _load_tasks()

    if task_id not in data["tasks"]:
        return {
            "status": "error",
            "message": f"Task with ID '{task_id}' not found"
        }

    deleted_task = data["tasks"].pop(task_id)
    _save_tasks(data)

    return {
        "status": "success",
        "message": f"Task '{deleted_task['title']}' (ID: {task_id}) deleted successfully"
    }


@mcp.tool()
def get_task(task_id: str) -> dict:
    """
    Get details of a specific task by ID.

    Args:
        task_id: The unique identifier of the task

    Returns:
        A dict with:
        - "status": "success" or "error"
        - "task": The task object (if found)
        - "message": Error message (if not found)
    """
    data = _load_tasks()

    if task_id in data["tasks"]:
        return {
            "status": "success",
            "task": data["tasks"][task_id]
        }

    return {
        "status": "error",
        "message": f"Task with ID '{task_id}' not found"
    }


# =============================================================================
# Server Entry Point
# =============================================================================

if __name__ == "__main__":
    print("Starting Task Manager MCP Server...")
    print(f"Storage location: {STORAGE_FILE}")
    mcp.run(transport="stdio")
