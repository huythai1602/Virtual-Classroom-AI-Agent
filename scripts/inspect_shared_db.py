import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.db import get_shared_connection

def inspect_quiz_questions():
    print("Connecting to shared database...", flush=True)
    try:
        with get_shared_connection() as conn:
            if conn is None:
                print("Could not connect to shared database.", flush=True)
                return

            with conn.cursor() as cur:
                print("Inspecting quiz_questions table...", flush=True)
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'quiz_questions'
                """)
                columns = cur.fetchall()
                print("Columns in quiz_questions:", flush=True)
                for col in columns:
                    print(f"- {col[0]} ({col[1]})", flush=True)
                
                print("\nSample data (first row):", flush=True)
                cur.execute("SELECT * FROM quiz_questions LIMIT 1")
                row = cur.fetchone()
                print(row, flush=True)

    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    inspect_quiz_questions()
