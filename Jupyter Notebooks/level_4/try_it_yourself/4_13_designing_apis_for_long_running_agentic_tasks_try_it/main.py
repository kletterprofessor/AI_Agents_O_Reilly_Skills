"""
FastAPI Server for Long-Running Agentic Tasks

=============================================================================
TRY IT YOURSELF: Add SSE (Server-Sent Events) Streaming
=============================================================================

OBJECTIVE:
    Implement real-time streaming as an alternative to polling.
    Instead of clients repeatedly asking "are you done yet?", the server
    PUSHES updates to the client as they happen.

BACKGROUND:
    Server-Sent Events (SSE) is a standard for servers to push data to clients
    over HTTP. Unlike WebSockets, SSE is:
    - Unidirectional (server -> client only)
    - Built on regular HTTP (works through proxies/firewalls)
    - Auto-reconnects on connection loss
    - Perfect for progress updates!

YOUR TASK:
    1. Add an SSE streaming endpoint: GET /tasks/{task_id}/stream
    2. The endpoint should:
       - Accept a task_id
       - Return a StreamingResponse with SSE events
       - Push progress updates as the agent executes
       - Send a final "complete" or "error" event when done

SSE EVENT FORMAT:
    Each event is plain text with this format:

        event: <event_type>
        data: <json_payload>

        (blank line separates events)

    Example events your endpoint should send:

        event: status
        data: {"status": "running", "progress": "analyzing_query"}

        event: status
        data: {"status": "running", "progress": "executing_search_step_1_of_2"}

        event: complete
        data: {"status": "completed", "execution_strategy": "sequential", "final_answer": "..."}

HINTS:
    1. Use `from sse_starlette.sse import EventSourceResponse`
    2. Create an async generator that yields SSE events
    3. Poll the database in a loop until task completes
    4. Use `asyncio.sleep()` between polls (don't hammer the DB!)
    5. Handle the case where task_id doesn't exist

STRETCH GOALS:
    - Add a "heartbeat" event every few seconds to keep connection alive
    - Handle client disconnection gracefully
    - Add a query parameter for poll interval: /tasks/{id}/stream?interval=0.5

=============================================================================

Run with: uvicorn main:app --reload
Test at: http://localhost:8000/docs
"""

import uuid
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# TODO: Uncomment this import after installing sse-starlette
# from sse_starlette.sse import EventSourceResponse

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

    ## Patterns Supported

    ### 1. Polling Pattern (Implemented)
    - POST /tasks - Submit task
    - GET /tasks/{task_id} - Poll status
    - GET /tasks/{task_id}/result - Get result

    ### 2. SSE Streaming Pattern (YOUR TASK!)
    - GET /tasks/{task_id}/stream - Real-time progress via Server-Sent Events
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
# Existing Polling Endpoints (Already Implemented)
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
            "stream_status": "GET /tasks/{task_id}/stream (YOUR TASK!)",
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
# TODO: Implement SSE Streaming Endpoint
# -----------------------------------------------------------------------------

@app.get("/tasks/{task_id}/stream")
async def stream_task_status(task_id: str):
    """
    Stream task status updates via Server-Sent Events (SSE).

    TODO: Implement this endpoint!

    Requirements:
    1. Check if task exists, return 404 if not
    2. Create an async generator that:
       - Polls the database for task status
       - Yields SSE events for each status change
       - Sends "complete" event with result when done
       - Sends "error" event if task fails
    3. Return an EventSourceResponse with the generator

    Example implementation structure:

        async def event_generator():
            last_progress = None
            while True:
                task = get_task(task_id)

                # Check for status changes and yield events
                # ...

                if task["status"] == "completed":
                    result = get_task_result(task_id)
                    yield {
                        "event": "complete",
                        "data": json.dumps({...})
                    }
                    break

                await asyncio.sleep(0.5)

        return EventSourceResponse(event_generator())
    """
    # ==========================================================================
    # YOUR CODE HERE
    # ==========================================================================

    # Step 1: Check if task exists
    # task = get_task(task_id)
    # if task is None:
    #     raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Step 2: Create async generator for SSE events
    # async def event_generator():
    #     ...

    # Step 3: Return EventSourceResponse
    # return EventSourceResponse(event_generator())

    # ==========================================================================
    # END YOUR CODE
    # ==========================================================================

    # Placeholder - remove this when you implement the endpoint
    raise HTTPException(
        status_code=501,
        detail="SSE streaming not implemented yet. This is your task!"
    )


# -----------------------------------------------------------------------------
# Run with uvicorn
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
