"""
Redis State Store for Conversation History

This module manages ephemeral state in Redis, including:
- Conversation history (messages between user and agent)
- Session state (current context, pending operations)
- TTL-based automatic cleanup

Why Redis for Conversation History?
- Fast reads/writes for real-time interactions
- Automatic TTL cleanup prevents unbounded growth
- Shared state allows any worker to handle any request (stateless)
- Supports horizontal scaling via Redis Cluster

Storage Pattern:
- Key format: {user_id}:conversation:{conversation_id}:messages
- Value: JSON list of messages
- TTL: Configurable (default 1 hour)
"""

import os
import json
from datetime import datetime
from typing import Optional
import redis

# Redis connection settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/2")

# TTL for conversation history (1 hour default)
CONVERSATION_TTL = int(os.getenv("CONVERSATION_TTL", 3600))

# Maximum messages per conversation (to prevent unbounded growth)
MAX_MESSAGES_PER_CONVERSATION = int(os.getenv("MAX_MESSAGES", 100))


def get_redis_client() -> redis.Redis:
    """Get a Redis client instance."""
    return redis.from_url(REDIS_URL, decode_responses=True)


def _conversation_key(user_id: str, conversation_id: str) -> str:
    """Generate Redis key for conversation messages."""
    return f"{user_id}:conversation:{conversation_id}:messages"


def _user_conversations_key(user_id: str) -> str:
    """Generate Redis key for user's conversation list."""
    return f"{user_id}:conversations"


def store_message(
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None
) -> dict:
    """
    Store a message in conversation history.

    Args:
        user_id: User identifier
        conversation_id: Conversation identifier
        role: Message role ('user', 'assistant', 'system')
        content: Message content
        metadata: Optional metadata (task_id, tool calls, etc.)

    Returns:
        The stored message with timestamp
    """
    client = get_redis_client()
    key = _conversation_key(user_id, conversation_id)

    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": metadata or {}
    }

    # Add message to list
    client.rpush(key, json.dumps(message))

    # Trim to max messages (keep most recent)
    client.ltrim(key, -MAX_MESSAGES_PER_CONVERSATION, -1)

    # Refresh TTL
    client.expire(key, CONVERSATION_TTL)

    # Track conversation in user's conversation list
    conv_list_key = _user_conversations_key(user_id)
    client.zadd(conv_list_key, {conversation_id: datetime.utcnow().timestamp()})
    client.expire(conv_list_key, CONVERSATION_TTL)

    return message


def get_conversation_history(
    user_id: str,
    conversation_id: str,
    limit: Optional[int] = None
) -> list[dict]:
    """
    Retrieve conversation history.

    Args:
        user_id: User identifier
        conversation_id: Conversation identifier
        limit: Optional limit on number of messages (most recent)

    Returns:
        List of messages in chronological order
    """
    client = get_redis_client()
    key = _conversation_key(user_id, conversation_id)

    if limit:
        # Get most recent N messages
        messages_json = client.lrange(key, -limit, -1)
    else:
        # Get all messages
        messages_json = client.lrange(key, 0, -1)

    messages = [json.loads(m) for m in messages_json]

    # Refresh TTL on access
    if messages:
        client.expire(key, CONVERSATION_TTL)

    return messages


def get_user_conversations(user_id: str, limit: int = 20) -> list[dict]:
    """
    Get list of user's conversations.

    Args:
        user_id: User identifier
        limit: Maximum number of conversations to return

    Returns:
        List of conversation metadata, most recent first
    """
    client = get_redis_client()
    conv_list_key = _user_conversations_key(user_id)

    # Get conversation IDs sorted by last activity (most recent first)
    conversation_ids = client.zrevrange(conv_list_key, 0, limit - 1, withscores=True)

    conversations = []
    for conv_id, timestamp in conversation_ids:
        key = _conversation_key(user_id, conv_id)
        message_count = client.llen(key)

        # Get first message as preview
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
    """
    Delete a conversation and all its messages.

    Args:
        user_id: User identifier
        conversation_id: Conversation identifier

    Returns:
        True if deleted, False if not found
    """
    client = get_redis_client()
    key = _conversation_key(user_id, conversation_id)
    conv_list_key = _user_conversations_key(user_id)

    deleted = client.delete(key)
    client.zrem(conv_list_key, conversation_id)

    return deleted > 0


