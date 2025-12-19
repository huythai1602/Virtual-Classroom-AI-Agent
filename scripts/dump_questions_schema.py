import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.db import get_shared_connection

def dump_questions_schema():
    output_file = "quiz_questions_dump.txt"
    try:
        with get_shared_connection() as conn:
            if conn is None:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write("Could not connect to shared database.")
                return

            with conn.cursor() as cur:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(f"Columns in quiz_questions:\n")
                    cur.execute(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'quiz_questions'
                    """)
                    columns = cur.fetchall()
                    for col in columns:
                        f.write(f"- {col[0]} ({col[1]})\n")
                    
                    f.write("\nSample data (first row):\n")
                    cur.execute("SELECT * FROM quiz_questions LIMIT 1")
                    row = cur.fetchone()
                    f.write(str(row))

    except Exception as e:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"Error: {e}")

if __name__ == "__main__":
    dump_questions_schema()
