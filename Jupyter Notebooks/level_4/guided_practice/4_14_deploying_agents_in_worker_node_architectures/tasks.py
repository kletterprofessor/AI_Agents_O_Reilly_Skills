"""
Celery Task Definitions for Agent Worker

This module defines Celery tasks that run on worker nodes, separate from
the FastAPI web server. Workers pull tasks from Redis and execute the
long-running agent logic.

Architecture:
    Client -> FastAPI -> Redis Queue -> Celery Worker -> SQLite (results)

To run a worker:
    celery -A tasks worker --loglevel=info
"""

import os

from celery import Celery
from dotenv import load_dotenv

from database import (
    update_task_status,
    save_task_result,
    save_task_error,
)
from agent import run_task_decomposition

# Load environment variables
load_dotenv()

# -----------------------------------------------------------------------------
# Celery Configuration
# -----------------------------------------------------------------------------

# Redis URLs - configurable via environment variables for Docker
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Create Celery app with Redis as broker and backend
# Redis serves as both the message queue and result backend
celery_app = Celery(
    "agent_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Configure Celery
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Task settings
    task_track_started=True,           # Track when tasks start
    task_time_limit=600,               # Hard limit: 10 minutes
    task_soft_time_limit=540,          # Soft limit: 9 minutes (raises exception)

    # Result settings
    result_expires=3600,               # Results expire after 1 hour

    # Worker settings
    worker_prefetch_multiplier=1,      # Fetch one task at a time (good for slow tasks)
    worker_concurrency=2,              # Number of concurrent workers
)


# -----------------------------------------------------------------------------
# Agent Task Definition
# -----------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_agent_task(self, task_id: str, query: str):
    """
    Celery task that executes the task decomposition agent.

    This task runs on a worker node, separate from the FastAPI server.
    It updates the SQLite database with progress so the API can report status.

    Args:
        self: Celery task instance (for retry functionality)
        task_id: Unique task identifier
        query: The user's query to process

    Features:
        - Automatic retry on failure (max 2 retries)
        - Progress updates to database
        - Time limits to prevent runaway tasks
    """
    execution_strategy = None

    def on_progress(status: str, progress: str | None):
        """Callback to update task progress in the database."""
        nonlocal execution_strategy

        # Extract execution strategy from progress if present
        if progress and "parallel" in progress:
            execution_strategy = "parallel"
        elif progress and ("sequential" in progress or "step" in progress):
            execution_strategy = "sequential"

        # Update database so API can report progress
        update_task_status(task_id, status, progress, execution_strategy)

    try:
        # Run the agent with progress callback
        result = run_task_decomposition(query, on_progress=on_progress)

        # Save the final result to SQLite
        save_task_result(task_id, {
            "query": result["query"],
            "execution_strategy": result["execution_strategy"],
            "final_answer": result["final_answer"],
        })

        return {
            "task_id": task_id,
            "status": "completed",
            "execution_strategy": result["execution_strategy"],
        }

    except Exception as e:
        # Save error to database
        save_task_error(task_id, str(e))

        # Retry the task if we haven't exceeded max retries
        # This is useful for transient errors (network issues, rate limits)
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            # Max retries exceeded, task has permanently failed
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
            }


# -----------------------------------------------------------------------------
# Health Check Task
# -----------------------------------------------------------------------------

@celery_app.task
def health_check():
    """
    Simple task to verify workers are running and can process jobs.

    Usage:
        from tasks import health_check
        result = health_check.delay()
        print(result.get(timeout=10))  # Should print "ok"
    """
    return "ok"
