# Try It Yourself: Add a New Agent Task to Worker Architecture

## Overview

In the guided practice, you built a worker node architecture with:
- FastAPI server that accepts requests
- Redis queue for job distribution
- Celery workers that run the task decomposition agent

Now you'll extend this system by adding a **second agent** - a simpler, faster search agent.

## Your Task

Add a new "quick search" capability to the system:

| Endpoint | Agent | Speed | Use Case |
|----------|-------|-------|----------|
| `POST /tasks` | Task Decomposition | Slow (10-30s) | Complex multi-step research |
| `POST /tasks/quick` | Simple Search | Fast (3-5s) | Quick single-search answers |

## What You'll Implement

### Part 1: Celery Task (`tasks.py`)

Add a new task called `run_simple_search_task` that:
1. Accepts `task_id` and `query` parameters
2. Calls `run_simple_search()` from `simple_agent.py`
3. Updates progress via callback
4. Saves result to database

### Part 2: FastAPI Endpoint (`main.py`)

Add a new endpoint `POST /tasks/quick` that:
1. Generates a unique task_id
2. Creates a task entry in the database
3. Enqueues your new Celery task
4. Returns the task_id immediately

## What's Provided

| File | Description |
|------|-------------|
| `simple_agent.py` | The Tavily search agent (provided, don't modify) |
| `agent.py` | Full task decomposition agent (unchanged) |
| `database.py` | SQLite operations (unchanged) |
| `client.py` | Polling client (unchanged) |
| `tasks.py` | Celery tasks with TODO for your new task |
| `main.py` | FastAPI server with TODO for your new endpoint |

## Setup

### 1. Install Dependencies

```bash
cd level_4/try_it_yourself/4_14_deploying_agents_in_worker_node_architectures_try_it
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file:
```
OPENAI_API_KEY=your-openai-key
TAVILY_API_KEY=your-tavily-key
```

### 3. Start Services

**Terminal 1: Redis**
```bash
redis-server
```

**Terminal 2: Celery Worker**
```bash
celery -A tasks worker --loglevel=info
```

**Terminal 3: FastAPI**
```bash
uvicorn main:app --reload
```

## Implementation Guide

### Step 1: Add the Celery Task

In `tasks.py`:

1. Uncomment the import:
```python
from simple_agent import run_simple_search
```

2. Implement `run_simple_search_task`:
```python
@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_simple_search_task(self, task_id: str, query: str):
    def on_progress(status: str, progress: str | None):
        update_task_status(task_id, status, progress)

    try:
        result = run_simple_search(query, on_progress=on_progress)

        save_task_result(task_id, {
            "query": result["query"],
            "answer": result["answer"],
            "tool_used": result["tool_used"],
        })

        return {"task_id": task_id, "status": "completed"}

    except Exception as e:
        save_task_error(task_id, str(e))
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {"task_id": task_id, "status": "failed", "error": str(e)}
```

### Step 2: Add the FastAPI Endpoint

In `main.py`:

1. Uncomment the import:
```python
from tasks import run_simple_search_task
```

2. Implement `submit_quick_task`:
```python
@app.post("/tasks/quick", response_model=TaskSubmitResponse)
def submit_quick_task(request: TaskSubmitRequest):
    task_id = str(uuid.uuid4())
    create_task(task_id, request.query)
    celery_result = run_simple_search_task.delay(task_id, request.query)

    return TaskSubmitResponse(
        task_id=task_id,
        celery_task_id=celery_result.id,
        status="queued",
        message="Quick search queued. Poll GET /tasks/{task_id} for status."
    )
```

## Testing Your Implementation

### Restart the Worker

After modifying `tasks.py`, restart the Celery worker:
```bash
# Ctrl+C to stop, then:
celery -A tasks worker --loglevel=info
```

### Test via API Docs

1. Go to http://localhost:8000/docs
2. Try `POST /tasks/quick` with a query
3. Poll `GET /tasks/{task_id}` until completed
4. Get result with `GET /tasks/{task_id}/result`

### Test via Client

```bash
# Use curl to test quick endpoint
curl -X POST http://localhost:8000/tasks/quick \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of France?"}'

# Then poll for status
curl http://localhost:8000/tasks/{task_id}

# Get result
curl http://localhost:8000/tasks/{task_id}/result
```

### Compare Speed

```bash
# Quick search (should be ~3-5 seconds)
time curl -X POST http://localhost:8000/tasks/quick \
  -H "Content-Type: application/json" \
  -d '{"query": "Latest news about OpenAI"}'

# Full task decomposition (should be ~10-30 seconds)
time curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"query": "Latest news about OpenAI"}'
```

## Solution

When you're ready to check your work:

```bash
# Start worker with solution
celery -A tasks_solution worker --loglevel=info

# Start API with solution
uvicorn main_solution:app --reload
```

Solution files:
- `tasks_solution.py` - Complete Celery tasks
- `main_solution.py` - Complete FastAPI server

## Files

```
4_14_deploying_agents_in_worker_node_architectures_try_it/
├── README.md              # This file
├── requirements.txt       # Dependencies
├── Dockerfile            # Docker image
├── docker-compose.yml    # Docker orchestration
├── simple_agent.py       # Tavily search agent (PROVIDED)
├── agent.py              # Task decomposition agent (unchanged)
├── database.py           # SQLite operations (unchanged)
├── client.py             # Polling client (unchanged)
├── tasks.py              # Celery tasks (YOUR TODO)
├── main.py               # FastAPI server (YOUR TODO)
├── tasks_solution.py     # Complete Celery solution
└── main_solution.py      # Complete FastAPI solution
```

## Key Concepts Reinforced

1. **Adding Celery Tasks**: How to define new tasks with decorators
2. **Task Parameters**: Passing data to worker processes
3. **Progress Callbacks**: Reporting status during execution
4. **API Routing**: Multiple endpoints to different task types
5. **Code Reuse**: Using existing database and polling infrastructure
