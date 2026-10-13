"""
Client for Long-Running Agent Tasks

=============================================================================
TRY IT YOURSELF: Add SSE Streaming Client
=============================================================================

OBJECTIVE:
    Implement a streaming client that connects to the SSE endpoint and
    receives real-time progress updates instead of polling.

YOUR TASK:
    1. Implement the `run_with_streaming()` function
    2. Parse SSE events from the streaming response
    3. Handle different event types: "status", "complete", "error"
    4. Display progress updates in real-time

SSE FORMAT:
    Server-Sent Events are plain text with this format:

        event: <event_type>
        data: <json_payload>
        <blank line separates events>

    Example:
        event: status
        data: {"status": "running", "progress": "analyzing_query"}

        event: complete
        data: {"status": "completed", "final_answer": "..."}

PARSING SSE EVENTS:
    We've provided `parse_sse_events()` to handle SSE parsing for you!

    ```python
    response = requests.get(url, stream=True)

    for event in parse_sse_events(response):
        event_type = event["event"]      # "status", "complete", or "error"
        data = json.loads(event["data"]) # JSON payload
        print(f"Got {event_type}: {data}")
    ```

EXPECTED OUTPUT:
    When running with --stream flag:

    ======================================================================
    LONG-RUNNING AGENT TASK CLIENT (STREAMING MODE)
    ======================================================================

    Query: What AI products were launched by...

    [1] Submitting task...
        Task ID: abc123-...

    [2] Streaming progress updates...
        [status] running | analyzing_query
        [status] running | executing_search_step_1_of_2
        [status] running | executing_search_step_2_of_2
        [status] running | synthesizing_results
        [complete] Task finished!

    [3] Result received via stream!

    ======================================================================
    RESULT
    ======================================================================
    ...

HINTS:
    1. Use requests.get(url, stream=True) to keep connection open
    2. Use the provided parse_sse_events(response) to iterate over events
    3. Each event has event["event"] (type) and event["data"] (JSON string)
    4. Parse the data with json.loads(event["data"])
    5. Handle connection errors gracefully with try/except

=============================================================================

Usage:
    python client.py "Your query" --stream          # Use SSE streaming
    python client.py "Your query"                   # Use polling (existing)
    python client.py "Your query" --stream --url http://localhost:8000
"""

import argparse
import json
import time
import sys

import requests


API_BASE_URL = "http://localhost:8000"


# -----------------------------------------------------------------------------
# SSE Event Parser (PROVIDED - use this to parse streaming events)
# -----------------------------------------------------------------------------

def parse_sse_events(response):
    """
    Parse Server-Sent Events from a streaming response.

    SSE format:
        event: <event_type>
        data: <payload>
        <blank line>

    Args:
        response: A requests.Response object with stream=True

    Yields:
        dict with 'event' and 'data' keys

    Example usage:
        response = requests.get(url, stream=True)
        for event in parse_sse_events(response):
            print(f"Event: {event['event']}")
            data = json.loads(event['data'])
            print(f"Data: {data}")
    """
    current_event = {"event": "message", "data": ""}

    for line in response.iter_lines(decode_unicode=True):
        if line is None:
            continue

        # Blank line signals end of event
        if line == "":
            if current_event["data"]:
                yield current_event
                current_event = {"event": "message", "data": ""}
            continue

        # Parse event type
        if line.startswith("event:"):
            current_event["event"] = line[6:].strip()

        # Parse data (can be multiple data: lines)
        elif line.startswith("data:"):
            data = line[5:].strip()
            if current_event["data"]:
                current_event["data"] += "\n" + data
            else:
                current_event["data"] = data

        # Ignore comments and other fields (id:, retry:)
        elif line.startswith(":"):
            pass


# -----------------------------------------------------------------------------
# Existing Polling Implementation (Already Works)
# -----------------------------------------------------------------------------

def submit_task(query: str) -> str:
    """Submit a new task to the server."""
    response = requests.post(
        f"{API_BASE_URL}/tasks",
        json={"query": query}
    )

    if not response.ok:
        print(f"Error submitting task: {response.status_code}")
        print(response.text)
        sys.exit(1)

    data = response.json()
    return data["task_id"]


def poll_status(task_id: str) -> dict:
    """Poll the status of a task."""
    response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")

    if not response.ok:
        print(f"Error polling status: {response.status_code}")
        print(response.text)
        sys.exit(1)

    return response.json()


