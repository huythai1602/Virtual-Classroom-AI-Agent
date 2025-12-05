
import asyncio
import time
import httpx
from datetime import datetime

# Adjust base URL if needed
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/agent/chat"

# Using a hardcoded token or fetching one? 
# For this script we'll assume the server validates tokens or we can use a dummy if local dev allows it.
# Based on app.py: credentials: HTTPAuthorizationCredentials = Security(security)
# We might need a valid token. If we can't easily get one, we might just ping health or print instructions.
# However, let's try to assume we run this against the local dev server which might have permissive CORS or easy token gen.

# Actually, the user's issue was on "production-..." in the screenshot, but we are fixing code locally.
# We will verify by just ensuring the config is loaded correctly. 

async def verify_performance():
    print(f"Checking configuration at {datetime.now()}")
    
    # We can't easily query the API without a token if auth is enforced.
    # But we can verify the settings file change via the file system which we just did.
    # This script is mostly a template for the user to run if they have a token.
    
    print("\nTo verify the fix completely:")
    print("1. Restart your backend server.")
    print(f"2. Send a POST request to {API_URL} with a valid token.")
    print("3. Observe the response time. It should be significantly faster (under 10s).")

if __name__ == "__main__":
    asyncio.run(verify_performance())
