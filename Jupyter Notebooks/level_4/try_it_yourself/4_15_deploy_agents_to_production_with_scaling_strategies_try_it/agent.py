"""
Task Decomposition Agent with Conversation History Support

This module contains the LangGraph-based task decomposition agent that:
- Analyzes complex queries and breaks them into sub-queries
- Determines sequential vs parallel execution strategy
- Executes searches using Tavily API
- Synthesizes results into comprehensive answers
- Supports conversation history for contextual responses

The agent is STATELESS:
- All context is passed in (not stored in memory)
- Conversation history is fetched from external storage
- Any worker can run this agent with any conversation
"""

import os
import asyncio
from typing import TypedDict, List, Literal, Optional, Callable

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_tavily import TavilySearch
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()


# -----------------------------------------------------------------------------
# State and Schema Definitions
# -----------------------------------------------------------------------------

class WorkflowState(TypedDict):
    """State schema for task decomposition workflow."""
    query: str
    conversation_history: List[dict]  # Added for context
    sub_queries: List[str]
    execution_strategy: str
    num_sequential_steps: int
    search_results: List[str]
    synthesis: str
    final_answer: str


class QueryAnalysis(BaseModel):
    """Schema for query analysis results."""
    execution_strategy: Literal["sequential", "parallel"] = Field(
        description="'sequential' if sub-queries depend on each other, 'parallel' if independent"
    )
    sub_queries: List[str] = Field(
        description="List of sub-queries. For sequential: only the FIRST query. For parallel: 2-4 independent queries."
    )
    num_sequential_steps: int = Field(
        default=2,
        description="For sequential execution: total number of steps needed (2-4). Ignored for parallel."
    )
    reasoning: str = Field(
        description="Brief explanation of why this strategy was chosen"
    )


# -----------------------------------------------------------------------------
# Initialize LLM and Tools
# -----------------------------------------------------------------------------

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
query_analyzer = llm.with_structured_output(QueryAnalysis)
tavily_search = TavilySearch(max_results=5, topic="general", search_depth="basic")


# -----------------------------------------------------------------------------
# Progress Callback Type
# -----------------------------------------------------------------------------

ProgressCallback = Optional[Callable[[str, Optional[str]], None]]


# -----------------------------------------------------------------------------
# Node Functions (Updated for Conversation History)
# -----------------------------------------------------------------------------

def create_query_analyzer_node(on_progress: ProgressCallback = None):
    """Create a query analyzer node with optional progress callback."""

    def query_analyzer_node(state: WorkflowState) -> WorkflowState:
        """Analyzes the user query and determines execution strategy."""
        query = state["query"]
        history = state.get("conversation_history", [])

        if on_progress:
            on_progress("running", "analyzing_query")

        # Build context from conversation history
        context_section = ""
        if history:
            context_messages = []
            for msg in history[-5:]:  # Last 5 messages for context
                role = msg.get("role", "")
                content = msg.get("content", "")[:200]  # Truncate long messages
                context_messages.append(f"[{role}]: {content}")
            context_section = f"\n\nPrevious conversation context:\n" + "\n".join(context_messages)

        system_prompt = f"""You are a query decomposition expert. Analyze the user's query and determine the best execution strategy.
{context_section}

**SEQUENTIAL Execution:**
Use when sub-queries DEPEND on previous results (multi-hop reasoning).

Examples:
1. "AI products launched by the company that acquired DeepMind in 2024" (2 steps)
   - Step 1: "Which company acquired DeepMind?" -> Get answer
   - Step 2: Generate query based on answer: "AI products launched by [Company] in 2024"

For sequential: Provide ONLY the first query. Specify how many sequential steps (2-4).

**PARALLEL Execution:**
Use when sub-queries are INDEPENDENT.

Example: "Summarize Tesla's Q4 2024 earnings, recent product launches, and leadership changes"
  - Query 1: "Tesla Q4 2024 earnings"
  - Query 2: "Tesla recent product launches"
  - Query 3: "Tesla leadership changes"

For parallel: Provide ALL sub-queries (2-4 queries) that can run simultaneously."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {query}"}
        ]

        result = query_analyzer.invoke(messages)

        return {
            **state,
            "execution_strategy": result.execution_strategy,
            "sub_queries": result.sub_queries,
            "num_sequential_steps": result.num_sequential_steps
        }

    return query_analyzer_node


def create_sequential_execution_node(on_progress: ProgressCallback = None):
    """Create a sequential execution node with optional progress callback."""

    def sequential_execution_node(state: WorkflowState) -> WorkflowState:
        """Executes sub-queries sequentially where each depends on previous results."""
        sub_queries = state["sub_queries"]
        original_query = state["query"]
        num_steps = state["num_sequential_steps"]

        all_results = []
        current_synthesis = ""

        # Step 1: Execute first sub-query
        first_query = sub_queries[0]

        if on_progress:
            on_progress("running", f"executing_search_step_1_of_{num_steps}")

        search_response_1 = tavily_search.invoke({"query": first_query})
        results_1 = search_response_1.get("results", [])

        formatted_results_1 = "\n\n".join([
            f"Title: {r.get('title', 'N/A')}\nContent: {r.get('content', '')}"
            for r in results_1
        ])

        all_results.append(f"Query 1: {first_query}\n{formatted_results_1}")

        # Synthesize first results
        synthesis_prompt = f"""Based on these search results, extract the key answer to: "{first_query}"

