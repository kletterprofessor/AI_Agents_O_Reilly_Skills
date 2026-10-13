"""
Polling Client for Worker Node Architecture

This client demonstrates how to interact with the worker-based API:
1. Submit a task (queued to Redis, processed by Celery worker)
2. Poll for status until completion
3. Retrieve the final result

The client works the same as the BackgroundTasks version - the difference
is entirely on the server side (worker processes vs in-process execution).

Usage:
    python client.py "What AI products were launched by the company that acquired DeepMind in 2024?"
    python client.py "Summarize Tesla's Q4 2024 earnings" --interval 2
    python client.py --check-workers  # Check if workers are running
"""

import argparse
import time
import sys

import requests


API_BASE_URL = "http://localhost:8000"


def check_workers() -> bool:
    """
    Check if Celery workers are available.

    Returns True if workers are responsive, False otherwise.
    """
    print("Checking worker availability...")

    try:
        response = requests.get(f"{API_BASE_URL}/workers/health", timeout=10)

        if response.ok:
            data = response.json()
            if data["worker_available"]:
                print(f"  Workers are available: {data['message']}")
                return True
            else:
                print(f"  Workers NOT available: {data['message']}")
                return False
        else:
            print(f"  Error checking workers: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("  Cannot connect to API server. Is it running?")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def submit_task(query: str) -> dict:
    """
    Submit a new task to the server.

    Returns the full response including task_id and celery_task_id.
    """
    response = requests.post(
        f"{API_BASE_URL}/tasks",
        json={"query": query}
    )

    if not response.ok:
        print(f"Error submitting task: {response.status_code}")
        print(response.text)
        sys.exit(1)

    return response.json()


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


def run_with_polling(
    query: str,
    poll_interval: float = 1.0,
    timeout: float = 300.0
) -> dict:
    """
    Submit a task and poll until completion.

    Args:
        query: The query to process
        poll_interval: Seconds between status polls
        timeout: Maximum seconds to wait

    Returns:
        Final result dictionary
    """
    print("=" * 70)
    print("WORKER NODE ARCHITECTURE CLIENT")
    print("=" * 70)
    print(f"\nQuery: {query}")
    print(f"Poll interval: {poll_interval}s | Timeout: {timeout}s")
    print("-" * 70)

    # Check if workers are available first
    print("\n[0] Checking worker availability...")
    if not check_workers():
        print("\n    WARNING: Workers may not be running!")
        print("    Start workers with: celery -A tasks worker --loglevel=info")
        print("    Continuing anyway...\n")

    # Step 1: Submit the task
    print("\n[1] Submitting task to queue...")
    submit_response = submit_task(query)
    task_id = submit_response["task_id"]
    celery_id = submit_response["celery_task_id"]
    print(f"    Task ID: {task_id}")
    print(f"    Celery Task ID: {celery_id}")
    print(f"    Status: {submit_response['status']}")

    # Step 2: Poll for status
    print("\n[2] Polling for status (task processing on worker)...")
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
    print("\n[3] Retrieving result from worker...")
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
        description="Client for worker node architecture API"
    )
    parser.add_argument(
        "query",
        nargs="?",
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
    parser.add_argument(
        "--check-workers",
        action="store_true",
        help="Only check if workers are available, then exit"
    )

    args = parser.parse_args()

    global API_BASE_URL
    API_BASE_URL = args.url

    if args.check_workers:
        success = check_workers()
        sys.exit(0 if success else 1)

    if not args.query:
        parser.error("query is required unless using --check-workers")

    run_with_polling(
        query=args.query,
        poll_interval=args.interval,
        timeout=args.timeout
    )


if __name__ == "__main__":
    main()
