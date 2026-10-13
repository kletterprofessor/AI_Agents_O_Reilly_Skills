"""
FastAPI Server with Multi-User Support and Stateless Design

This API server demonstrates production-ready patterns:
- User authentication via X-User-ID header (simplified for demo)
- Task scoping per user
- Conversation history management via Redis
- Stateless design - any API instance can handle any request

Key differences from 4_14:
- All endpoints require user authentication
- Tasks are scoped to users
- Conversation history endpoints for managing chat state
- Stateless workers fetch all context from external stores

Run with:
    1. Start Redis:     redis-server (or docker-compose up redis)
    2. Start Worker:    celery -A tasks worker --loglevel=info
    3. Start API:       uvicorn main:app --reload
"""

import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Query
from pydantic import BaseModel

from database import (
    init_db,
    create_task,
    get_task,
    get_task_result,
    get_user_tasks,
)
from state_store import (
    store_message,
    get_conversation_history,
    get_user_conversations,
    delete_conversation,
    get_conversation_formatted_for_llm,
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
    title="Production Agent API with Scaling Support",
    description="""
    Multi-user agent API with stateless architecture for horizontal scaling.

    ## Authentication
    All endpoints require an `X-User-ID` header.

    ## Key Features
    - User-scoped tasks
    - Conversation history in Redis
    - Stateless workers (any worker handles any task)
    - Automatic TTL cleanup for conversations
    """,
    version="1.0.0",
    lifespan=lifespan,
)


# -----------------------------------------------------------------------------
# User Authentication (Simplified for Demo)
# -----------------------------------------------------------------------------

def get_user_id(x_user_id: str = Header(..., description="User identifier")) -> str:
    """
    Extract user ID from header.

    In production, this would validate a JWT token or session.
    For this demo, we accept any non-empty user ID.
    """
    if not x_user_id or len(x_user_id) < 1:
        raise HTTPException(status_code=401, detail="X-User-ID header required")
    return x_user_id


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------

class TaskSubmitRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "What are the latest AI developments in 2024?",
                    "conversation_id": "conv-123"
                },
            ]
        }
    }


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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"role": "user", "content": "What is machine learning?"}
            ]
        }
    }


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
# Health Check
# -----------------------------------------------------------------------------

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Production Agent API is running",
        "features": [
            "Multi-user support (X-User-ID header)",
            "Task scoping per user",
            "Conversation history (Redis)",
            "Stateless workers",
        ]
    }


# -----------------------------------------------------------------------------
# Task Endpoints
# -----------------------------------------------------------------------------

@app.post("/tasks", response_model=TaskSubmitResponse)
def submit_task(
    request: TaskSubmitRequest,
    x_user_id: str = Header(..., description="User identifier")
):
    """
    Submit a new task for processing.

    The task will be queued for a Celery worker. If a conversation_id is
    provided, the task will include conversation history as context.
    """
    user_id = get_user_id(x_user_id)
    task_id = str(uuid.uuid4())

    # Create or use provided conversation ID
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Store user message in conversation history
    store_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=request.query,
        metadata={"task_id": task_id}
    )

    # Create task in database
    create_task(task_id, user_id, request.query, conversation_id)

    # Enqueue Celery task (stateless - worker will fetch all context)
    celery_result = run_agent_task.delay(
        task_id=task_id,
        user_id=user_id,
        query=request.query,
        conversation_id=conversation_id
    )

    return TaskSubmitResponse(
        task_id=task_id,
        user_id=user_id,
        celery_task_id=celery_result.id,
        status="queued",
        conversation_id=conversation_id,
        message="Task queued. Poll GET /tasks/{task_id} for status."
    )


@app.get("/tasks", response_model=TaskListResponse)
def list_user_tasks(
    x_user_id: str = Header(..., description="User identifier"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, description="Filter by status")
):
    """
    List all tasks for the authenticated user.
    """
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
    """
    Get the status of a specific task.

    Only returns tasks owned by the authenticated user.
    """
    user_id = get_user_id(x_user_id)
    task = get_task(task_id, user_id=user_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found or not owned by user"
        )

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
    """
    Get the result of a completed task.

    Only returns results for tasks owned by the authenticated user.
    """
    user_id = get_user_id(x_user_id)
    task = get_task(task_id, user_id=user_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found or not owned by user"
        )

    if task["status"] == "failed":
        raise HTTPException(status_code=400, detail=f"Task failed: {task['error']}")

    if task["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not yet completed. Current status: {task['status']}"
        )

    result = get_task_result(task_id, user_id=user_id)
    if result is None:
        raise HTTPException(status_code=500, detail="Result not found")

    return TaskResultResponse(
        task_id=task_id,
        query=result.get("query"),
        execution_strategy=result.get("execution_strategy"),
        final_answer=result.get("final_answer"),
    )


# -----------------------------------------------------------------------------
# Conversation History Endpoints
# -----------------------------------------------------------------------------

@app.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    x_user_id: str = Header(..., description="User identifier"),
    limit: int = Query(default=20, ge=1, le=100)
):
    """
    List all conversations for the authenticated user.

    Returns conversation metadata including last activity and message count.
    """
    user_id = get_user_id(x_user_id)
    conversations = get_user_conversations(user_id, limit=limit)

    return ConversationListResponse(conversations=conversations)


@app.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    x_user_id: str = Header(..., description="User identifier"),
    limit: Optional[int] = Query(default=None, description="Limit messages (most recent)")
):
    """
    Get messages from a specific conversation.
    """
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
    """
    Add a message to a conversation.

    Use this to add context or continue a conversation without submitting a task.
    """
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
    """
    Delete a conversation and all its messages.
    """
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
    """
    Get conversation formatted for LLM consumption.

    Returns messages in the format expected by chat models:
    [{"role": "system|user|assistant", "content": "..."}]
    """
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
