"""
Redis State Store for Conversation History and Rate Limiting

This module manages ephemeral state in Redis, including:
- Conversation history (messages between user and agent)
- Session state (current context, pending operations)
- TTL-based automatic cleanup
- Rate limiting (YOUR TASK!)

=============================================================================
TRY IT YOURSELF: Implement Rate Limiting
=============================================================================

OBJECTIVE:
    Implement per-user rate limiting to prevent API abuse and control costs.
    Users should be limited to a configurable number of tasks per time window.

YOUR TASK:
    1. Implement check_rate_limit() - Check if user is within rate limit
    2. Implement increment_rate_limit() - Record a new request
    3. Implement get_rate_limit_status() - Get current usage info

BACKGROUND:
    From the slides on "Cost Control and Multi-Tenant Fairness":
    - "The Risk: LLM costs scale linearly; one runaway loop can drain budgets"
    - "Throttling: Return 429 Too Many Requests rather than over-scaling"

REDIS PATTERN:
    Key: "{user_id}:rate_limit:{window}"
    Value: Counter of requests in current window
    TTL: Window duration (e.g., 60 seconds)

    Example for user "alice" with 1-minute windows:
    - Key: "alice:rate_limit:2024-01-15T10:30"
    - Value: 3 (she's made 3 requests this minute)
    - TTL: 60 seconds (auto-cleanup when window expires)

=============================================================================
"""

import os
import json
from datetime import datetime
from typing import Optional, Tuple
import redis

# Redis connection settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/2")

# TTL for conversation history (1 hour default)
CONVERSATION_TTL = int(os.getenv("CONVERSATION_TTL", 3600))

# Maximum messages per conversation (to prevent unbounded growth)
MAX_MESSAGES_PER_CONVERSATION = int(os.getenv("MAX_MESSAGES", 100))

# =============================================================================
# RATE LIMIT CONFIGURATION (Used by your implementation)
# =============================================================================

# Maximum requests per window
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", 5))

# Window duration in seconds (60 = 1 minute)
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))


def get_redis_client() -> redis.Redis:
    """Get a Redis client instance."""
    return redis.from_url(REDIS_URL, decode_responses=True)


def _conversation_key(user_id: str, conversation_id: str) -> str:
    """Generate Redis key for conversation messages."""
    return f"{user_id}:conversation:{conversation_id}:messages"


def _user_conversations_key(user_id: str) -> str:
    """Generate Redis key for user's conversation list."""
    return f"{user_id}:conversations"


def _rate_limit_key(user_id: str) -> str:
    """
    Generate Redis key for rate limiting.

    Uses minute-based windows for simplicity.
    Example: "user-alice-123:rate_limit:2024-01-15T10:30"
    """
    current_minute = datetime.utcnow().strftime("%Y-%m-%dT%H:%M")
    return f"{user_id}:rate_limit:{current_minute}"


# =============================================================================
# RATE LIMITING FUNCTIONS (YOUR TASK!)
# =============================================================================

def check_rate_limit(user_id: str) -> Tuple[bool, int, int]:
    """
    Check if a user is within their rate limit.

    Args:
        user_id: User identifier

    Returns:
        Tuple of (is_allowed, current_count, max_allowed)
        - is_allowed: True if user can make another request
        - current_count: Number of requests made in current window
        - max_allowed: Maximum requests allowed per window

    Example:
        is_allowed, current, max_allowed = check_rate_limit("user-alice")
        if not is_allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    ==========================================================================
    YOUR CODE HERE
    ==========================================================================

    HINTS:
    1. Get a Redis client using get_redis_client()
    2. Generate the rate limit key using _rate_limit_key(user_id)
    3. Use Redis GET command to retrieve the current count
       - If the key doesn't exist, GET returns None (meaning 0 requests)
       - If it exists, convert the string value to an integer
    4. Compare the current count against RATE_LIMIT_MAX_REQUESTS
    5. Return a tuple: (whether allowed, current count, max allowed)

    USEFUL REDIS COMMANDS:
    - client.get(key) - Returns the value or None if key doesn't exist

    ==========================================================================
    """
    # TODO: Implement this function

    # Placeholder - allows all requests (remove this when implementing)
    return (True, 0, RATE_LIMIT_MAX_REQUESTS)


