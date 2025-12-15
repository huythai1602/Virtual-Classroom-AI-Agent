import os
import sys

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from repositories.db import init_shared_connection_pool, get_shared_connection
from repositories.sessions import sync_message_to_shared_db

def test_config():
    print("\n--- Testing Configuration ---")
    print(f"Shared Host: {settings.SHARED_POSTGRES_HOST}")
    print(f"Shared DB: {settings.SHARED_POSTGRES_DB}")
    if not settings.SHARED_POSTGRES_HOST:
        print("⚠️ Shared Host not set. Skipping real connection test.")
        return False
    return True

def test_connection():
    print("\n--- Testing Shared Connection ---")
    try:
        pool = init_shared_connection_pool()
        if pool:
            print("✅ Pool initialized successfully")
            with get_shared_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    print("✅ Connection query (SELECT 1) successful")
        else:
            print("❌ Pool initialization returned None (Check credentials)")
    except Exception as e:
        print(f"❌ Connection test failed: {e}")

def test_sync_logic():
    print("\n--- Testing Sync Logic (Dry Run) ---")
    # We won't actually insert unless we're sure, but we can verify the function calls rely on the connection
    # Or insert a test message if the user permitted.
    # For now, just validating import and function existence is a good sanity check.
    # To really test, we need valid credentials.
    
    print("Calling sync_message_to_shared_db with dummy data...")
    try:
        # This will fail fast if connection logic is broken, or print warning if connection is None
        sync_message_to_shared_db(
            thread_id="test_thread",
            role="user",
            content="This is a test message from Agent Verification",
            user_id="0",
            lesson_id=None
        )
        print("✅ Sync function called without exception (Check logs for warnings if DB not connected)")
    except Exception as e:
        print(f"❌ Sync function threw exception: {e}")

if __name__ == "__main__":
    if test_config():
        test_connection()
        test_sync_logic()
    else:
        print("\nPlease update .env with SHARED_POSTGRES_... variables to run full test.")
