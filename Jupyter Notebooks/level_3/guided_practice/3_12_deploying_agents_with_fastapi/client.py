"""
Simple client to call the chatbot API.

Usage: python client.py "Hello, my name is Alice"
       python client.py "What's my name?" --user alice
"""

import argparse
import requests

API_URL = "http://localhost:8000/chat"

def main():
    parser = argparse.ArgumentParser(description="Chat with the bot")
    parser.add_argument("message", help="Message to send")
    parser.add_argument("--user", default="default", help="User ID for conversation")
    args = parser.parse_args()

    response = requests.post(API_URL, json={
        "message": args.message,
        "user_id": args.user
    })

    if response.ok:
        data = response.json()
        print(f"[{data['user_id']}] {data['response']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")


if __name__ == "__main__":
    main()