def increment_rate_limit(user_id: str) -> int:
    """
    Increment the rate limit counter for a user.

    Call this AFTER successfully processing a request.

    Args:
        user_id: User identifier

    Returns:
        New count after incrementing

    Example:
        # After successfully creating a task
        new_count = increment_rate_limit("user-alice")
        print(f"User has made {new_count} requests this window")

    ==========================================================================
    YOUR CODE HERE
    ==========================================================================

    HINTS:
    1. Get a Redis client and generate the rate limit key
    2. Use Redis INCR command to atomically increment the counter
       - INCR automatically creates the key with value 1 if it doesn't exist
       - INCR is atomic, so it's safe for concurrent requests
    3. If this is the first request in the window (count == 1), set the TTL
       - Use EXPIRE command to set how long until the key auto-deletes
       - Use RATE_LIMIT_WINDOW_SECONDS for the TTL value
    4. Return the new count

    USEFUL REDIS COMMANDS:
    - client.incr(key) - Increment and return new value (creates key if needed)
    - client.expire(key, seconds) - Set time-to-live on a key

    ==========================================================================
    """
    # TODO: Implement this function

    # Placeholder - does nothing (remove this when implementing)
    return 1


def get_rate_limit_status(user_id: str) -> dict:
    """
    Get detailed rate limit status for a user.

    Useful for returning rate limit headers in API responses.

    Args:
        user_id: User identifier

    Returns:
        Dictionary with rate limit information:
        {
            "limit": 5,              # Max requests per window
            "remaining": 3,          # Requests remaining
            "reset_seconds": 45,     # Seconds until window resets
            "window_seconds": 60     # Window duration
        }

    Example:
        status = get_rate_limit_status("user-alice")
        response.headers["X-RateLimit-Limit"] = str(status["limit"])
        response.headers["X-RateLimit-Remaining"] = str(status["remaining"])

    ==========================================================================
    YOUR CODE HERE
    ==========================================================================

    HINTS:
    1. Get the current count (similar to check_rate_limit)
    2. Use Redis TTL command to get remaining time until key expires
       - TTL returns -2 if key doesn't exist
       - TTL returns -1 if key exists but has no expiration
       - Otherwise returns seconds remaining
    3. Calculate "remaining" as max(0, limit - current_count)
    4. Handle TTL edge cases: if TTL is negative, use the full window duration
    5. Return a dictionary with all the rate limit info

    USEFUL REDIS COMMANDS:
    - client.ttl(key) - Returns time-to-live in seconds

    ==========================================================================
    """
    # TODO: Implement this function

    # Placeholder - returns default values (remove this when implementing)
    return {
        "limit": RATE_LIMIT_MAX_REQUESTS,
        "remaining": RATE_LIMIT_MAX_REQUESTS,
        "reset_seconds": RATE_LIMIT_WINDOW_SECONDS,
        "window_seconds": RATE_LIMIT_WINDOW_SECONDS
    }


# =============================================================================
# CONVERSATION HISTORY FUNCTIONS (Already implemented - no changes needed)
# =============================================================================

def store_message(
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None
) -> dict:
    """Store a message in conversation history."""
    client = get_redis_client()
    key = _conversation_key(user_id, conversation_id)

    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": metadata or {}
    }

    client.rpush(key, json.dumps(message))
    client.ltrim(key, -MAX_MESSAGES_PER_CONVERSATION, -1)
    client.expire(key, CONVERSATION_TTL)

    conv_list_key = _user_conversations_key(user_id)
    client.zadd(conv_list_key, {conversation_id: datetime.utcnow().timestamp()})
    client.expire(conv_list_key, CONVERSATION_TTL)

    return message


