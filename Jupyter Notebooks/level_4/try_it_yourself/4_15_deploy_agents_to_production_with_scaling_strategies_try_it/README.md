# Try It Yourself: Implement Rate Limiting

In this exercise, you'll implement **per-user rate limiting** for the agent API to prevent abuse and control costs.

## Background

From the slides on "Cost Control and Multi-Tenant Fairness":

> **The Risk:** LLM costs scale linearly; one runaway loop can drain budgets instantly.
>
> **Throttling:** Return 429 Too Many Requests rather than over-scaling.

Rate limiting is essential for production agent systems because:
- LLM API calls are expensive
- One user shouldn't monopolize resources
- Prevents accidental infinite loops from draining budgets

## Your Task

Implement rate limiting that:
1. Limits each user to **5 requests per minute**
2. Returns **429 Too Many Requests** when limit exceeded
3. Adds **rate limit headers** to responses

## Files to Modify

| File | What to do |
|------|------------|
| `state_store.py` | Implement 3 rate limiting functions |
| `main.py` | Add rate limit checks to task submission |

## Quick Start

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery worker
celery -A tasks worker --loglevel=info

# Terminal 3: Start API
uvicorn main:app --reload

# Terminal 4: Test your implementation
python state_store.py  # Run built-in tests
```

## Step 1: Implement Rate Limiting Functions (state_store.py)

Open `state_store.py` and implement these three functions. Each function has detailed hints in the docstring.

### 1.1 `check_rate_limit(user_id)`

**Purpose:** Check if a user has exceeded their rate limit

**What it should do:**
- Look up the current request count for this user in Redis
- Compare against the maximum allowed requests
- Return whether they're allowed to make another request

**Returns:** `(is_allowed, current_count, max_allowed)`

### 1.2 `increment_rate_limit(user_id)`

**Purpose:** Record that a user made a request

**What it should do:**
- Increment the counter in Redis for this user
- Set an expiration time on the first request so counters auto-cleanup
- Return the new count

**Key concept:** Use Redis INCR which atomically increments (and creates the key if needed)

### 1.3 `get_rate_limit_status(user_id)`

**Purpose:** Get detailed info for response headers

**What it should do:**
- Get current count and time-to-live from Redis
- Calculate how many requests remain
- Return a dictionary with limit info

## Step 2: Test Your Functions

Run the built-in tests to verify your implementation:

```bash
python state_store.py
```

Expected output when tests pass:
```
Testing Rate Limiting Implementation...
============================================================

1. Checking initial rate limit...
   Allowed: True, Current: 0, Max: 5

2. Incrementing rate limit...
   After increment 1: count = 1
   ...
   Allowed: True, Current: 3, Max: 5

3. Hitting the rate limit...
   Allowed: False, Current: 5, Max: 5

4. Getting rate limit status...
   Status: {'limit': 5, 'remaining': 0, ...}

============================================================
All tests passed!
```

## Step 3: Integrate into the API (main.py)

Once your functions work, integrate them into the API:

### 3.1 Import your functions

Add the rate limiting functions to the imports at the top of `main.py`.

### 3.2 Add rate limit check to `submit_task()`

**Before** creating the task:
- Check if the user is within their rate limit
- If not allowed, raise an HTTPException with status code 429
- Include a helpful message telling them when they can retry

**After** task creation succeeds:
- Increment the rate limit counter
- Add rate limit headers to the response

### 3.3 Implement `add_rate_limit_headers()`

Set these standard headers on the response:
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Requests left in current window
- `X-RateLimit-Reset`: Seconds until window resets

## Step 4: Test the Full Integration

```bash
# Submit 5 tasks (should all succeed)
for i in {1..5}; do
  curl -s -X POST http://localhost:8000/tasks \
    -H "Content-Type: application/json" \
    -H "X-User-ID: test-user" \
    -d '{"query": "Test query"}' | jq -r '.status // .detail'
done

# 6th request should fail with 429
curl -s -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-User-ID: test-user" \
  -d '{"query": "This should be rate limited"}' | jq '.'
```

Expected: First 5 return "queued", 6th returns error with "Rate limit exceeded".

### Check Rate Limit Headers

```bash
curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-User-ID: new-user" \
  -d '{"query": "Check headers"}'
```

Look for `X-RateLimit-*` headers in the response.

## Redis Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `GET key` | Get value (None if missing) | `client.get("user:rate")` |
| `INCR key` | Increment (creates with 1 if missing) | `client.incr("user:rate")` |
| `EXPIRE key seconds` | Set TTL | `client.expire("user:rate", 60)` |
| `TTL key` | Get remaining TTL | `client.ttl("user:rate")` |

## Configuration

Rate limits are configurable via environment variables:

```bash
RATE_LIMIT_MAX_REQUESTS=5    # Requests per window (default: 5)
RATE_LIMIT_WINDOW_SECONDS=60  # Window duration (default: 60)
```

## Bonus: Rate Limit Status Endpoint

Implement `GET /rate-limit` so users can check their status without making a task request.

## Solution

If you get stuck, check `state_store_solution.py` and `main_solution.py` for complete implementations.

## What You Learned

- How to implement rate limiting with Redis
- Using atomic Redis operations (INCR, EXPIRE, TTL)
- Adding custom headers to FastAPI responses
- Returning appropriate HTTP status codes (429 Too Many Requests)
- Why rate limiting is critical for production agent systems
