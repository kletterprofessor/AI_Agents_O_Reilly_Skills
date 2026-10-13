"""
FastAPI Server for Chatbot with Conversation Memory

This server exposes a LangGraph chatbot with SQLite-based conversation persistence.

Run with: uvicorn main:app --reload
Test at: http://localhost:8000/docs

YOUR TASK:
1. Implement the MessageItem and HistoryResponse Pydantic models
2. Implement the GET /history/{user_id} endpoint to retrieve conversation history
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

# -----------------------------------------------------------------------------
# YOUR TASK 1: Define the Pydantic models for the history endpoint
# -----------------------------------------------------------------------------
# TODO: Implement MessageItem model
# - Should have a 'role' field (str) for the message role ("human" or "ai")
# - Should have a 'content' field (str) for the message content
class MessageItem(BaseModel):
    pass  # Replace with your implementation


# TODO: Implement HistoryResponse model
# - Should have a 'user_id' field (str)
# - Should have a 'messages' field (list of MessageItem)
class HistoryResponse(BaseModel):
    pass  # Replace with your implementation

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
# YOUR TASK 2: Implement the history endpoint
# -----------------------------------------------------------------------------
# TODO: Complete the route below
@app.get("", response_model=)
# TODO: Complete the function
def get_history(user_id: str):
    """
    Retrieve the conversation history for a specific user.

    Args:
        user_id: The user ID to retrieve history for

    Returns:
        HistoryResponse with the user_id and list of messages

    Hints:
        - Use checkpointer.get_tuple(config) to get the stored state
        - The config format is: {"configurable": {"thread_id": user_id}}
        - Messages have a 'type' attribute ("human" or "ai") and 'content' attribute
        - Return an empty messages list if no history exists
    """
    # TODO: Implement this endpoint
    # 1. Create the config with the thread_id set to user_id
    # 2. Use checkpointer.get_tuple(config) to retrieve the checkpoint
    # 3. Extract messages from the checkpoint state
    # 4. Convert messages to MessageItem format
    # 5. Return HistoryResponse with the messages

    raise HTTPException(status_code=501, detail="Not implemented - this is your task!")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
