import requests
import json
import time
import sys

BASE_URL = "http://localhost:8004"

print("--- WAITING FOR SERVER STARTUP (up to 30s) ---")
for i in range(30):
    try:
        resp = requests.get(BASE_URL)
        if resp.status_code == 200:
            print("Server is UP!")
            break
    except:
        time.sleep(1)
        print(".", end="", flush=True)
else:
    print("\nServer failed to start in time.")
    sys.exit(1)

print("\n\n--- TESTING SPECIFIC REGRESSION: SERVICE TIMES ---")
payload = {
    "message": "When are service times?",
    "history": [],
    "use_full_context": False
}

try:
    start = time.time()
    resp = requests.post(f"{BASE_URL}/chat", json=payload)
    duration = time.time() - start
    
    if resp.status_code == 200:
        data = resp.json()
        content = data["response"]
        print(f"\nResponse ({duration:.2f}s):")
        print("-" * 40)
        print(content)
        print("-" * 40)
        
        # VERIFICATION CHECKS
        # 1. Check for Bullet Points
        if "*" not in content:
            print("[FAIL] Formatting lost: No bullet points found.")
            sys.exit(1)
            
        # 2. Check for Links
        if "](" not in content:
            print("[FAIL] Links lost: No markdown links found.")
            sys.exit(1)
            
        print("[PASS] Formatting passed checks.")
    else:
        print(f"[FAIL] Error {resp.status_code}: {resp.text}")
        sys.exit(1)

except Exception as e:
    print(f"[FAIL] Exception: {e}")
    sys.exit(1)
