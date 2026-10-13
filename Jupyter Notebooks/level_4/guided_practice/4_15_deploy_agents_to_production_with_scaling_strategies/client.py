"""
Demo Client for Multi-User Agent API

This script demonstrates:
1. Multi-user task submission (isolated per user)
2. Conversation history management
3. Polling for task completion
4. User isolation verification

Run the API first:
    docker-compose up --build

Then run this client:
    python client.py
"""

import time
import requests

BASE_URL = "http://localhost:8000"


def submit_task(user_id: str, query: str, conversation_id: str = None) -> dict:
    """Submit a task for a specific user."""
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={"query": query, "conversation_id": conversation_id},
        headers={"X-User-ID": user_id}
    )
    response.raise_for_status()
    return response.json()


def poll_task(user_id: str, task_id: str, max_wait: int = 120) -> dict:
    """Poll for task completion."""
    print(f"  Polling task {task_id[:8]}...", end="", flush=True)

    for _ in range(max_wait // 2):
        response = requests.get(
            f"{BASE_URL}/tasks/{task_id}",
            headers={"X-User-ID": user_id}
        )
        response.raise_for_status()
        status = response.json()

        if status["status"] == "completed":
            print(" done!")
            return status
        elif status["status"] == "failed":
            print(" failed!")
            return status

        print(".", end="", flush=True)
        time.sleep(2)

    print(" timeout!")
    return {"status": "timeout"}


def get_task_result(user_id: str, task_id: str) -> dict:
    """Get the result of a completed task."""
    response = requests.get(
        f"{BASE_URL}/tasks/{task_id}/result",
        headers={"X-User-ID": user_id}
    )
    response.raise_for_status()
    return response.json()


def list_user_tasks(user_id: str) -> list:
    """List all tasks for a user."""
    response = requests.get(
        f"{BASE_URL}/tasks",
        headers={"X-User-ID": user_id}
    )
    response.raise_for_status()
    return response.json()


def list_conversations(user_id: str) -> list:
    """List all conversations for a user."""
    response = requests.get(
        f"{BASE_URL}/conversations",
        headers={"X-User-ID": user_id}
    )
    response.raise_for_status()
    return response.json()


def get_conversation(user_id: str, conversation_id: str) -> dict:
    """Get conversation messages."""
    response = requests.get(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers={"X-User-ID": user_id}
    )
    response.raise_for_status()
    return response.json()


def demo_multi_user():
    """Demonstrate multi-user task isolation."""
    print("\n" + "="*70)
    print("DEMO: Multi-User Task Isolation")
    print("="*70)

    # Two different users
    user_a = "alice-123"
    user_b = "bob-456"

    # User A submits a task
    print(f"\n[User A: {user_a}]")
    print("  Submitting: 'What are the latest developments in quantum computing?'")
    task_a = submit_task(
        user_a,
        "What are the latest developments in quantum computing?"
    )
    print(f"  Task ID: {task_a['task_id'][:8]}...")
    print(f"  Conversation ID: {task_a['conversation_id'][:8]}...")

    # User B submits a different task
    print(f"\n[User B: {user_b}]")
    print("  Submitting: 'Explain the latest AI regulations in Europe'")
    task_b = submit_task(
        user_b,
        "Explain the latest AI regulations in Europe"
    )
    print(f"  Task ID: {task_b['task_id'][:8]}...")
    print(f"  Conversation ID: {task_b['conversation_id'][:8]}...")

    # Poll both tasks
    print("\n[Waiting for tasks to complete...]")

    print(f"\n[User A]")
    status_a = poll_task(user_a, task_a["task_id"])

    print(f"\n[User B]")
    status_b = poll_task(user_b, task_b["task_id"])

    # Get results
    if status_a["status"] == "completed":
        print(f"\n[User A Result]")
        result_a = get_task_result(user_a, task_a["task_id"])
        print(f"  Strategy: {result_a.get('execution_strategy')}")
        print(f"  Answer: {result_a.get('final_answer', '')[:200]}...")

    if status_b["status"] == "completed":
        print(f"\n[User B Result]")
        result_b = get_task_result(user_b, task_b["task_id"])
        print(f"  Strategy: {result_b.get('execution_strategy')}")
        print(f"  Answer: {result_b.get('final_answer', '')[:200]}...")

    # Verify isolation: User A cannot see User B's tasks
    print("\n[Isolation Verification]")
    try:
        # This should fail - User A trying to access User B's task
        requests.get(
            f"{BASE_URL}/tasks/{task_b['task_id']}",
            headers={"X-User-ID": user_a}
        ).raise_for_status()
        print("  ERROR: User A could access User B's task!")
    except requests.exceptions.HTTPError:
        print("  OK: User A cannot access User B's task (as expected)")


def demo_conversation_history():
    """Demonstrate conversation history management."""
    print("\n" + "="*70)
    print("DEMO: Conversation History")
    print("="*70)

    user_id = "charlie-789"
    conversation_id = "conv-demo-123"

    # First message in conversation
    print(f"\n[User: {user_id}]")
    print(f"[Conversation: {conversation_id}]")

    print("\n  First query: 'Tell me about Tesla'")
    task_1 = submit_task(
        user_id,
        "Tell me about Tesla's recent electric vehicle announcements",
        conversation_id=conversation_id
    )

    print(f"  Task ID: {task_1['task_id'][:8]}...")
    status_1 = poll_task(user_id, task_1["task_id"])

    if status_1["status"] == "completed":
        result_1 = get_task_result(user_id, task_1["task_id"])
        print(f"\n  Answer 1: {result_1.get('final_answer', '')[:200]}...")

    # Second message - builds on context
    print("\n  Follow-up query: 'What about their energy business?'")
    task_2 = submit_task(
        user_id,
        "What about their energy business?",  # Relies on conversation context
        conversation_id=conversation_id
    )

    status_2 = poll_task(user_id, task_2["task_id"])

    if status_2["status"] == "completed":
        result_2 = get_task_result(user_id, task_2["task_id"])
        print(f"\n  Answer 2: {result_2.get('final_answer', '')[:200]}...")

    # Show conversation history
    print("\n[Conversation History]")
    conv = get_conversation(user_id, conversation_id)
    for i, msg in enumerate(conv["messages"], 1):
        role = msg["role"].upper()
        content = msg["content"][:80]
        print(f"  {i}. [{role}]: {content}...")


def demo_task_list():
    """Demonstrate task listing."""
    print("\n" + "="*70)
    print("DEMO: Task Listing")
    print("="*70)

    user_id = "alice-123"

    print(f"\n[User: {user_id}]")
    tasks = list_user_tasks(user_id)
    print(f"  Total tasks: {tasks['total']}")

    for task in tasks["tasks"][:5]:  # Show first 5
        status_icon = {
            "completed": "v",
            "failed": "x",
            "running": "~",
            "pending": "o"
        }.get(task["status"], "?")

        print(f"  [{status_icon}] {task['task_id'][:8]}... - {task['status']}")


def main():
    """Run all demos."""
    print("\n" + "="*70)
    print("Production Agent API - Multi-User Demo")
    print("="*70)

    # Check API is running
    try:
        response = requests.get(f"{BASE_URL}/")
        response.raise_for_status()
        print("\nAPI is running!")
        print(f"Features: {response.json().get('features', [])}")
    except requests.exceptions.ConnectionError:
        print("\nERROR: Cannot connect to API")
        print("Please start the API first:")
        print("  docker-compose up --build")
        print("  OR")
        print("  uvicorn main:app --reload")
        return

    # Run demos
    demo_multi_user()
    demo_conversation_history()
    demo_task_list()

    print("\n" + "="*70)
    print("Demo complete!")
    print("="*70)


if __name__ == "__main__":
    main()
