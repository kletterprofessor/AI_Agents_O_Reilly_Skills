# Guided Practice: Worker Node Architecture for Agents

## Overview

This guided practice demonstrates the **worker node architecture** pattern for deploying long-running agents. Instead of running agent tasks in the same process as the web server (using `BackgroundTasks`), we use:

- **Redis** as a message queue
- **Celery** workers as separate processes that execute agent tasks

## Architecture

```
                                     +------------------+
                                     |  Celery Worker   |
                                     |  (runs agents)   |
                                     +--------+---------+
                                              |
Client --> FastAPI --> Redis Queue --> Worker Pool --> SQLite
              |                                           |
              +-------- Poll /tasks/{id} <---------------+
```

## Why Worker Node Architecture?

| Aspect | BackgroundTasks (4_13) | Celery Workers (4_14) |
|--------|------------------------|------------------------|
| Process | Same as FastAPI | Separate processes |
| Queue | In-memory (lost on restart) | Redis (persistent) |
| Retries | Manual | Automatic |
| Scaling | Limited by server | Add more workers |
| Failures | Task lost if server crashes | Task retried by another worker |
| Monitoring | None built-in | Flower, Redis CLI |

## Prerequisites

1. **Redis** must be installed and running:
   ```bash
   # macOS
   brew install redis
   brew services start redis

   # Ubuntu
   sudo apt install redis-server
   sudo systemctl start redis

   # Docker
   docker run -d -p 6379:6379 redis
   ```

2. **API Keys** in `.env` file:
   ```
   OPENAI_API_KEY=your-openai-key
   TAVILY_API_KEY=your-tavily-key
   ```

## Setup

```bash
cd level_4/guided_practice/4_14_deploying_agents_in_worker_node_architectures
pip install -r requirements.txt
```

## Running the System

You need **three terminals**:

### Terminal 1: Redis (if not running as service)
```bash
redis-server
```

### Terminal 2: Celery Worker
```bash
celery -A tasks worker --loglevel=info
```

You should see:
```
[config]
.> app:         agent_tasks:0x...
.> transport:   redis://localhost:6379/0
.> results:     redis://localhost:6379/1
.> concurrency: 2 (prefork)

[queues]
.> celery           exchange=celery(direct) key=celery

[tasks]
  . tasks.health_check
  . tasks.run_agent_task

[... worker ready]
```

### Terminal 3: FastAPI Server
```bash
uvicorn main:app --reload
```

## Testing

### Check Workers are Running
```bash
python client.py --check-workers
```

### Run a Query
```bash
python client.py "What AI products were launched by the company that acquired DeepMind in 2024?"
```

### Expected Output
```
======================================================================
WORKER NODE ARCHITECTURE CLIENT
======================================================================

Query: What AI products were launched by...
Poll interval: 1.0s | Timeout: 300.0s
----------------------------------------------------------------------

[0] Checking worker availability...
Checking worker availability...
  Workers are available: Worker is responsive

[1] Submitting task to queue...
    Task ID: abc123-...
    Celery Task ID: def456-...
    Status: queued

[2] Polling for status (task processing on worker)...
    [  0.5s] Status: running | Progress: analyzing_query
    [  2.1s] Status: running [sequential] | Progress: executing_search_step_1_of_2
    [  5.3s] Status: running [sequential] | Progress: executing_search_step_2_of_2
    [  8.7s] Status: running [sequential] | Progress: synthesizing_results

    Task completed in 12.3s

[3] Retrieving result from worker...

======================================================================
RESULT
======================================================================

Execution Strategy: sequential

Final Answer:
Google launched several AI products in 2024...
```

## Files

```
4_14_deploying_agents_in_worker_node_architectures/
├── README.md           # This file
├── requirements.txt    # Dependencies (includes celery, redis)
├── Dockerfile          # Container image for API and worker
├── docker-compose.yml  # Orchestrates Redis, API, and worker
├── agent.py           # Task decomposition agent (unchanged from 4_13)
├── database.py        # SQLite for task status/results
├── tasks.py           # Celery task definitions (NEW)
├── main.py            # FastAPI server (enqueues to Celery)
└── client.py          # Polling client (checks worker health)
```

## Running with Docker (Recommended)

Docker Compose manages all three services (Redis, API, Worker) in one command.

### 1. Set Environment Variables

Create a `.env` file:
```bash
OPENAI_API_KEY=your-openai-key
TAVILY_API_KEY=your-tavily-key
```

### 2. Start All Services

```bash
docker-compose up --build
```

This starts:
- **redis**: Message queue on port 6379
- **api**: FastAPI server on port 8000
- **worker**: Celery worker processing tasks

### 3. Test

```bash
# In another terminal
python client.py "What AI products did Google launch in 2024?"

# Or use curl
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"query": "What AI products did Google launch in 2024?"}'
```

### 4. View Logs

```bash
# All services
docker-compose logs -f

# Just the worker
docker-compose logs -f worker
```

### 5. Stop Services

```bash
docker-compose down

# Remove volumes too (clears data)
docker-compose down -v
```

### Scaling Workers

Add more workers to handle more concurrent tasks:

```bash
docker-compose up --scale worker=3
```

## Key Code Differences from 4_13

### 4_13 (BackgroundTasks)
```python
@app.post("/tasks")
def submit_task(request: TaskSubmitRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    create_task(task_id, request.query)
    # Runs in same process
    background_tasks.add_task(run_agent_task, task_id, request.query)
    return {"task_id": task_id}
```

### 4_14 (Celery Workers)
```python
@app.post("/tasks")
def submit_task(request: TaskSubmitRequest):
    task_id = str(uuid.uuid4())
    create_task(task_id, request.query)
    # Queued to Redis, executed by separate worker process
    celery_result = run_agent_task.delay(task_id, request.query)
    return {"task_id": task_id, "celery_task_id": celery_result.id}
```

## Monitoring Workers

### Using Redis CLI
```bash
redis-cli

# Check queue length
LLEN celery

# Monitor all commands
MONITOR
```

### Using Flower (optional)
```bash
pip install flower
celery -A tasks flower
# Open http://localhost:5555
```

## Troubleshooting

### "Worker not available" error
- Make sure Redis is running: `redis-cli ping` should return `PONG`
- Make sure Celery worker is running in a separate terminal
- Check worker logs for errors

### Task stuck in "pending"
- Worker may not be running
- Check worker terminal for errors
- Verify Redis connection: `redis-cli ping`

### Task fails immediately
- Check worker terminal for Python errors
- Verify API keys are set in `.env`
- Check agent.py imports work: `python -c "from agent import run_task_decomposition"`
