"""
FastAPI Server for Worker Node Architecture

=============================================================================
TRY IT YOURSELF: Add a New API Endpoint
=============================================================================

OBJECTIVE:
    Add a new endpoint `POST /tasks/quick` that submits tasks to your
    new `run_simple_search_task` Celery task.

YOUR TASK:
    1. Import your new task from tasks.py
    2. Create a new endpoint POST /tasks/quick
    3. The endpoint should:
       - Generate a task_id
       - Create a task entry in the database
       - Enqueue your new Celery task
       - Return the task_id

HINTS:
    - Look at submit_task() below as a template
    - Use run_simple_search_task.delay(task_id, query) to enqueue
    - The response model can be the same (TaskSubmitResponse)

=============================================================================

Run with:
    1. Start Redis:     redis-server (or docker-compose up redis)
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

# TODO: Import your new task
# from tasks import run_simple_search_task


# -----------------------------------------------------------------------------
# Lifespan
# -----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# -----------------------------------------------------------------------------
# FastAPI App
# -----------------------------------------------------------------------------

app = FastAPI(
    title="Agent Worker Node Architecture API",
    description="""
    API for long-running agent tasks using Celery workers.

    ## Endpoints

    ### Existing
    - POST /tasks - Full task decomposition (slow, thorough)
    - GET /tasks/{id} - Poll status
    - GET /tasks/{id}/result - Get result

    ### Your Task
    - POST /tasks/quick - Simple search (fast, single search) - YOU IMPLEMENT THIS!
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
                {"query": "What are the latest AI developments in 2024?"},
            ]
        }
    }


class TaskSubmitResponse(BaseModel):
    task_id: str
    celery_task_id: str
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
    execution_strategy: str | None = None
    final_answer: str | None = None
    answer: str | None = None
    tool_used: bool | None = None


# -----------------------------------------------------------------------------
# Existing Endpoints
# -----------------------------------------------------------------------------

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Agent Worker Node API is running",
        "endpoints": {
            "full_task": "POST /tasks",
            "quick_task": "POST /tasks/quick (YOUR TASK!)",
            "poll_status": "GET /tasks/{task_id}",
            "get_result": "GET /tasks/{task_id}/result",
        }
    }


@app.post("/tasks", response_model=TaskSubmitResponse)
def submit_task(request: TaskSubmitRequest):
    """
    Submit a full task decomposition task.
    This is the EXISTING endpoint - use it as a template.
    """
    task_id = str(uuid.uuid4())
    create_task(task_id, request.query)
    celery_result = run_agent_task.delay(task_id, request.query)

    return TaskSubmitResponse(
        task_id=task_id,
        celery_task_id=celery_result.id,
        status="queued",
        message="Full task decomposition queued. Poll GET /tasks/{task_id} for status."
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

    # Handle both full task and quick task results
    return TaskResultResponse(
        task_id=task_id,
        query=result.get("query"),
        execution_strategy=result.get("execution_strategy"),
        final_answer=result.get("final_answer"),
        answer=result.get("answer"),
        tool_used=result.get("tool_used"),
    )


# -----------------------------------------------------------------------------
# TODO: Add Your New Endpoint Here
# -----------------------------------------------------------------------------

# @app.post("/tasks/quick", response_model=TaskSubmitResponse)
# def submit_quick_task(request: TaskSubmitRequest):
#     """
#     Submit a quick search task.
#
#     This uses the simple Tavily search agent which is faster than
#     the full task decomposition. Good for simple questions that
#     need a single web search.
#     """
#     # ==========================================================================
#     # YOUR CODE HERE
#     # ==========================================================================
#
#     # Step 1: Generate a unique task_id
#     # task_id = str(uuid.uuid4())
#
#     # Step 2: Create task entry in database
#     # create_task(task_id, request.query)
#
#     # Step 3: Enqueue your Celery task
#     # celery_result = run_simple_search_task.delay(task_id, request.query)
#
#     # Step 4: Return response
#     # return TaskSubmitResponse(
#     #     task_id=task_id,
#     #     celery_task_id=celery_result.id,
#     #     status="queued",
#     #     message="Quick search queued. Poll GET /tasks/{task_id} for status."
#     # )
#
#     # ==========================================================================
#     # END YOUR CODE
#     # ==========================================================================
#     pass


# -----------------------------------------------------------------------------
# Run with uvicorn
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
