"""
Redis State Store - SOLUTION

This file contains the complete implementation of rate limiting functions.
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

# Maximum messages per conversation
MAX_MESSAGES_PER_CONVERSATION = int(os.getenv("MAX_MESSAGES", 100))

# Rate limit configuration
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", 5))
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
    """Generate Redis key for rate limiting."""
    current_minute = datetime.utcnow().strftime("%Y-%m-%dT%H:%M")
    return f"{user_id}:rate_limit:{current_minute}"


# =============================================================================
# RATE LIMITING FUNCTIONS - SOLUTION
# =============================================================================

def check_rate_limit(user_id: str) -> Tuple[bool, int, int]:
    """
    Check if a user is within their rate limit.

    Args:
        user_id: User identifier

    Returns:
        Tuple of (is_allowed, current_count, max_allowed)
    """
    client = get_redis_client()
    key = _rate_limit_key(user_id)

    # Get current count (returns None if key doesn't exist)
    current_count = client.get(key)

    if current_count is None:
        current_count = 0
    else:
        current_count = int(current_count)

    is_allowed = current_count < RATE_LIMIT_MAX_REQUESTS

    return (is_allowed, current_count, RATE_LIMIT_MAX_REQUESTS)


def increment_rate_limit(user_id: str) -> int:
    """
    Increment the rate limit counter for a user.

    Args:
        user_id: User identifier

    Returns:
        New count after incrementing
    """
    client = get_redis_client()
    key = _rate_limit_key(user_id)

    # Atomically increment (creates key with value 1 if doesn't exist)
    new_count = client.incr(key)

    # Set expiration on first request in window
    if new_count == 1:
        client.expire(key, RATE_LIMIT_WINDOW_SECONDS)

    return new_count


def get_rate_limit_status(user_id: str) -> dict:
    """
    Get detailed rate limit status for a user.

    Args:
        user_id: User identifier

    Returns:
        Dictionary with rate limit information
    """
    client = get_redis_client()
    key = _rate_limit_key(user_id)

    current_count = client.get(key)
    if current_count is None:
        current_count = 0
    else:
        current_count = int(current_count)

    ttl = client.ttl(key)
    if ttl < 0:
        ttl = RATE_LIMIT_WINDOW_SECONDS

    remaining = max(0, RATE_LIMIT_MAX_REQUESTS - current_count)

    return {
        "limit": RATE_LIMIT_MAX_REQUESTS,
        "remaining": remaining,
        "reset_seconds": ttl,
        "window_seconds": RATE_LIMIT_WINDOW_SECONDS
    }


# =============================================================================
# CONVERSATION HISTORY FUNCTIONS (unchanged)
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
# TEST
# =============================================================================

if __name__ == "__main__":
    print("Testing Rate Limiting Implementation (SOLUTION)...")
    print("=" * 60)

    test_user = "test-user-solution"

    # Clean up from previous runs
    client = get_redis_client()
    for key in client.keys(f"{test_user}:*"):
        client.delete(key)

    # Test 1: Check initial rate limit
    print("\n1. Checking initial rate limit...")
    is_allowed, current, max_allowed = check_rate_limit(test_user)
    print(f"   Allowed: {is_allowed}, Current: {current}, Max: {max_allowed}")
    assert is_allowed == True
    assert current == 0

    # Test 2: Increment and check
    print("\n2. Incrementing rate limit...")
    for i in range(3):
        new_count = increment_rate_limit(test_user)
        print(f"   After increment {i+1}: count = {new_count}")

    is_allowed, current, max_allowed = check_rate_limit(test_user)
    print(f"   Allowed: {is_allowed}, Current: {current}, Max: {max_allowed}")
    assert current == 3

    # Test 3: Hit the limit
    print("\n3. Hitting the rate limit...")
    for i in range(2):
        increment_rate_limit(test_user)

    is_allowed, current, max_allowed = check_rate_limit(test_user)
    print(f"   Allowed: {is_allowed}, Current: {current}, Max: {max_allowed}")
    assert is_allowed == False
    assert current == 5

    # Test 4: Get status
    print("\n4. Getting rate limit status...")
    status = get_rate_limit_status(test_user)
    print(f"   Status: {status}")
    assert status["remaining"] == 0

    print("\n" + "=" * 60)
    print("All tests passed!")
