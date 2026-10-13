# Try It Yourself: Add a Conversation History Endpoint

## Overview

In the guided practice, you learned how to deploy a chatbot with FastAPI that uses LangGraph with SQLite-based conversation persistence. The chatbot stores conversation history per user using thread IDs.

Your task is to extend the API by implementing the Pydantic models and a new endpoint that retrieves the conversation history for a given user.

## Your Tasks

### Task 1: Implement the Pydantic Models

Define the following Pydantic models in `main.py`:

1. **MessageItem** - Represents a single message in the conversation
   - `role` (str): The role of the message sender ("human" or "ai")
   - `content` (str): The message content

2. **HistoryResponse** - The response model for the history endpoint
   - `user_id` (str): The user ID
   - `messages` (list[MessageItem]): List of messages in the conversation

### Task 2: Implement the History Endpoint

Implement the `GET /history/{user_id}` endpoint that:

1. Takes a `user_id` as a path parameter
2. Retrieves all messages from the conversation history for that user
3. Returns the messages in a structured format

## Requirements

### Endpoint Specification

- **Method**: `GET`
- **Path**: `/history/{user_id}`
- **Response Model**: `HistoryResponse` (you will implement this)

### Expected Response Format

```json
{
  "user_id": "alice",
  "messages": [
    {"role": "human", "content": "Hello, my name is Alice"},
    {"role": "ai", "content": "Hello Alice! Nice to meet you..."},
    {"role": "human", "content": "What's my name?"},
    {"role": "ai", "content": "Your name is Alice!"}
  ]
}
```

### Edge Cases to Handle

- If no conversation history exists for the user, return an empty messages list
- Handle any potential errors gracefully

## Hints

1. The `checkpointer` stores state by `thread_id` (which maps to `user_id`)
2. You can use `checkpointer.get_tuple(config)` to retrieve the stored state
3. The config format is: `{"configurable": {"thread_id": user_id}}`
4. Messages in the state have a `type` attribute (`"human"` or `"ai"`) and a `content` attribute

## Testing Your Implementation

1. Start the server:
   ```bash
   uvicorn main:app --reload
   ```

2. First, create some conversation history:
   ```bash
   python client.py "Hello, my name is Alice" --user alice
   python client.py "What's my name?" --user alice
   ```

3. Then test your history endpoint using the provided client script:
   ```bash
   python client_history.py alice
   ```

   Or use curl directly:
   ```bash
   curl http://localhost:8000/history/alice
   ```

4. You can also test via the interactive docs at: http://localhost:8000/docs

## Files

- `main.py` - The FastAPI server (implement your endpoint here)
- `client.py` - A simple client for testing the chat endpoint
- `client_history.py` - A client for testing the history endpoint
- `requirements.txt` - Python dependencies

## Solution

Once you've attempted the exercise, check `main_solution.py` to see one possible implementation.