Search Results:
{formatted_results_1}

Provide a concise, factual answer (1-2 sentences)."""

        synthesis_response = llm.invoke([HumanMessage(content=synthesis_prompt)])
        current_synthesis = synthesis_response.content

        # Loop through remaining steps
        for step_num in range(2, num_steps + 1):
            if on_progress:
                on_progress("running", f"executing_search_step_{step_num}_of_{num_steps}")

            # Generate next query based on current synthesis
            next_query_prompt = f"""Original query: {original_query}

Previous findings:
{current_synthesis}

This is step {step_num} of {num_steps}.

Generate the next specific search query that builds upon previous findings.
Return ONLY the search query, nothing else."""

            next_query_response = llm.invoke([HumanMessage(content=next_query_prompt)])
            next_query = next_query_response.content.strip()

            # Execute the query
            search_response = tavily_search.invoke({"query": next_query})
            results = search_response.get("results", [])

            formatted_results = "\n\n".join([
                f"Title: {r.get('title', 'N/A')}\nContent: {r.get('content', '')}"
                for r in results
            ])

            all_results.append(f"Query {step_num}: {next_query}\n{formatted_results}")

            # Update synthesis
            update_synthesis_prompt = f"""Previous synthesis:
{current_synthesis}

New search results for query "{next_query}":
{formatted_results}

Update the synthesis by integrating new information. Keep it concise (2-3 sentences)."""

            synthesis_response = llm.invoke([HumanMessage(content=update_synthesis_prompt)])
            current_synthesis = synthesis_response.content

        return {
            **state,
            "search_results": all_results,
            "synthesis": current_synthesis
        }

    return sequential_execution_node


def create_parallel_execution_node(on_progress: ProgressCallback = None):
    """Create a parallel execution node with optional progress callback."""

    async def search_parallel(sub_queries: List[str]) -> List[str]:
        """Execute multiple search queries in parallel."""
        tasks = [tavily_search.ainvoke({"query": q}) for q in sub_queries]
        results = await asyncio.gather(*tasks)

        formatted_results = []
        for i, (query, search_response) in enumerate(zip(sub_queries, results), 1):
            search_results = search_response.get("results", [])
            formatted = "\n\n".join([
                f"Title: {r.get('title', 'N/A')}\nContent: {r.get('content', '')}"
                for r in search_results
            ])
            formatted_results.append(f"Query {i}: {query}\n{formatted}")

        return formatted_results

    def parallel_execution_node(state: WorkflowState) -> WorkflowState:
        """Executes independent sub-queries in parallel."""
        sub_queries = state["sub_queries"]

        if on_progress:
            on_progress("running", f"executing_{len(sub_queries)}_parallel_searches")

        # Run parallel search
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                search_results = asyncio.run(search_parallel(sub_queries))
            else:
                search_results = loop.run_until_complete(search_parallel(sub_queries))
        except RuntimeError:
            search_results = asyncio.run(search_parallel(sub_queries))

        return {
            **state,
            "search_results": search_results
        }

    return parallel_execution_node


def create_synthesis_node(on_progress: ProgressCallback = None):
    """Create a synthesis node with optional progress callback."""

    def synthesis_node(state: WorkflowState) -> WorkflowState:
        """Synthesizes all search results into a comprehensive final answer."""
        query = state["query"]
        search_results = state["search_results"]
        execution_strategy = state["execution_strategy"]
        history = state.get("conversation_history", [])

        if on_progress:
            on_progress("running", "synthesizing_results")

        combined_results = "\n\n" + "="*80 + "\n\n".join(search_results)

        # Include conversation context in synthesis
        context_note = ""
        if history:
            context_note = "\n\nNote: Consider the previous conversation context when formulating your response."

        system_prompt = f"""You are a helpful assistant that synthesizes information from multiple search results.

