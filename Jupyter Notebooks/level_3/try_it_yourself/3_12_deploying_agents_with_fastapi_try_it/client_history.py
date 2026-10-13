"""
Simple client to retrieve conversation history from the chatbot API.

Usage: python client_history.py alice
       python client_history.py --user default
"""

import argparse
import requests

API_URL = "http://localhost:8000/history"

def main():
    parser = argparse.ArgumentParser(description="Get conversation history")
    parser.add_argument("user_id", nargs="?", default="default", help="User ID to retrieve history for")
    args = parser.parse_args()

    response = requests.get(f"{API_URL}/{args.user_id}")

    if response.ok:
        data = response.json()
        print(f"Conversation history for user: {data['user_id']}")
        print("-" * 50)

        if not data["messages"]:
            print("No conversation history found.")
        else:
            for msg in data["messages"]:
                role = "User" if msg["role"] == "human" else "Bot"
                print(f"[{role}]: {msg['content']}")
                print()
    else:
        print(f"Error: {response.status_code} - {response.text}")


if __name__ == "__main__":
    main()
