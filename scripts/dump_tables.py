import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.db import get_shared_connection

def dump_tables():
    output_file = "tables_dump.txt"
    try:
        with get_shared_connection() as conn:
            if conn is None:
                with open(output_file, "w") as f:
                    f.write("Could not connect to shared database.")
                return

            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                tables = cur.fetchall()
                
                with open(output_file, "w") as f:
                    f.write("Tables in public schema:\n")
                    for table in tables:
                        f.write(f"- {table[0]}\n")
                        
                    # Also check for 'quiz_attempts' specifically or similar
                    f.write("\nChecking for potential attempt tables:\n")
                    for table in tables:
                        if 'attempt' in table[0].lower():
                             # Get columns for attempt table
                             cur.execute(f"""
                                SELECT column_name, data_type 
                                FROM information_schema.columns 
                                WHERE table_name = '{table[0]}'
                            """)
                             cols = cur.fetchall()
                             f.write(f"\nColumns in {table[0]}:\n")
                             for c in cols:
                                 f.write(f"  - {c[0]} ({c[1]})\n")

    except Exception as e:
        with open(output_file, "w") as f:
            f.write(f"Error: {e}")

if __name__ == "__main__":
    dump_tables()