def clear_user_conversations(user_id: str) -> int:
    """
    Clear all conversations for a user.

    Args:
        user_id: User identifier

    Returns:
        Number of conversations deleted
    """
    client = get_redis_client()
    conv_list_key = _user_conversations_key(user_id)

    # Get all conversation IDs
    conversation_ids = client.zrange(conv_list_key, 0, -1)

    # Delete each conversation
    deleted = 0
    for conv_id in conversation_ids:
        key = _conversation_key(user_id, conv_id)
        deleted += client.delete(key)

    # Delete the conversation list
    client.delete(conv_list_key)

    return deleted


def extend_conversation_ttl(user_id: str, conversation_id: str, ttl: int = None) -> bool:
    """
    Extend the TTL of a conversation.

    Args:
        user_id: User identifier
        conversation_id: Conversation identifier
        ttl: New TTL in seconds (defaults to CONVERSATION_TTL)

    Returns:
        True if TTL was set, False if conversation not found
    """
    client = get_redis_client()
    key = _conversation_key(user_id, conversation_id)

    if not client.exists(key):
        return False

    client.expire(key, ttl or CONVERSATION_TTL)
    return True


def get_conversation_formatted_for_llm(
    user_id: str,
    conversation_id: str,
    system_prompt: Optional[str] = None
) -> list[dict]:
    """
    Get conversation history formatted for LLM consumption.

    Args:
        user_id: User identifier
        conversation_id: Conversation identifier
        system_prompt: Optional system prompt to prepend

    Returns:
        List of messages in LLM format [{"role": ..., "content": ...}]
    """
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


# Session state management (for more complex agent state)

def set_session_state(
    user_id: str,
    conversation_id: str,
    state: dict,
    ttl: int = None
):
    """
    Store arbitrary session state for a conversation.

    Args:
        user_id: User identifier
        conversation_id: Conversation identifier
        state: State dictionary to store
        ttl: Optional TTL (defaults to CONVERSATION_TTL)
    """
    client = get_redis_client()
    key = f"{user_id}:conversation:{conversation_id}:state"

    client.set(key, json.dumps(state), ex=ttl or CONVERSATION_TTL)


def get_session_state(user_id: str, conversation_id: str) -> Optional[dict]:
    """
    Retrieve session state for a conversation.

    Args:
        user_id: User identifier
        conversation_id: Conversation identifier

    Returns:
        State dictionary or None if not found
    """
    client = get_redis_client()
    key = f"{user_id}:conversation:{conversation_id}:state"

    state_json = client.get(key)
    if state_json:
        return json.loads(state_json)
    return None


def update_session_state(
    user_id: str,
    conversation_id: str,
    updates: dict
) -> dict:
    """
    Update session state (merge with existing).

    Args:
        user_id: User identifier
        conversation_id: Conversation identifier
        updates: Dictionary of updates to merge

    Returns:
        Updated state dictionary
    """
    state = get_session_state(user_id, conversation_id) or {}
    state.update(updates)
    set_session_state(user_id, conversation_id, state)
    return state


if __name__ == "__main__":
    # Quick test
    test_user = "test-user-123"
    test_conv = "test-conv-456"

    print("Testing state store...")

    # Store some messages
    store_message(test_user, test_conv, "user", "What is the capital of France?")
    store_message(test_user, test_conv, "assistant", "The capital of France is Paris.")
    store_message(test_user, test_conv, "user", "What about Germany?")

    # Retrieve history
    history = get_conversation_history(test_user, test_conv)
    print(f"\nConversation history ({len(history)} messages):")
    for msg in history:
        print(f"  [{msg['role']}]: {msg['content'][:50]}...")

    # Get LLM-formatted
    llm_messages = get_conversation_formatted_for_llm(
        test_user, test_conv,
        system_prompt="You are a helpful assistant."
    )
    print(f"\nLLM-formatted messages: {len(llm_messages)}")

    # List conversations
    conversations = get_user_conversations(test_user)
    print(f"\nUser conversations: {conversations}")

    # Cleanup
    delete_conversation(test_user, test_conv)
    print("\nTest conversation deleted.")
