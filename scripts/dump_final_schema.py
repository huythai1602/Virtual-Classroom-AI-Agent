import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.db import get_shared_connection

def dump_final_schema():
    output_file = "schema_final_dump.txt"
    try:
        with get_shared_connection() as conn:
            if conn is None:
                with open(output_file, "w") as f:
                    f.write("Could not connect to shared database.")
                return

            with conn.cursor() as cur:
                with open(output_file, "w") as f:
                    for table in ['quizzes', 'lessons']:
                        f.write(f"Columns in {table}:\n")
                        cur.execute(f"""
                            SELECT column_name, data_type 
                            FROM information_schema.columns 
                            WHERE table_name = '{table}'
                        """)
                        columns = cur.fetchall()
                        for col in columns:
                            f.write(f"- {col[0]} ({col[1]})\n")
                        f.write("\n")

    except Exception as e:
        with open(output_file, "w") as f:
            f.write(f"Error: {e}")

if __name__ == "__main__":
    dump_final_schema()
