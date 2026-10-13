"""
Simple Tavily Search Agent (PROVIDED)

This is a simple agent that performs a single web search using Tavily
and returns a summarized answer. It's simpler and faster than the full
task decomposition agent.

This agent is PROVIDED to students - you don't need to modify this file.
Your task is to:
1. Add a Celery task in tasks.py that calls run_simple_search()
2. Add a FastAPI endpoint in main.py that enqueues your new task
"""

import os
from typing import Optional, Callable

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

# Load environment variables
load_dotenv()


# -----------------------------------------------------------------------------
# Agent Setup
# -----------------------------------------------------------------------------

def _create_search_agent():
    """Create a simple search agent with Tavily tool."""
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1
    )

    search_tool = TavilySearch(
        max_results=5,
        search_depth="basic",
        include_raw_content=False,
        include_images=False
    )

    agent = create_agent(
        model=model,
        tools=[search_tool]
    )

    return agent


# Create agent instance (lazy initialization)
_agent = None


def _get_agent():
    """Get or create the agent instance."""
    global _agent
    if _agent is None:
        _agent = _create_search_agent()
    return _agent


# -----------------------------------------------------------------------------
# Main Function (Use this in your Celery task)
# -----------------------------------------------------------------------------

ProgressCallback = Optional[Callable[[str, Optional[str]], None]]


def run_simple_search(
    query: str,
    on_progress: ProgressCallback = None
) -> dict:
    """
    Run a simple web search and return a summarized answer.

    This is the function you should call from your Celery task.

    Args:
        query: The user's search query
        on_progress: Optional callback function(status, progress_message)
                    Called at each step to report progress

    Returns:
        Dictionary containing:
        - query: Original query
        - answer: The agent's response
        - tool_used: Whether the agent used the search tool

    Example:
        result = run_simple_search("What is the capital of France?")
        print(result["answer"])
    """
    if on_progress:
        on_progress("running", "starting_search")

    # Get the agent
    agent = _get_agent()

    if on_progress:
        on_progress("running", "searching_web")

    # Invoke the agent
    result = agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })

    if on_progress:
        on_progress("running", "generating_response")

    # Extract the final response
    final_message = result["messages"][-1]
    answer = final_message.content

    # Check if tools were used (look for tool messages)
    tool_used = any(
        msg.type == "tool" for msg in result["messages"]
        if hasattr(msg, "type")
    )

    return {
        "query": query,
        "answer": answer,
        "tool_used": tool_used
    }


# -----------------------------------------------------------------------------
# Test the agent directly
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    def print_progress(status: str, progress: Optional[str]):
        print(f"[{status.upper()}] {progress}")

    test_query = "What are the latest AI developments in 2024?"
    print(f"\nTesting with query: {test_query}\n")

    result = run_simple_search(test_query, on_progress=print_progress)

    print(f"\n{'='*60}")
    print(f"Tool used: {result['tool_used']}")
    print(f"\nAnswer:\n{result['answer']}")
