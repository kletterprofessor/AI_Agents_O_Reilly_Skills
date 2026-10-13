"""
FastAPI Server for Long-Running Agentic Tasks

This server implements the polling pattern for long-running agent tasks:
- POST /tasks: Submit a new task, returns task_id immediately
- GET /tasks/{task_id}: Poll for task status and progress
- GET /tasks/{task_id}/result: Retrieve the final result when completed

The server runs agent tasks in the background using FastAPI's BackgroundTasks,
allowing clients to poll for progress without blocking.

Run with: uvicorn main:app --reload
Test at: http://localhost:8000/docs
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from database import (
    init_db,
    create_task,
    update_task_status,
    save_task_result,
    save_task_error,
    get_task,
    get_task_result,
)
from agent import run_task_decomposition


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
    title="Long-Running Agent Tasks API",
    description="""
    API for submitting and polling long-running agentic tasks.

    ## Polling Pattern

    1. **Submit a task**: POST /tasks with your query
    2. **Poll for status**: GET /tasks/{task_id} until status is 'completed' or 'failed'
    3. **Get the result**: GET /tasks/{task_id}/result

    The agent performs task decomposition:
    - Analyzes queries and breaks them into sub-queries
    - Executes searches sequentially or in parallel
    - Synthesizes results into comprehensive answers
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


# -----------------------------------------------------------------------------
# Background Task Runner
# -----------------------------------------------------------------------------

def run_agent_task(task_id: str, query: str):
    """
    Run the agent task in the background.

    This function is executed asynchronously by FastAPI's BackgroundTasks.
    It updates the database with progress as the agent executes.

    Args:
        task_id: Unique task identifier
        query: The user's query to process
    """
    execution_strategy = None

    def on_progress(status: str, progress: str | None):
        """Callback to update task progress in the database."""
        nonlocal execution_strategy

        # Extract execution strategy from progress if present
        if progress and "parallel" in progress:
            execution_strategy = "parallel"
        elif progress and "sequential" in progress or progress and "step" in progress:
            execution_strategy = "sequential"

        update_task_status(task_id, status, progress, execution_strategy)

    try:
        # Run the agent with progress callback
        result = run_task_decomposition(query, on_progress=on_progress)

        # Save the final result
        save_task_result(task_id, {
            "query": result["query"],
            "execution_strategy": result["execution_strategy"],
            "final_answer": result["final_answer"],
        })

    except Exception as e:
        # Save error if task fails
        save_task_error(task_id, str(e))


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Long-Running Agent Tasks API is running",
        "endpoints": {
            "submit_task": "POST /tasks",
            "poll_status": "GET /tasks/{task_id}",
            "get_result": "GET /tasks/{task_id}/result",
        }
    }


@app.post("/tasks", response_model=TaskSubmitResponse)
def submit_task(request: TaskSubmitRequest, background_tasks: BackgroundTasks):
    """
    Submit a new task for processing.

    The task will be processed in the background. Use the returned task_id
    to poll for status and retrieve results.

    Returns immediately with the task_id - does not wait for completion.
    """
    # Generate unique task ID
    task_id = str(uuid.uuid4())

    # Create task entry in database
    create_task(task_id, request.query)

    # Queue the agent task to run in background
    background_tasks.add_task(run_agent_task, task_id, request.query)

    return TaskSubmitResponse(
        task_id=task_id,
        status="pending",
        message="Task submitted successfully. Poll GET /tasks/{task_id} for status."
    )


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    """
    Poll the status of a task.

    Status values:
    - **pending**: Task is queued but not started
    - **running**: Task is being processed (check 'progress' for details)
    - **completed**: Task finished successfully (use /tasks/{task_id}/result to get result)
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


# -----------------------------------------------------------------------------
# Run with uvicorn
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
