"""
FastAPI Server with Rate Limiting - SOLUTION

This file contains the complete implementation with rate limiting integrated.
"""

import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Query, Response
from pydantic import BaseModel

from database import (
    init_db,
    create_task,
    get_task,
    get_task_result,
    get_user_tasks,
)
from state_store_solution import (
    store_message,
    get_conversation_history,
    get_user_conversations,
    delete_conversation,
    get_conversation_formatted_for_llm,
    # Rate limiting functions
    check_rate_limit,
    increment_rate_limit,
    get_rate_limit_status,
)
from tasks import run_agent_task


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
    title="Production Agent API with Rate Limiting - SOLUTION",
    description="""
    Multi-user agent API with stateless architecture and rate limiting.

    ## Rate Limiting
    - Users are limited to 5 requests per minute
    - Check `X-RateLimit-*` headers in responses
    - Returns 429 Too Many Requests when limit exceeded
    """,
    version="1.0.0",
    lifespan=lifespan,
)


# -----------------------------------------------------------------------------
# User Authentication
# -----------------------------------------------------------------------------

def get_user_id(x_user_id: str = Header(..., description="User identifier")) -> str:
    """Extract user ID from header."""
    if not x_user_id or len(x_user_id) < 1:
        raise HTTPException(status_code=401, detail="X-User-ID header required")
    return x_user_id


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------

class TaskSubmitRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None


class TaskSubmitResponse(BaseModel):
    task_id: str
    user_id: str
    celery_task_id: str
    status: str
    conversation_id: Optional[str] = None
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    user_id: str
    status: str
    progress: Optional[str] = None
    execution_strategy: Optional[str] = None
    error: Optional[str] = None


class TaskResultResponse(BaseModel):
    task_id: str
    query: str
    execution_strategy: Optional[str] = None
    final_answer: Optional[str] = None


class TaskListResponse(BaseModel):
    tasks: list[TaskStatusResponse]
    total: int


class MessageRequest(BaseModel):
    role: str
    content: str


class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str
    metadata: dict


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: list[MessageResponse]


class ConversationListResponse(BaseModel):
    conversations: list[dict]


# -----------------------------------------------------------------------------
# Helper: Add Rate Limit Headers - SOLUTION
# -----------------------------------------------------------------------------

def add_rate_limit_headers(response: Response, user_id: str):
    """Add rate limit headers to the response."""
    status = get_rate_limit_status(user_id)
    response.headers["X-RateLimit-Limit"] = str(status["limit"])
    response.headers["X-RateLimit-Remaining"] = str(status["remaining"])
    response.headers["X-RateLimit-Reset"] = str(status["reset_seconds"])


# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Production Agent API with Rate Limiting (SOLUTION)",
        "features": [
            "Multi-user support",
            "Rate limiting (5 requests/minute)",
            "Conversation history",
            "Stateless workers",
        ]
    }


# -----------------------------------------------------------------------------
# Task Endpoints with Rate Limiting - SOLUTION
# -----------------------------------------------------------------------------

@app.post("/tasks", response_model=TaskSubmitResponse)
def submit_task(
    request: TaskSubmitRequest,
    response: Response,
    x_user_id: str = Header(..., description="User identifier")
):
    """Submit a new task with rate limiting."""
    user_id = get_user_id(x_user_id)

    # SOLUTION: Check rate limit BEFORE creating task
    is_allowed, current_count, max_allowed = check_rate_limit(user_id)

    if not is_allowed:
        status = get_rate_limit_status(user_id)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. You have made {current_count}/{max_allowed} requests. "
                   f"Try again in {status['reset_seconds']} seconds."
        )

    task_id = str(uuid.uuid4())
    conversation_id = request.conversation_id or str(uuid.uuid4())

    store_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=request.query,
        metadata={"task_id": task_id}
    )

    create_task(task_id, user_id, request.query, conversation_id)

    celery_result = run_agent_task.delay(
        task_id=task_id,
        user_id=user_id,
        query=request.query,
        conversation_id=conversation_id
    )

    # SOLUTION: Increment rate limit after successful task creation
    increment_rate_limit(user_id)

    # SOLUTION: Add rate limit headers to response
    add_rate_limit_headers(response, user_id)

    return TaskSubmitResponse(
        task_id=task_id,
        user_id=user_id,
        celery_task_id=celery_result.id,
        status="queued",
        conversation_id=conversation_id,
        message="Task queued. Poll GET /tasks/{task_id} for status."
    )


# -----------------------------------------------------------------------------
# Rate Limit Status Endpoint - SOLUTION
# -----------------------------------------------------------------------------

