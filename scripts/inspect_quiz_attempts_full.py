import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.db import get_shared_connection

def inspect():
    with open("quiz_attempts_schema.txt", "w", encoding="utf-8") as f:
        try:
            with get_shared_connection() as conn:
                if not conn:
                    f.write("No connection to shared DB\n")
                    return
                
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'quiz_attempts'
                        ORDER BY ordinal_position
                    """)
                    columns = cur.fetchall()
                    f.write("Columns in quiz_attempts:\n")
                    for col in columns:
                        col_name, data_type = col
                        f.write(f"- {col_name}: {data_type}\n")
                        
                    # Also check quiz_answers for context
                    # ...
                        
        except Exception as e:
             f.write(f"Error: {e}\n")

if __name__ == "__main__":
    inspect()
