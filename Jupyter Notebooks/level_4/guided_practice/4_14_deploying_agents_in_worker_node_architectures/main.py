"""
FastAPI Server for Worker Node Architecture

This server demonstrates the worker node pattern:
- FastAPI handles HTTP requests and stays responsive
- Long-running agent tasks are queued to Celery/Redis
- Workers (separate processes) execute the agent logic
- Results are stored in SQLite for retrieval

Architecture:
    Client -> FastAPI -> Redis Queue -> Celery Worker -> SQLite
                  |                                        |
                  +-------- Poll /tasks/{id} <------------+

This is different from BackgroundTasks (used in 4_13):
- BackgroundTasks: runs in the same process, no queue, no retries
- Celery Workers: separate processes, persistent queue, automatic retries

Run with:
    1. Start Redis:     redis-server
    2. Start Worker:    celery -A tasks worker --loglevel=info
    3. Start API:       uvicorn main:app --reload

Test at: http://localhost:8000/docs
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from database import (
    init_db,
    create_task,
    get_task,
    get_task_result,
)
from tasks import run_agent_task


# -----------------------------------------------------------------------------
# Lifespan: Initialize database on startup
# -----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


# -----------------------------------------------------------------------------
# FastAPI App
# -----------------------------------------------------------------------------

app = FastAPI(
    title="Agent Worker Node Architecture API",
    description="""
    API demonstrating worker node architecture for long-running agent tasks.

    ## Architecture

    ```
    Client -> FastAPI -> Redis Queue -> Celery Worker -> SQLite
    ```

    ## Key Differences from BackgroundTasks

    | Aspect | BackgroundTasks | Celery Workers |
    |--------|-----------------|----------------|
    | Process | Same as FastAPI | Separate processes |
    | Queue | In-memory | Redis (persistent) |
    | Retries | Manual | Automatic |
    | Scaling | Limited | Add more workers |
    | Monitoring | None | Flower, Redis CLI |

    ## Endpoints

    - POST /tasks - Submit task to queue
    - GET /tasks/{id} - Poll status
    - GET /tasks/{id}/result - Get result
    - GET /workers/health - Check worker availability
    """,
    version="1.0.0",
    lifespan=lifespan,
)


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------

class TaskSubmitRequest(BaseModel):
    """Request model for submitting a new task."""
    query: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "What AI products were launched by the company that acquired DeepMind in 2024?"},
                {"query": "Summarize Tesla's Q4 2024 earnings, recent product launches, and leadership changes"},
            ]
        }
    }


class TaskSubmitResponse(BaseModel):
    """Response model after submitting a task."""
    task_id: str
    celery_task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    """Response model for task status polling."""
    task_id: str
    status: str
    progress: str | None = None
    execution_strategy: str | None = None
    error: str | None = None


class TaskResultResponse(BaseModel):
    """Response model for completed task result."""
    task_id: str
    query: str
    execution_strategy: str
    final_answer: str


class WorkerHealthResponse(BaseModel):
    """Response model for worker health check."""
    status: str
    message: str
    worker_available: bool


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Agent Worker Node API is running",
        "architecture": "FastAPI -> Redis -> Celery Worker -> SQLite",
        "endpoints": {
            "submit_task": "POST /tasks",
            "poll_status": "GET /tasks/{task_id}",
            "get_result": "GET /tasks/{task_id}/result",
            "worker_health": "GET /workers/health",
        }
    }


@app.post("/tasks", response_model=TaskSubmitResponse)
def submit_task(request: TaskSubmitRequest):
    """
    Submit a new task to the worker queue.

    The task is immediately queued to Redis and will be picked up by
    an available Celery worker. Returns immediately with task IDs.

    Unlike BackgroundTasks, this:
    - Persists the job in Redis (survives server restart)
    - Will be retried automatically on failure
    - Can be processed by any available worker
    """
    # Generate unique task ID
    task_id = str(uuid.uuid4())

    # Create task entry in database (for status tracking)
    create_task(task_id, request.query)

    # Enqueue the task to Celery via Redis
    # This returns immediately - the worker will process it asynchronously
    celery_result = run_agent_task.delay(task_id, request.query)

    return TaskSubmitResponse(
        task_id=task_id,
        celery_task_id=celery_result.id,
        status="queued",
        message="Task queued for processing. Poll GET /tasks/{task_id} for status."
    )


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    """
    Poll the status of a task.

    Status values:
    - **pending**: Task is queued but worker hasn't started it
    - **running**: Worker is processing the task (check 'progress' for details)
    - **completed**: Task finished successfully (use /tasks/{task_id}/result)
    - **failed**: Task failed (check 'error' for details)
    """
    task = get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        progress=task["progress"],
        execution_strategy=task["execution_strategy"],
        error=task["error"],
    )


@app.get("/tasks/{task_id}/result", response_model=TaskResultResponse)
def get_task_result_endpoint(task_id: str):
    """
    Get the result of a completed task.

    Returns 404 if task not found, 400 if task is not yet completed.
    """
    task = get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task["status"] == "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Task failed: {task['error']}"
        )

    if task["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not yet completed. Current status: {task['status']}"
        )

    result = get_task_result(task_id)

    if result is None:
        raise HTTPException(status_code=500, detail="Result not found for completed task")

    return TaskResultResponse(
        task_id=task_id,
        query=result["query"],
        execution_strategy=result["execution_strategy"],
        final_answer=result["final_answer"],
    )


@app.get("/workers/health", response_model=WorkerHealthResponse)
def check_worker_health():
    """
    Check if Celery workers are available and responsive.

    Sends a health check task to the queue and waits for response.
    This verifies the full path: API -> Redis -> Worker -> Response.
    """
    from tasks import health_check as worker_health_check

    try:
        # Send health check task and wait for result (max 5 seconds)
        result = worker_health_check.delay()
        response = result.get(timeout=5)

        if response == "ok":
            return WorkerHealthResponse(
                status="ok",
                message="Worker is responsive",
                worker_available=True
            )
        else:
            return WorkerHealthResponse(
                status="warning",
                message=f"Unexpected response: {response}",
                worker_available=True
            )

    except Exception as e:
        return WorkerHealthResponse(
            status="error",
            message=f"Worker not available: {str(e)}",
            worker_available=False
        )


# -----------------------------------------------------------------------------
# Run with uvicorn
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
