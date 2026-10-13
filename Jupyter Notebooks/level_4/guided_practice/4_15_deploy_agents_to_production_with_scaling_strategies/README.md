# Guided Practice: Deploy Agents to Production with Scaling Strategies

This guided practice builds on the worker node architecture from 4_14, adding production-ready features for horizontal scaling:

1. **Multi-User Support** - Tasks are scoped to users
2. **Conversation History** - Stored in Redis (hot storage)
3. **Stateless Architecture** - Workers fetch all context from external stores

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Load Balancer                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI API Servers (Stateless)                      │
│  • Authenticate requests (X-User-ID header)                                  │
│  • Validate and enqueue tasks                                                │
│  • Serve conversation history from Redis                                     │
└─────────────────────────────────────────────────────────────────────────────┘
          │                         │                          │
          ▼                         ▼                          ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────────────┐
│   Redis Queue    │    │  Redis State     │    │    PostgreSQL / SQLite       │
│   (Celery)       │    │  (Conversations) │    │    (Tasks & Results)         │
│   - Task queue   │    │  - User sessions │    │    - Durable storage         │
│   - Result cache │    │  - Chat history  │    │    - Task metadata           │
└──────────────────┘    │  - TTL cleanup   │    │    - User associations       │
                        └──────────────────┘    └──────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Celery Worker 1 │    │  Celery Worker 2 │    │  Celery Worker N │
│  (Stateless)     │    │  (Stateless)     │    │  (Stateless)     │
│  • Fetches state │    │  • Fetches state │    │  • Fetches state │
│  • Runs agent    │    │  • Runs agent    │    │  • Runs agent    │
│  • Saves results │    │  • Saves results │    │  • Saves results │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

## Why Stateless?

From the slides, the key insight is:

> **The Anti-Pattern:** "Sticky sessions" lock users to specific servers, preventing failovers
>
> **The Solution:** Externalize all state. Workers fetch context, act, and save back.

Benefits:
- **Any worker can handle any task** - No affinity required
- **Fault tolerance** - If a worker crashes, the job re-queues to another
- **Easy scaling** - Just add more workers
- **Zero-downtime deployments** - Drain workers gracefully

## State Storage Strategy

Following the slides' tiered storage approach:

| Storage Tier | Technology | Purpose | TTL |
|-------------|------------|---------|-----|
| Hot | Redis | Conversation history, session state | 1 hour |
| Warm | SQLite/Postgres | Task metadata, results | Permanent |
| Cold | S3 (not in this demo) | Large artifacts, logs | Archive |

## Files in This Practice

```
4_15_deploy_agents_to_production_with_scaling_strategies/
├── README.md           # This file
├── main.py             # FastAPI with user auth and conversation endpoints
├── tasks.py            # Stateless Celery tasks
├── database.py         # SQLite with user_id support
├── state_store.py      # Redis conversation history manager
├── agent.py            # Task decomposition agent (from 4_14)
├── client.py           # Demo client showing multi-user usage
├── docker-compose.yml  # Full stack with Redis
├── Dockerfile          # Container definition
└── requirements.txt    # Python dependencies
```

## Quick Start

### Option 1: Run with Docker Compose (Recommended)

```bash
# Set your API keys
export OPENAI_API_KEY=your-key
export TAVILY_API_KEY=your-key

# Start the full stack
docker-compose up --build

# In another terminal, test with the client
python client.py
```

### Option 2: Run Locally

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery worker
celery -A tasks worker --loglevel=info

# Terminal 3: Start API server
uvicorn main:app --reload --port 8000

# Terminal 4: Test with client
python client.py
```

## Sample Queries

Once the API is running, try these sample queries using `curl`:

### Submit a Task (Parallel Execution)

This query will trigger parallel execution (multiple independent sub-queries):

```bash
# Submit a research task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user-alice-123" \
  -d '{
    "query": "Compare the AI strategies of Google, Microsoft, and OpenAI in 2024"
  }'

# Response:
# {
#   "task_id": "abc123...",
#   "user_id": "user-alice-123",
#   "celery_task_id": "...",
#   "status": "queued",
#   "conversation_id": "conv-xyz...",
#   "message": "Task queued. Poll GET /tasks/{task_id} for status."
# }
```

### Submit a Task (Sequential Execution)

This query requires multi-hop reasoning (sequential sub-queries):

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user-alice-123" \
  -d '{
    "query": "What AI products were launched by the company that acquired DeepMind?"
  }'
```

### Continue a Conversation

Use `conversation_id` to maintain context across queries:

```bash
# First query
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user-bob-456" \
  -d '{
    "query": "Tell me about Tesla recent announcements",
    "conversation_id": "conv-tesla-research"
  }'

# Follow-up query (uses conversation context)
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user-bob-456" \
  -d '{
    "query": "What about their energy storage business?",
    "conversation_id": "conv-tesla-research"
  }'
```

### Poll Task Status

