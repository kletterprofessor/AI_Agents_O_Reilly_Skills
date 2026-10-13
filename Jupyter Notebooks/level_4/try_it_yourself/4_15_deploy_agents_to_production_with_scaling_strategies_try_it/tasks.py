"""
Celery Task Definitions with Stateless Worker Design

This module defines Celery tasks that run on worker nodes following
stateless design principles:

1. Workers have NO local state
2. All context is fetched from external stores (Redis, DB)
3. Results are saved back to external stores
4. Any worker can handle any task (no sticky sessions)

Why Stateless?
- Horizontal scaling: Just add more workers
- Fault tolerance: If a worker crashes, job re-queues to another
- Zero-downtime deployments: Drain workers gracefully
- Load balancing: Round-robin without session affinity

To run a worker:
    celery -A tasks worker --loglevel=info
"""

import os
from typing import Optional

from celery import Celery
from dotenv import load_dotenv

from database import (
    update_task_status,
    save_task_result,
    save_task_error,
)
from state_store import (
    get_conversation_history,
    store_message,
    get_conversation_formatted_for_llm,
)
from agent import run_task_decomposition

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
    # Task timeout (10 minutes max for agent tasks)
    task_time_limit=600,
    task_soft_time_limit=540,
    # Result expiration (1 hour)
    result_expires=3600,
    # Worker settings for horizontal scaling
    worker_prefetch_multiplier=1,  # Fair distribution across workers
    worker_concurrency=2,  # Limit concurrent tasks per worker
    # Acknowledge tasks after completion (for fault tolerance)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


# -----------------------------------------------------------------------------
# Stateless Agent Task
# -----------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_agent_task(
    self,
    task_id: str,
    user_id: str,
    query: str,
    conversation_id: Optional[str] = None
):
    """
    Celery task that executes the task decomposition agent.

    STATELESS DESIGN:
    - Fetches conversation history from Redis (not local memory)
    - Runs agent with external context
    - Saves results back to external stores
    - Any worker can execute this task

    Args:
        self: Celery task instance (for retry functionality)
        task_id: Unique task identifier
        user_id: User who submitted the task
        query: The user's query to process
        conversation_id: Optional conversation for context

    Returns:
        Dict with task_id, status, and execution details
    """
    execution_strategy = None

    # Progress callback updates external database (not local state)
    def on_progress(status: str, progress: str | None):
        nonlocal execution_strategy
        if progress and "parallel" in progress:
            execution_strategy = "parallel"
        elif progress and ("sequential" in progress or "step" in progress):
            execution_strategy = "sequential"
        # Update external database - any API server can read this
        update_task_status(task_id, status, progress, execution_strategy)

    try:
        # STATELESS: Fetch conversation history from Redis
        history = []
        if conversation_id:
            history = get_conversation_formatted_for_llm(
                user_id,
                conversation_id,
                system_prompt="You are a helpful research assistant."
            )

        # Run the agent (agent is also stateless - all context passed in)
        result = run_task_decomposition(
            query,
            on_progress=on_progress,
            conversation_history=history
        )

        # STATELESS: Save result to external database
        save_task_result(task_id, {
            "query": result["query"],
            "execution_strategy": result["execution_strategy"],
            "final_answer": result["final_answer"],
        })

        # STATELESS: Save assistant response to Redis conversation history
        if conversation_id:
            store_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role="assistant",
                content=result["final_answer"],
                metadata={
                    "task_id": task_id,
                    "execution_strategy": result["execution_strategy"]
                }
            )

        return {
            "task_id": task_id,
            "user_id": user_id,
            "status": "completed",
            "execution_strategy": result["execution_strategy"],
        }

    except Exception as e:
        # STATELESS: Save error to external database
        save_task_error(task_id, str(e))

        try:
            # Retry will pick up a potentially different worker
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "task_id": task_id,
                "user_id": user_id,
                "status": "failed",
                "error": str(e),
            }


# -----------------------------------------------------------------------------
# Health Check Task
# -----------------------------------------------------------------------------

@celery_app.task
def health_check():
    """Simple task to verify workers are running."""
    return "ok"


# -----------------------------------------------------------------------------
# Graceful Shutdown Support
# -----------------------------------------------------------------------------

from celery.signals import worker_shutting_down


@worker_shutting_down.connect
def worker_shutting_down_handler(sig, how, exitcode, **kwargs):
    """
    Handle worker shutdown gracefully.

    This ensures:
    - Current tasks complete before worker exits
    - No tasks are lost during deployment

    Usage:
        celery -A tasks worker --loglevel=info

    To stop gracefully:
        celery -A tasks control shutdown
    """
    print("Worker shutting down... finishing current tasks")
