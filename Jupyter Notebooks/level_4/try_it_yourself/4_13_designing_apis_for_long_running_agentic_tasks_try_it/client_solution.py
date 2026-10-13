"""
Client for Long-Running Agent Tasks - SOLUTION

This is the complete solution with SSE streaming implemented.

Usage:
    python client_solution.py "Your query" --stream     # Use SSE streaming
    python client_solution.py "Your query"              # Use polling
"""

import argparse
import json
import time
import sys

import requests


API_BASE_URL = "http://localhost:8000"


# -----------------------------------------------------------------------------
# SSE Event Parser
# -----------------------------------------------------------------------------

def parse_sse_events(response):
    """
    Parse Server-Sent Events from a streaming response.

    SSE format:
        event: <event_type>
        data: <payload>
        <blank line>

    Yields:
        dict with 'event' and 'data' keys
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
# Task Submission (shared by both modes)
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


# -----------------------------------------------------------------------------
# Polling Implementation
# -----------------------------------------------------------------------------

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
    """Submit a task and poll until completion."""
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
# SSE Streaming Implementation - SOLUTION
# -----------------------------------------------------------------------------

def run_with_streaming(query: str, timeout: float = 300.0) -> dict:
    """
    Submit a task and receive real-time updates via SSE streaming.

    This is the complete solution demonstrating:
    1. Submitting a task to the server
    2. Connecting to the SSE streaming endpoint
    3. Processing real-time events as they arrive
    4. Handling different event types (status, complete, error, heartbeat)
    """
    print("=" * 70)
    print("LONG-RUNNING AGENT TASK CLIENT (STREAMING MODE)")
    print("=" * 70)
    print(f"\nQuery: {query}")
    print(f"Timeout: {timeout}s")
    print("-" * 70)

    # Step 1: Submit the task
    print("\n[1] Submitting task...")
    task_id = submit_task(query)
    print(f"    Task ID: {task_id}")

    # Step 2: Connect to SSE stream
    print("\n[2] Connecting to SSE stream...")
    start_time = time.time()
    result = None

    try:
        # Open streaming connection
        # Note: stream=True keeps the connection open for SSE
        response = requests.get(
            f"{API_BASE_URL}/tasks/{task_id}/stream",
            stream=True,
            timeout=timeout
        )

        if not response.ok:
            print(f"    Error connecting to stream: {response.status_code}")
            print(response.text)
            sys.exit(1)

        print("    Connected! Receiving events...\n")

        # Step 3: Process events as they arrive using our SSE parser
        for event in parse_sse_events(response):
            elapsed = time.time() - start_time

            # Parse event data
            try:
                data = json.loads(event["data"])
            except json.JSONDecodeError:
                print(f"    [{elapsed:5.1f}s] [warning] Could not parse event data: {event['data']}")
                continue

            # Handle different event types
            event_type = event["event"]

            if event_type == "status":
                status = data.get("status", "unknown")
                progress = data.get("progress", "-")
                strategy = data.get("execution_strategy")
                strategy_str = f" [{strategy}]" if strategy else ""
                print(f"    [{elapsed:5.1f}s] [status]{strategy_str} {status} | {progress}")

            elif event_type == "complete":
                print(f"    [{elapsed:5.1f}s] [complete] Task finished!")
                result = {
                    "task_id": task_id,
                    "query": data.get("query", query),
                    "execution_strategy": data.get("execution_strategy", "unknown"),
                    "final_answer": data.get("final_answer", "")
                }
                break

            elif event_type == "error":
                error = data.get("error", "Unknown error")
                print(f"    [{elapsed:5.1f}s] [error] Task failed: {error}")
                sys.exit(1)

            elif event_type == "heartbeat":
                # Heartbeat events keep the connection alive
                # We can silently ignore them or show a subtle indicator
                pass

            else:
                # Unknown event type
                print(f"    [{elapsed:5.1f}s] [unknown:{event_type}] {event['data']}")

    except requests.exceptions.Timeout:
        print(f"\n    TIMEOUT after {timeout}s")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"\n    Connection error: {e}")
        sys.exit(1)

    # Step 4: Display result
    if result:
        elapsed = time.time() - start_time
        print(f"\n    Task completed in {elapsed:.1f}s")

        print("\n" + "=" * 70)
        print("RESULT (received via SSE stream)")
        print("=" * 70)
        print(f"\nExecution Strategy: {result['execution_strategy']}")
        print(f"\nFinal Answer:\n{result['final_answer']}")
        print("\n" + "=" * 70)

        return result
    else:
        print("\n    No result received")
        sys.exit(1)


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Client for long-running agent tasks (with SSE streaming)"
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