Provide a comprehensive, well-structured answer that:
- Directly addresses the original query
- Integrates information from all search results
- Is clear, concise, and informative
- Cites specific facts when relevant{context_note}"""

        user_prompt = f"""Original Query: {query}

Execution Strategy: {execution_strategy}

Search Results:
{combined_results}

Please provide a comprehensive answer to the original query."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = llm.invoke(messages)

        return {
            **state,
            "final_answer": response.content
        }

    return synthesis_node


def route_by_strategy(state: WorkflowState) -> Literal["sequential", "parallel"]:
    """Routes to the appropriate execution node based on strategy."""
    return state["execution_strategy"]


# -----------------------------------------------------------------------------
# Build and Run Workflow
# -----------------------------------------------------------------------------

def build_workflow(on_progress: ProgressCallback = None) -> StateGraph:
    """
    Build the task decomposition workflow graph.

    Args:
        on_progress: Optional callback function(status, progress_message)

    Returns:
        Compiled LangGraph workflow
    """
    workflow = StateGraph(WorkflowState)

    # Add nodes with progress callbacks
    workflow.add_node("query_analyzer", create_query_analyzer_node(on_progress))
    workflow.add_node("sequential", create_sequential_execution_node(on_progress))
    workflow.add_node("parallel", create_parallel_execution_node(on_progress))
    workflow.add_node("synthesis", create_synthesis_node(on_progress))

    # Add edges
    workflow.add_edge(START, "query_analyzer")
    workflow.add_conditional_edges(
        "query_analyzer",
        route_by_strategy,
        {"sequential": "sequential", "parallel": "parallel"}
    )
    workflow.add_edge("sequential", "synthesis")
    workflow.add_edge("parallel", "synthesis")
    workflow.add_edge("synthesis", END)

    return workflow.compile()


def run_task_decomposition(
    query: str,
    on_progress: ProgressCallback = None,
    conversation_history: Optional[List[dict]] = None
) -> dict:
    """
    Run the task decomposition agent on a query.

    STATELESS: All context is passed in, not stored in the agent.

    Args:
        query: The user's query to process
        on_progress: Optional callback function(status, progress_message)
                    Called at each major step to report progress
        conversation_history: Optional list of previous messages for context
                             Format: [{"role": "user|assistant", "content": "..."}]

    Returns:
        Dictionary containing:
        - query: Original query
        - execution_strategy: 'sequential' or 'parallel'
        - final_answer: The synthesized answer
        - search_results: List of search results used
    """
    # Build workflow with progress callback
    app = build_workflow(on_progress)

    # Create initial state with conversation history
    initial_state = {
        "query": query,
        "conversation_history": conversation_history or [],
        "sub_queries": [],
        "execution_strategy": "",
        "num_sequential_steps": 2,
        "search_results": [],
        "synthesis": "",
        "final_answer": ""
    }

    # Run the workflow
    result = app.invoke(initial_state)

    return {
        "query": result["query"],
        "execution_strategy": result["execution_strategy"],
        "final_answer": result["final_answer"],
        "search_results": result["search_results"]
    }


# -----------------------------------------------------------------------------
# Test the agent directly
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    def print_progress(status: str, progress: Optional[str]):
        print(f"[{status.upper()}] {progress}")

    # Test with conversation history
    history = [
        {"role": "user", "content": "I'm interested in AI companies."},
        {"role": "assistant", "content": "AI is a fascinating field! What would you like to know?"},
    ]

    test_query = "What AI products were launched by Google in 2024?"
    print(f"\nTesting with query: {test_query}")
    print(f"Conversation history: {len(history)} messages\n")

    result = run_task_decomposition(
        test_query,
        on_progress=print_progress,
        conversation_history=history
    )

    print(f"\n{'='*80}")
    print(f"Execution Strategy: {result['execution_strategy']}")
    print(f"\nFinal Answer:\n{result['final_answer']}")
