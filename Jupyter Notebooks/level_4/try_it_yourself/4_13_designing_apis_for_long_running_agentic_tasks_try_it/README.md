# Try It Yourself: SSE Streaming for Long-Running Agent Tasks

## Overview

In the guided practice, you built an API for long-running agent tasks using the **polling pattern**. Now you'll implement **Server-Sent Events (SSE) streaming** - a more efficient way to deliver real-time updates to clients.

### Polling vs Streaming

| Aspect | Polling | SSE Streaming |
|--------|---------|---------------|
| Direction | Client pulls | Server pushes |
| Efficiency | Repeated requests | Single connection |
| Latency | Depends on poll interval | Instant updates |
| Complexity | Simple | Slightly more complex |
| Best for | Simple clients, broad compatibility | Real-time UIs, better UX |

## Setup

### 1. Install Dependencies

```bash
cd level_4/try_it_yourself/4_13_designing_apis_for_long_running_agentic_tasks_try_it
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file with your API keys:

```
OPENAI_API_KEY=your-openai-key
TAVILY_API_KEY=your-tavily-key
```

### 3. Start the Server

```bash
uvicorn main:app --reload
```

The server runs at http://localhost:8000. Visit http://localhost:8000/docs for the interactive API documentation.

## Your Task

Implement SSE streaming in two files:

### Part 1: Server-Side (`main.py`)

Implement the `stream_task_status()` function at line ~180.

**Requirements:**
1. Check if task exists (return 404 if not)
2. Create an async generator that yields SSE events
3. Poll the database and yield events when status changes
4. Send "complete" event with result when task finishes
5. Send "error" event if task fails
6. Return an `EventSourceResponse`

**SSE Event Format:**
```
event: status
data: {"status": "running", "progress": "analyzing_query"}

event: complete
data: {"status": "completed", "final_answer": "..."}

event: error
data: {"status": "failed", "error": "Something went wrong"}
```

### Part 2: Client-Side (`client.py`)

Implement the `run_with_streaming()` function at line ~250.

**Provided for you:** The `parse_sse_events()` function handles SSE parsing - you just use it!

**Requirements:**
1. Submit task using existing `submit_task()` function
2. Connect to `/tasks/{task_id}/stream` with `stream=True`
3. Use `parse_sse_events(response)` to iterate through events
4. Handle "status", "complete", and "error" events
5. Display progress updates in real-time

## Testing Your Implementation

### Test the Server

```bash
# Terminal 1: Start server
uvicorn main:app --reload

# Terminal 2: Test with curl
curl -N http://localhost:8000/tasks/{task_id}/stream
```

### Test the Client

```bash
# Streaming mode (your implementation)
python client.py "What AI products were launched by the company that acquired DeepMind in 2024?" --stream

# Polling mode (already works)
python client.py "Summarize Tesla's Q4 2024 earnings" --interval 2
```

### Expected Output (Streaming Mode)

```
======================================================================
LONG-RUNNING AGENT TASK CLIENT (STREAMING MODE)
======================================================================

Query: What AI products were launched by...
----------------------------------------------------------------------

[1] Submitting task...
    Task ID: abc123-def456-...

[2] Connecting to SSE stream...
    Connected! Receiving events...

    [  0.5s] [status] running | analyzing_query
    [  2.1s] [status] [sequential] running | executing_search_step_1_of_2
    [  5.3s] [status] [sequential] running | executing_search_step_2_of_2
    [  8.7s] [status] [sequential] running | synthesizing_results
    [ 10.2s] [complete] Task finished!

    Task completed in 10.2s

======================================================================
RESULT (received via SSE stream)
======================================================================

Execution Strategy: sequential

Final Answer:
Google, which acquired DeepMind in 2014, launched several AI products in 2024...

======================================================================
```

## Hints

### Server-Side Hints

```python
from sse_starlette.sse import EventSourceResponse

async def event_generator():
    while True:
        task = get_task(task_id)

        # Yield SSE event as a dict
        yield {
            "event": "status",
            "data": json.dumps({"status": task["status"], ...})
        }

        if task["status"] == "completed":
            yield {"event": "complete", "data": json.dumps({...})}
            break

        await asyncio.sleep(0.5)

return EventSourceResponse(event_generator())
```

### Client-Side Hints

```python
# parse_sse_events() is already provided in client.py!

response = requests.get(url, stream=True)

for event in parse_sse_events(response):
    event_type = event["event"]
    data = json.loads(event["data"])

    if event_type == "status":
        print(f"Progress: {data['progress']}")
    elif event_type == "complete":
        print("Done!")
        result = data  # Contains final_answer, execution_strategy
        break
    elif event_type == "error":
        print(f"Failed: {data['error']}")
        break
```

## Stretch Goals

1. **Heartbeat Events**: Add periodic "heartbeat" events to keep the connection alive
2. **Configurable Interval**: Add a query parameter `/stream?interval=0.5`
3. **Reconnection Support**: Handle client reconnection (track last event ID)
4. **Graceful Shutdown**: Clean up on client disconnect

## Solution

When you're ready to check your work, look at:
- `main_solution.py` - Complete server implementation
- `client_solution.py` - Complete client implementation

To test the solution:

```bash
# Start server with solution
uvicorn main_solution:app --reload

# Run client solution
python client_solution.py "Your query here" --stream
```

## Files in This Directory

```
4_13_designing_apis_for_long_running_agentic_tasks_try_it/
├── README.md              # This file
├── requirements.txt       # Dependencies
├── database.py           # SQLite operations (unchanged from guided practice)
├── agent.py              # Task decomposition agent (unchanged)
├── main.py               # Server with TODO for SSE endpoint
├── client.py             # Client with TODO + parse_sse_events() provided
├── main_solution.py      # Complete server solution
└── client_solution.py    # Complete client solution
```

## Key Concepts

### Server-Sent Events (SSE)

SSE is a web standard that allows servers to push data to clients over HTTP:

- **Unidirectional**: Server to client only
- **Text-based**: Events are plain text with specific format
- **Auto-reconnect**: Browsers automatically reconnect on disconnect
- **HTTP-based**: Works through firewalls and proxies

### Why SSE for Long-Running Tasks?

1. **Efficiency**: One connection instead of repeated polls
2. **Real-time**: Updates arrive instantly
3. **Simple**: Easier than WebSockets for one-way data
4. **Standard**: Supported by all modern browsers

### When to Use Each Pattern

- **Polling**: Simple clients, broad compatibility, stateless servers
- **SSE**: Real-time UIs, progress updates, dashboards
- **WebSockets**: Bidirectional communication, chat, gaming
