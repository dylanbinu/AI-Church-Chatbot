"""Simple live smoke test against a running local server."""
from __future__ import annotations

import sys
import time

import requests

BASE_URL = "http://127.0.0.1:8004"


def wait_for_server(timeout: int = 30) -> None:
    for _ in range(timeout):
        try:
            resp = requests.get(f"{BASE_URL}/health", timeout=2)
            if resp.status_code in (200, 503):
                print("Server is up:", resp.status_code, resp.json())
                return
        except requests.RequestException:
            time.sleep(1)
    print("Server failed to start in time.")
    sys.exit(1)


def main() -> None:
    wait_for_server()
    payload = {
        "message": "When are service times?",
        "history": [],
        "church_id": "heritage",
    }
    resp = requests.post(f"{BASE_URL}/chat", json=payload, timeout=60)
    print("status", resp.status_code)
    print(resp.text)
    if resp.status_code != 200:
        sys.exit(1)
    data = resp.json()
    if "*" not in data.get("response", "") and "](" not in data.get("response", ""):
        print("[WARN] Response missing expected markdown formatting")
    print("[PASS] chat endpoint responded")


if __name__ == "__main__":
    main()