def get_result(task_id: str) -> dict:
    """Get the final result of a completed task."""
    response = requests.get(f"{API_BASE_URL}/tasks/{task_id}/result")

    if not response.ok:
        print(f"Error getting result: {response.status_code}")
        print(response.text)
        sys.exit(1)

    return response.json()


def run_with_polling(query: str, poll_interval: float = 1.0, timeout: float = 300.0) -> dict:
    """Submit a task and poll until completion (existing implementation)."""
    print("=" * 70)
    print("LONG-RUNNING AGENT TASK CLIENT (POLLING MODE)")
    print("=" * 70)
    print(f"\nQuery: {query}")
    print(f"Poll interval: {poll_interval}s | Timeout: {timeout}s")
    print("-" * 70)

    print("\n[1] Submitting task...")
    task_id = submit_task(query)
    print(f"    Task ID: {task_id}")

    print("\n[2] Polling for status...")
    start_time = time.time()
    last_progress = None

    while True:
        elapsed = time.time() - start_time

        if elapsed > timeout:
            print(f"\n    TIMEOUT after {timeout}s")
            sys.exit(1)

        status_data = poll_status(task_id)
        status = status_data["status"]
        progress = status_data.get("progress")
        strategy = status_data.get("execution_strategy")

        if progress != last_progress:
            strategy_str = f" [{strategy}]" if strategy else ""
            print(f"    [{elapsed:5.1f}s] Status: {status}{strategy_str} | Progress: {progress or '-'}")
            last_progress = progress

        if status == "completed":
            print(f"\n    Task completed in {elapsed:.1f}s")
            break
        elif status == "failed":
            error = status_data.get("error", "Unknown error")
            print(f"\n    Task FAILED: {error}")
            sys.exit(1)

        time.sleep(poll_interval)

    print("\n[3] Retrieving result...")
    result = get_result(task_id)

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"\nExecution Strategy: {result['execution_strategy']}")
    print(f"\nFinal Answer:\n{result['final_answer']}")
    print("\n" + "=" * 70)

    return result


# -----------------------------------------------------------------------------
# TODO: Implement SSE Streaming Client
# -----------------------------------------------------------------------------

def run_with_streaming(query: str, timeout: float = 300.0) -> dict:
    """
    Submit a task and receive real-time updates via SSE streaming.

    TODO: Implement this function!

    Requirements:
    1. Submit the task (use existing submit_task function)
    2. Connect to the SSE streaming endpoint: GET /tasks/{task_id}/stream
    3. Use parse_sse_events() to iterate over events
    4. Handle "status", "complete", and "error" event types
    5. Return the final result

    Example structure:

        response = requests.get(url, stream=True, timeout=timeout)

        for event in parse_sse_events(response):
            event_type = event["event"]
            data = json.loads(event["data"])

            if event_type == "status":
                # Display progress: data["status"], data["progress"]
                ...
            elif event_type == "complete":
                # Task done: data["final_answer"], data["execution_strategy"]
                ...
            elif event_type == "error":
                # Task failed: data["error"]
                ...

        return result
    """
    # ==========================================================================
    # YOUR CODE HERE
    # ==========================================================================

    print("=" * 70)
    print("LONG-RUNNING AGENT TASK CLIENT (STREAMING MODE)")
    print("=" * 70)
    print(f"\nQuery: {query}")
    print("-" * 70)

    # Step 1: Submit the task
    print("\n[1] Submitting task...")
    task_id = submit_task(query)
    print(f"    Task ID: {task_id}")

    # Step 2: Connect to SSE stream
    print("\n[2] Connecting to SSE stream...")

    # TODO: Implement SSE streaming logic here
    # - Connect to /tasks/{task_id}/stream with stream=True
    # - Parse SSE events using iter_lines()
    # - Handle each event type (status, complete, error)

    # Placeholder - remove when implementing
    print("\n    ERROR: SSE streaming not implemented yet!")
    print("    This is your task - implement the run_with_streaming() function")
    print("\n    Falling back to polling mode...\n")
    return run_with_polling(query)

    # ==========================================================================
    # END YOUR CODE
    # ==========================================================================


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Client for long-running agent tasks"
    )
    parser.add_argument(
        "query",
        help="The query to process"
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Use SSE streaming instead of polling"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Poll interval in seconds for polling mode (default: 1.0)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Timeout in seconds (default: 300)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    global API_BASE_URL
    API_BASE_URL = args.url

    if args.stream:
        run_with_streaming(query=args.query, timeout=args.timeout)
    else:
        run_with_polling(
            query=args.query,
            poll_interval=args.interval,
            timeout=args.timeout
        )


if __name__ == "__main__":
    main()
