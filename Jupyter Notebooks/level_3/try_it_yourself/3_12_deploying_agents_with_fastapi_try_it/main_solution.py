"""
FastAPI Server for Chatbot with Conversation Memory - SOLUTION

This server exposes a LangGraph chatbot with SQLite-based conversation persistence.

Run with: uvicorn main_solution:app --reload
Test at: http://localhost:8000/docs
"""

import os
import sqlite3
from typing import Annotated
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing_extensions import TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver

# Load environment variables
load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found. Add it to your .env file.")

# -----------------------------------------------------------------------------
# Step 1: Create the FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Chatbot with Memory API",
    description="A chatbot that remembers conversation history using thread IDs",
    version="1.0.0"
)

# -----------------------------------------------------------------------------
# Step 2: Define request/response models
# -----------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"

class ChatResponse(BaseModel):
    response: str
    user_id: str

class MessageItem(BaseModel):
    role: str
    content: str

class HistoryResponse(BaseModel):
    user_id: str
    messages: list[MessageItem]

# -----------------------------------------------------------------------------
# Step 3: Define the chatbot state and node
# -----------------------------------------------------------------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def chatbot_node(state: ChatState) -> ChatState:
    """Process messages using the LLM."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

# -----------------------------------------------------------------------------
# Step 4: Build the graph with SQLite checkpointer
# -----------------------------------------------------------------------------
workflow = StateGraph(ChatState)
workflow.add_node("chatbot", chatbot_node)
workflow.add_edge(START, "chatbot")
workflow.add_edge("chatbot", END)

# Create SQLite checkpointer for conversation persistence
conn = sqlite3.connect("chatbot_memory.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)

# Compile the graph with the checkpointer
chatbot = workflow.compile(checkpointer=checkpointer)

# -----------------------------------------------------------------------------
# Step 5: Define endpoints
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "Chatbot API is running"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Chat with the bot. Use the same user_id to continue a conversation.

    Different user_ids create separate conversation histories.
    """
    try:
        config = {"configurable": {"thread_id": request.user_id}}

        result = chatbot.invoke(
            {"messages": [HumanMessage(content=request.message)]},
            config=config
        )

        final_message = result["messages"][-1]
        return ChatResponse(
            response=final_message.content,
            user_id=request.user_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# SOLUTION: History endpoint implementation
# -----------------------------------------------------------------------------
@app.get("/history/{user_id}", response_model=HistoryResponse)
def get_history(user_id: str):
    """
    Retrieve the conversation history for a specific user.

    Args:
        user_id: The user ID to retrieve history for

    Returns:
        HistoryResponse with the user_id and list of messages
    """
    try:
        # Create config with the thread_id set to user_id
        config = {"configurable": {"thread_id": user_id}}

        # Use checkpointer.get_tuple(config) to retrieve the checkpoint
        checkpoint_tuple = checkpointer.get_tuple(config)

        # If no checkpoint exists, return empty messages
        if checkpoint_tuple is None:
            return HistoryResponse(user_id=user_id, messages=[])

        # Extract the checkpoint from the tuple
        checkpoint = checkpoint_tuple.checkpoint

        # Get messages from the checkpoint's channel_values
        stored_messages = checkpoint.get("channel_values", {}).get("messages", [])

        # Convert messages to MessageItem format
        message_items = []
        for msg in stored_messages:
            message_items.append(
                MessageItem(
                    role=msg.type,  # "human" or "ai"
                    content=msg.content
                )
            )

        return HistoryResponse(user_id=user_id, messages=message_items)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
