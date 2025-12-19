import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.db import get_shared_connection

def check_enum():
    print("Checking enum values...")
    try:
        with get_shared_connection() as conn:
            if not conn:
                print("No connection")
                return
            
            with conn.cursor() as cur:
                # Option 1: Try to query distinct values if table has data
                # cur.execute("SELECT DISTINCT role FROM lesson_chat_messages")
                
                # Option 2: Introspect pg_enum (safer if table empty)
                query = """
                    SELECT e.enumlabel
                    FROM pg_type t 
                    JOIN pg_enum e ON t.oid = e.enumtypid  
                    JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = 'lesson_chat_messages_role_enum'
                """
                cur.execute(query)
                rows = cur.fetchall()
                print(f"Enum values found: {[r[0] for r in rows]}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_enum()