```bash
curl -X GET http://localhost:8000/tasks/{task_id} \
  -H "X-User-ID: user-alice-123"

# Response:
# {
#   "task_id": "abc123...",
#   "user_id": "user-alice-123",
#   "status": "running",
#   "progress": "executing_3_parallel_searches",
#   "execution_strategy": "parallel",
#   "error": null
# }
```

### Get Task Result

```bash
curl -X GET http://localhost:8000/tasks/{task_id}/result \
  -H "X-User-ID: user-alice-123"

# Response:
# {
#   "task_id": "abc123...",
#   "query": "Compare the AI strategies...",
#   "execution_strategy": "parallel",
#   "final_answer": "Google's AI strategy in 2024 focuses on..."
# }
```

### List All Your Tasks

```bash
curl -X GET "http://localhost:8000/tasks?limit=10&status=completed" \
  -H "X-User-ID: user-alice-123"
```

### View Conversation History

```bash
# List all conversations
curl -X GET http://localhost:8000/conversations \
  -H "X-User-ID: user-bob-456"

# Get messages from a specific conversation
curl -X GET http://localhost:8000/conversations/conv-tesla-research \
  -H "X-User-ID: user-bob-456"

# Get conversation formatted for LLM (with system prompt)
curl -X GET "http://localhost:8000/conversations/conv-tesla-research/llm-format?system_prompt=You%20are%20a%20helpful%20assistant" \
  -H "X-User-ID: user-bob-456"
```

### Add a Message to Conversation (Without Running a Task)

```bash
curl -X POST http://localhost:8000/conversations/conv-tesla-research/messages \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user-bob-456" \
  -d '{
    "role": "user",
    "content": "I am particularly interested in their Megapack product."
  }'
```

### Delete a Conversation

```bash
curl -X DELETE http://localhost:8000/conversations/conv-tesla-research \
  -H "X-User-ID: user-bob-456"
```

### Verify User Isolation

```bash
# This should return 404 - users cannot access each other's tasks
curl -X GET http://localhost:8000/tasks/{alice_task_id} \
  -H "X-User-ID: user-bob-456"

# Response: {"detail": "Task abc123... not found or not owned by user"}
```

## API Endpoints

### Authentication
All endpoints require an `X-User-ID` header to identify the user.

### Task Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tasks` | Submit a new task |
| GET | `/tasks` | List all tasks for the user |
| GET | `/tasks/{task_id}` | Get task status |
| GET | `/tasks/{task_id}/result` | Get completed task result |

### Conversation History

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/conversations` | List user's conversations |
| GET | `/conversations/{conv_id}` | Get conversation messages |
| POST | `/conversations/{conv_id}/messages` | Add message to conversation |
| DELETE | `/conversations/{conv_id}` | Delete conversation |

## Key Concepts Demonstrated

### 1. User Scoping

Every task is associated with a `user_id`:

```python
# Tasks are scoped to users
create_task(task_id, user_id, query)
get_user_tasks(user_id)  # Only returns tasks for this user
```

### 2. Conversation History in Redis

Messages are stored with automatic TTL:

```python
# Store message (auto-expires after 1 hour)
store_message(user_id, conversation_id, role="user", content="...")

# Retrieve history (from any API server or worker)
messages = get_conversation_history(user_id, conversation_id)
```

### 3. Stateless Worker Design

Workers have no local state - everything is fetched:

```python
@celery_app.task
def run_agent_task(task_id: str, user_id: str, query: str):
    # Fetch conversation history from Redis (not local memory)
    history = get_conversation_history(user_id, conversation_id)

    # Run agent with external context
    result = run_task_decomposition(query, history=history)

    # Save results back to external stores
    save_task_result(task_id, result)
    store_message(user_id, conversation_id, "assistant", result["answer"])
```

### 4. TTL-Based Cleanup

Conversation history auto-expires (configurable):

```python
# In state_store.py
CONVERSATION_TTL = 3600  # 1 hour

# Redis automatically cleans up expired data
# No manual cleanup required!
```

## Testing Multi-User Behavior

The `client.py` demonstrates:

1. **User A** submits a task and builds conversation history
2. **User B** submits a different task (isolated from User A)
3. Both users can poll their own tasks independently
4. Conversation history is user-scoped

```bash
python client.py
```

## Scaling in Production

### Horizontal Scaling

```bash
# Scale workers
docker-compose up --scale worker=5

# Scale API servers (behind load balancer)
docker-compose up --scale api=3
```

### Redis Cluster (for high availability)

For production, use Redis Cluster or Redis Sentinel:

```yaml
# docker-compose.prod.yml
services:
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    deploy:
      replicas: 3
```

### Database Connection Pooling

For PostgreSQL in production, add PgBouncer:

```yaml
services:
  pgbouncer:
    image: edoburu/pgbouncer
    environment:
      DATABASE_URL: postgres://user:pass@postgres:5432/db
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 1000
```
