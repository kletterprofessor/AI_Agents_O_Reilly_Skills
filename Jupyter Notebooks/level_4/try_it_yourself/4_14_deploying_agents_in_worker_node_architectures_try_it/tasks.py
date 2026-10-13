"""
Celery Task Definitions for Agent Worker

This module defines Celery tasks that run on worker nodes.

=============================================================================
TRY IT YOURSELF: Add a New Celery Task
=============================================================================

OBJECTIVE:
    Add a new Celery task called `run_simple_search_task` that uses the
    simple Tavily search agent (provided in simple_agent.py).

YOUR TASK:
    1. Import run_simple_search from simple_agent.py
    2. Create a new Celery task called run_simple_search_task
    3. The task should:
       - Accept task_id and query parameters
       - Call run_simple_search() with a progress callback
       - Save the result to the database
       - Handle errors appropriately

HINTS:
    - Look at run_agent_task below as a template
    - The simple agent returns: {"query": ..., "answer": ..., "tool_used": ...}
    - Save the result with: save_task_result(task_id, {...})

=============================================================================

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

# TODO: Import run_simple_search from simple_agent
# from simple_agent import run_simple_search

# Load environment variables
load_dotenv()

# -----------------------------------------------------------------------------
# Celery Configuration
# -----------------------------------------------------------------------------

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "agent_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    result_expires=3600,
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
)


# -----------------------------------------------------------------------------
# Existing Task: Full Task Decomposition Agent
# -----------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_agent_task(self, task_id: str, query: str):
    """
    Celery task that executes the full task decomposition agent.
    This is the EXISTING task - use it as a template for your new task.
    """
    execution_strategy = None

    def on_progress(status: str, progress: str | None):
        nonlocal execution_strategy
        if progress and "parallel" in progress:
            execution_strategy = "parallel"
        elif progress and ("sequential" in progress or "step" in progress):
            execution_strategy = "sequential"
        update_task_status(task_id, status, progress, execution_strategy)

    try:
        result = run_task_decomposition(query, on_progress=on_progress)

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
        save_task_error(task_id, str(e))
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
            }


# -----------------------------------------------------------------------------
# TODO: Add Your New Task Here
# -----------------------------------------------------------------------------

# @celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
# def run_simple_search_task(self, task_id: str, query: str):
#     """
#     Celery task that executes the simple Tavily search agent.
#
#     This is a simpler, faster alternative to the full task decomposition.
#     It performs a single web search and returns a summarized answer.
#
#     Args:
#         self: Celery task instance (for retry functionality)
#         task_id: Unique task identifier
#         query: The user's search query
#
#     Returns:
#         Dict with task_id, status, and whether tools were used
#     """
#     # ==========================================================================
#     # YOUR CODE HERE
#     # ==========================================================================
#
#     # Step 1: Create a progress callback function
#     # def on_progress(status: str, progress: str | None):
#     #     update_task_status(task_id, status, progress)
#
#     # Step 2: Try to run the simple search agent
#     # try:
#     #     result = run_simple_search(query, on_progress=on_progress)
#     #
#     #     # Step 3: Save the result to database
#     #     save_task_result(task_id, {
#     #         "query": result["query"],
#     #         "answer": result["answer"],
#     #         "tool_used": result["tool_used"],
#     #     })
#     #
#     #     return {"task_id": task_id, "status": "completed"}
#     #
#     # except Exception as e:
#     #     # Step 4: Handle errors
#     #     save_task_error(task_id, str(e))
#     #     try:
#     #         raise self.retry(exc=e)
#     #     except self.MaxRetriesExceededError:
#     #         return {"task_id": task_id, "status": "failed", "error": str(e)}
#
#     # ==========================================================================
#     # END YOUR CODE
#     # ==========================================================================
#     pass


# -----------------------------------------------------------------------------
# Health Check Task
# -----------------------------------------------------------------------------

@celery_app.task
def health_check():
    """Simple task to verify workers are running."""
    return "ok"