def get_conversation_history(
    user_id: str,
    conversation_id: str,
    limit: Optional[int] = None
) -> list[dict]:
    """Retrieve conversation history."""
    client = get_redis_client()
    key = _conversation_key(user_id, conversation_id)

    if limit:
        messages_json = client.lrange(key, -limit, -1)
    else:
        messages_json = client.lrange(key, 0, -1)

    messages = [json.loads(m) for m in messages_json]

    if messages:
        client.expire(key, CONVERSATION_TTL)

    return messages


def get_user_conversations(user_id: str, limit: int = 20) -> list[dict]:
    """Get list of user's conversations."""
    client = get_redis_client()
    conv_list_key = _user_conversations_key(user_id)

    conversation_ids = client.zrevrange(conv_list_key, 0, limit - 1, withscores=True)

    conversations = []
    for conv_id, timestamp in conversation_ids:
        key = _conversation_key(user_id, conv_id)
        message_count = client.llen(key)

        first_message = client.lindex(key, 0)
        preview = ""
        if first_message:
            msg = json.loads(first_message)
            preview = msg.get("content", "")[:100]

        conversations.append({
            "conversation_id": conv_id,
            "last_activity": datetime.fromtimestamp(timestamp).isoformat(),
            "message_count": message_count,
            "preview": preview
        })

    return conversations


def delete_conversation(user_id: str, conversation_id: str) -> bool:
    """Delete a conversation and all its messages."""
    client = get_redis_client()
    key = _conversation_key(user_id, conversation_id)
    conv_list_key = _user_conversations_key(user_id)

    deleted = client.delete(key)
    client.zrem(conv_list_key, conversation_id)

    return deleted > 0


def get_conversation_formatted_for_llm(
    user_id: str,
    conversation_id: str,
    system_prompt: Optional[str] = None
) -> list[dict]:
    """Get conversation history formatted for LLM consumption."""
    messages = get_conversation_history(user_id, conversation_id)

    llm_messages = []

    if system_prompt:
        llm_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        llm_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    return llm_messages


# =============================================================================
# TEST YOUR IMPLEMENTATION
# =============================================================================

if __name__ == "__main__":
    print("Testing Rate Limiting Implementation...")
    print("=" * 60)

    test_user = "test-user-rate-limit"

    # Test 1: Check initial rate limit
    print("\n1. Checking initial rate limit...")
    is_allowed, current, max_allowed = check_rate_limit(test_user)
    print(f"   Allowed: {is_allowed}, Current: {current}, Max: {max_allowed}")
    assert is_allowed == True, "Should be allowed initially"
    assert current == 0, "Should have 0 requests initially"

    # Test 2: Increment and check
    print("\n2. Incrementing rate limit...")
    for i in range(3):
        new_count = increment_rate_limit(test_user)
        print(f"   After increment {i+1}: count = {new_count}")

    is_allowed, current, max_allowed = check_rate_limit(test_user)
    print(f"   Allowed: {is_allowed}, Current: {current}, Max: {max_allowed}")
    assert current == 3, "Should have 3 requests"

    # Test 3: Hit the limit
    print("\n3. Hitting the rate limit...")
    for i in range(2):
        increment_rate_limit(test_user)

    is_allowed, current, max_allowed = check_rate_limit(test_user)
    print(f"   Allowed: {is_allowed}, Current: {current}, Max: {max_allowed}")
    assert is_allowed == False, "Should NOT be allowed after 5 requests"
    assert current == 5, "Should have 5 requests"

    # Test 4: Get status
    print("\n4. Getting rate limit status...")
    status = get_rate_limit_status(test_user)
    print(f"   Status: {status}")
    assert status["remaining"] == 0, "Should have 0 remaining"

    print("\n" + "=" * 60)
    print("All tests passed! Your implementation is correct.")
    print("\nNote: Wait 60 seconds and run again to see the window reset.")