@app.get("/rate-limit")
def get_rate_limit_endpoint(
    x_user_id: str = Header(..., description="User identifier")
):
    """Get current rate limit status for the user."""
    user_id = get_user_id(x_user_id)
    status = get_rate_limit_status(user_id)
    return status


# -----------------------------------------------------------------------------
# Other Endpoints (unchanged)
# -----------------------------------------------------------------------------

@app.get("/tasks", response_model=TaskListResponse)
def list_user_tasks(
    x_user_id: str = Header(..., description="User identifier"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None)
):
    """List all tasks for the authenticated user."""
    user_id = get_user_id(x_user_id)
    tasks = get_user_tasks(user_id, limit=limit, offset=offset, status_filter=status)

    return TaskListResponse(
        tasks=[
            TaskStatusResponse(
                task_id=t["task_id"],
                user_id=t["user_id"],
                status=t["status"],
                progress=t["progress"],
                execution_strategy=t["execution_strategy"],
                error=t["error"]
            )
            for t in tasks
        ],
        total=len(tasks)
    )


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    x_user_id: str = Header(..., description="User identifier")
):
    """Get the status of a specific task."""
    user_id = get_user_id(x_user_id)
    task = get_task(task_id, user_id=user_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return TaskStatusResponse(
        task_id=task["task_id"],
        user_id=task["user_id"],
        status=task["status"],
        progress=task["progress"],
        execution_strategy=task["execution_strategy"],
        error=task["error"],
    )


@app.get("/tasks/{task_id}/result", response_model=TaskResultResponse)
def get_task_result_endpoint(
    task_id: str,
    x_user_id: str = Header(..., description="User identifier")
):
    """Get the result of a completed task."""
    user_id = get_user_id(x_user_id)
    task = get_task(task_id, user_id=user_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task["status"] == "failed":
        raise HTTPException(status_code=400, detail=f"Task failed: {task['error']}")

    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Task not completed: {task['status']}")

    result = get_task_result(task_id, user_id=user_id)
    if result is None:
        raise HTTPException(status_code=500, detail="Result not found")

    return TaskResultResponse(
        task_id=task_id,
        query=result.get("query"),
        execution_strategy=result.get("execution_strategy"),
        final_answer=result.get("final_answer"),
    )


@app.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    x_user_id: str = Header(..., description="User identifier"),
    limit: int = Query(default=20, ge=1, le=100)
):
    """List all conversations for the authenticated user."""
    user_id = get_user_id(x_user_id)
    conversations = get_user_conversations(user_id, limit=limit)
    return ConversationListResponse(conversations=conversations)


@app.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    x_user_id: str = Header(..., description="User identifier"),
    limit: Optional[int] = Query(default=None)
):
    """Get messages from a specific conversation."""
    user_id = get_user_id(x_user_id)
    messages = get_conversation_history(user_id, conversation_id, limit=limit)

    return ConversationResponse(
        conversation_id=conversation_id,
        messages=[
            MessageResponse(
                role=m["role"],
                content=m["content"],
                timestamp=m["timestamp"],
                metadata=m.get("metadata", {})
            )
            for m in messages
        ]
    )


@app.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
def add_message_to_conversation(
    conversation_id: str,
    request: MessageRequest,
    x_user_id: str = Header(..., description="User identifier")
):
    """Add a message to a conversation."""
    user_id = get_user_id(x_user_id)

    message = store_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role=request.role,
        content=request.content
    )

    return MessageResponse(
        role=message["role"],
        content=message["content"],
        timestamp=message["timestamp"],
        metadata=message.get("metadata", {})
    )


@app.delete("/conversations/{conversation_id}")
def delete_conversation_endpoint(
    conversation_id: str,
    x_user_id: str = Header(..., description="User identifier")
):
    """Delete a conversation and all its messages."""
    user_id = get_user_id(x_user_id)
    deleted = delete_conversation(user_id, conversation_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"status": "deleted", "conversation_id": conversation_id}


@app.get("/conversations/{conversation_id}/llm-format")
def get_conversation_for_llm(
    conversation_id: str,
    x_user_id: str = Header(..., description="User identifier"),
    system_prompt: Optional[str] = Query(default=None)
):
    """Get conversation formatted for LLM consumption."""
    user_id = get_user_id(x_user_id)
    messages = get_conversation_formatted_for_llm(
        user_id,
        conversation_id,
        system_prompt=system_prompt
    )
    return {"messages": messages}


# -----------------------------------------------------------------------------
# Run with uvicorn
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
