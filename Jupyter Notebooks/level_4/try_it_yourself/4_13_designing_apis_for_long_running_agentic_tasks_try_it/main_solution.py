"""
FastAPI Server for Long-Running Agentic Tasks - SOLUTION

This is the complete solution with SSE streaming implemented.

Run with: uvicorn main_solution:app --reload
Test at: http://localhost:8000/docs
"""

import uuid
import json
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

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
    title="Long-Running Agent Tasks API (with SSE Streaming)",
    description="""
    API for submitting and monitoring long-running agentic tasks.

    ## Patterns Supported

    ### 1. Polling Pattern
    - POST /tasks - Submit task
    - GET /tasks/{task_id} - Poll status
    - GET /tasks/{task_id}/result - Get result

    ### 2. SSE Streaming Pattern
    - GET /tasks/{task_id}/stream - Real-time progress via Server-Sent Events
    """,
    version="1.0.0",
    lifespan=lifespan,
)


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------

class TaskSubmitRequest(BaseModel):
    query: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "What AI products were launched by the company that acquired DeepMind in 2024?"},
            ]
        }
    }


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: str | None = None
    execution_strategy: str | None = None
    error: str | None = None


class TaskResultResponse(BaseModel):
    task_id: str
    query: str
    execution_strategy: str
    final_answer: str


# -----------------------------------------------------------------------------
# Background Task Runner
# -----------------------------------------------------------------------------

def run_agent_task(task_id: str, query: str):
    """Run the agent task in the background."""
    execution_strategy = None

    def on_progress(status: str, progress: str | None):
        nonlocal execution_strategy
        if progress and "parallel" in progress:
            execution_strategy = "parallel"
        elif progress and "sequential" in progress or progress and "step" in progress:
            execution_strategy = "sequential"
        update_task_status(task_id, status, progress, execution_strategy)

    try:
        result = run_task_decomposition(query, on_progress=on_progress)
        save_task_result(task_id, {
            "query": result["query"],
            "execution_strategy": result["execution_strategy"],
            "final_answer": result["final_answer"],
        })
    except Exception as e:
        save_task_error(task_id, str(e))


# -----------------------------------------------------------------------------
# Polling Endpoints
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
            "stream_status": "GET /tasks/{task_id}/stream",
        }
    }


@app.post("/tasks", response_model=TaskSubmitResponse)
def submit_task(request: TaskSubmitRequest, background_tasks: BackgroundTasks):
    """Submit a new task for processing."""
    task_id = str(uuid.uuid4())
    create_task(task_id, request.query)
    background_tasks.add_task(run_agent_task, task_id, request.query)

    return TaskSubmitResponse(
        task_id=task_id,
        status="pending",
        message="Task submitted. Use GET /tasks/{task_id}/stream for real-time updates!"
    )


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    """Poll the status of a task."""
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
    """Get the result of a completed task."""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task["status"] == "failed":
        raise HTTPException(status_code=400, detail=f"Task failed: {task['error']}")

    if task["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not yet completed. Current status: {task['status']}"
        )

    result = get_task_result(task_id)
    if result is None:
        raise HTTPException(status_code=500, detail="Result not found")

    return TaskResultResponse(
        task_id=task_id,
        query=result["query"],
        execution_strategy=result["execution_strategy"],
        final_answer=result["final_answer"],
    )


# -----------------------------------------------------------------------------
# SSE Streaming Endpoint - SOLUTION
# -----------------------------------------------------------------------------

@app.get("/tasks/{task_id}/stream")
async def stream_task_status(task_id: str, interval: float = 0.5):
    """
    Stream task status updates via Server-Sent Events (SSE).

    Args:
        task_id: The task identifier
        interval: Poll interval in seconds (default: 0.5)

    Returns:
        EventSourceResponse with real-time status updates

    Events:
        - status: Progress update {"status": "running", "progress": "..."}
        - complete: Task finished {"status": "completed", "final_answer": "..."}
        - error: Task failed {"status": "failed", "error": "..."}
        - heartbeat: Keep-alive ping (every 15 seconds)
    """
    # Check if task exists
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    async def event_generator():
        """
        Async generator that yields SSE events as task progresses.
        """
        last_progress = None
        last_status = None
        heartbeat_counter = 0
        heartbeat_interval = 30  # Send heartbeat every 30 polls (15 seconds at 0.5s interval)

        while True:
            # Get current task state
            task = get_task(task_id)

            if task is None:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Task not found"})
                }
                break

            status = task["status"]
            progress = task["progress"]
            execution_strategy = task["execution_strategy"]

            # Send status update if progress changed
            if progress != last_progress or status != last_status:
                yield {
                    "event": "status",
                    "data": json.dumps({
                        "status": status,
                        "progress": progress,
                        "execution_strategy": execution_strategy
                    })
                }
                last_progress = progress
                last_status = status

            # Check for terminal states
            if status == "completed":
                result = get_task_result(task_id)
                yield {
                    "event": "complete",
                    "data": json.dumps({
                        "status": "completed",
                        "query": result["query"] if result else "",
                        "execution_strategy": result["execution_strategy"] if result else "",
                        "final_answer": result["final_answer"] if result else ""
                    })
                }
                break

            elif status == "failed":
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "status": "failed",
                        "error": task["error"]
                    })
                }
                break

            # Send heartbeat to keep connection alive
            heartbeat_counter += 1
            if heartbeat_counter >= heartbeat_interval:
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({"ping": "alive"})
                }
                heartbeat_counter = 0

            # Wait before next poll
            await asyncio.sleep(interval)

    return EventSourceResponse(event_generator())


# -----------------------------------------------------------------------------
# Run with uvicorn
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
