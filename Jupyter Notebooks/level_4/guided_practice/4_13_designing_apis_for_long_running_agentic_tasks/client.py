"""
Polling Client for Long-Running Agent Tasks

This client demonstrates the polling pattern for long-running tasks:
1. Submit a task via POST /tasks
2. Poll GET /tasks/{task_id} at regular intervals
3. Display progress updates as they arrive
4. Retrieve final result when status is 'completed'

Usage:
    python client.py "What AI products were launched by the company that acquired DeepMind in 2024?"
    python client.py "Summarize Tesla's Q4 2024 earnings and leadership changes" --interval 2
    python client.py "Your query here" --timeout 300
"""

import argparse
import time
import sys

import requests


API_BASE_URL = "http://localhost:8000"


def submit_task(query: str) -> str:
    """
    Submit a new task to the server.

    Args:
        query: The query to process

    Returns:
        task_id: Unique identifier for the submitted task
    """
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
    """
    Poll the status of a task.

    Args:
        task_id: The task identifier

    Returns:
        Status response dictionary
    """
    response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")

    if not response.ok:
        print(f"Error polling status: {response.status_code}")
        print(response.text)
        sys.exit(1)

    return response.json()


def get_result(task_id: str) -> dict:
    """
    Get the final result of a completed task.

    Args:
        task_id: The task identifier

    Returns:
        Result response dictionary
    """
    response = requests.get(f"{API_BASE_URL}/tasks/{task_id}/result")

    if not response.ok:
        print(f"Error getting result: {response.status_code}")
        print(response.text)
        sys.exit(1)

    return response.json()


def run_with_polling(
    query: str,
    poll_interval: float = 1.0,
    timeout: float = 300.0
) -> dict:
    """
    Submit a task and poll until completion.

    Args:
        query: The query to process
        poll_interval: Seconds between status polls (default: 1.0)
        timeout: Maximum seconds to wait (default: 300)

    Returns:
        Final result dictionary
    """
    print("=" * 70)
    print("LONG-RUNNING AGENT TASK CLIENT")
    print("=" * 70)
    print(f"\nQuery: {query}")
    print(f"Poll interval: {poll_interval}s | Timeout: {timeout}s")
    print("-" * 70)

    # Step 1: Submit the task
    print("\n[1] Submitting task...")
    task_id = submit_task(query)
    print(f"    Task ID: {task_id}")

    # Step 2: Poll for status
    print("\n[2] Polling for status...")
    start_time = time.time()
    last_progress = None

    while True:
        elapsed = time.time() - start_time

        # Check timeout
        if elapsed > timeout:
            print(f"\n    TIMEOUT after {timeout}s")
            sys.exit(1)

        # Poll status
        status_data = poll_status(task_id)
        status = status_data["status"]
        progress = status_data.get("progress")
        strategy = status_data.get("execution_strategy")

        # Print progress updates (only when changed)
        if progress != last_progress:
            strategy_str = f" [{strategy}]" if strategy else ""
            print(f"    [{elapsed:5.1f}s] Status: {status}{strategy_str} | Progress: {progress or '-'}")
            last_progress = progress

        # Check if completed or failed
        if status == "completed":
            print(f"\n    Task completed in {elapsed:.1f}s")
            break
        elif status == "failed":
            error = status_data.get("error", "Unknown error")
            print(f"\n    Task FAILED: {error}")
            sys.exit(1)

        # Wait before next poll
        time.sleep(poll_interval)

    # Step 3: Get the result
    print("\n[3] Retrieving result...")
    result = get_result(task_id)

    # Display result
    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"\nExecution Strategy: {result['execution_strategy']}")
    print(f"\nFinal Answer:\n{result['final_answer']}")
    print("\n" + "=" * 70)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Client for long-running agent tasks with polling"
    )
    parser.add_argument(
        "query",
        help="The query to process"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Poll interval in seconds (default: 1.0)"
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

    run_with_polling(
        query=args.query,
        poll_interval=args.interval,
        timeout=args.timeout
    )


if __name__ == "__main__":
    main()
