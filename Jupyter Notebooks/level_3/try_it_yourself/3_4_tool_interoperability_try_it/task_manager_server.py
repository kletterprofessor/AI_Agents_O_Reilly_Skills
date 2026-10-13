"""
Task Manager MCP Server - Practice Exercise

Build an MCP server that provides tools for managing a task/todo list.
This exercise reinforces the FastMCP patterns from the guided practice.

Your tasks:
1. Initialize the FastMCP server
2. Implement 5 MCP tools

Tools to implement:
- add_task: Add a new task with title, priority, and optional due date
- list_tasks: List tasks with optional status filter
- complete_task: Mark a task as completed
- delete_task: Remove a task
- get_task: Get details of a specific task

Run this server:
    python task_manager_server.py

Test with the provided notebook: 3_5_mcp_server_try_it.ipynb

Estimated time: 15-20 minutes
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastmcp import FastMCP


# =============================================================================
# TODO 1: Initialize the MCP Server
# =============================================================================
# Create a FastMCP instance with:
# - name: "TaskManager"
# - instructions: A helpful description for the AI about what this server does
#
# Hint: Look at the guided practice knowledge_base_server.py for the pattern

mcp = None  # TODO: Replace with FastMCP(...)


# =============================================================================
# Storage Configuration (provided)
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
# TODO 2: Implement the MCP Tools
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
    # TODO: Implement this tool
    # 1. Validate that priority is one of: "high", "medium", "low"
    #    Return error dict if invalid
    # 2. Load existing tasks using _load_tasks()
    # 3. Generate a task ID using str(uuid4())[:8]
    # 4. Create the task dict with all required fields
    # 5. Save using _save_tasks()
    # 6. Return success response with the task
    pass


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
    # TODO: Implement this tool
    # 1. Load tasks using _load_tasks()
    # 2. Convert to list of task objects
    # 3. Apply filter if provided:
    #    - "completed": only tasks where completed=True
    #    - "pending": only tasks where completed=False
    # 4. Sort by priority (high > medium > low)
    # 5. Return the response dict
    pass


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
    # TODO: Implement this tool
    # 1. Load tasks
    # 2. Check if task_id exists, return error if not found
    # 3. Set completed=True on the task
    # 4. Save and return success response with updated task
    pass


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
    # TODO: Implement this tool
    # 1. Load tasks
    # 2. Check if task_id exists, return error if not found
    # 3. Remove the task from the dict
    # 4. Save and return success response
    pass


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
    # TODO: Implement this tool
    # 1. Load tasks
    # 2. Check if task_id exists
    # 3. Return the task if found, error message if not
    pass


# =============================================================================
# Server Entry Point
# =============================================================================

if __name__ == "__main__":
    print("Starting Task Manager MCP Server...")
    print(f"Storage location: {STORAGE_FILE}")
    mcp.run(transport="stdio")
