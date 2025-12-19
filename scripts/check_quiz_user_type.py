import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.db import get_shared_connection

def check_schema():
    print("Checking schema for quiz_attempts table...")
    try:
        with get_shared_connection() as conn:
            if not conn:
                print("Could not connect to shared DB")
                return
            
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'quiz_attempts'
                """)
                columns = cur.fetchall()
                print("\nColumns in quiz_attempts:")
                for col in columns:
                    print(f"- {col[0]}: {col[1]}")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()
