import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.db import get_shared_connection

def inspect_full():
    with open("schema_full.txt", "w", encoding="utf-8") as f:
        try:
            with get_shared_connection() as conn:
                if not conn:
                    return
                
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT table_name, column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public'
                        ORDER BY table_name, ordinal_position
                    """)
                    rows = cur.fetchall()
                    
                    current_table = ""
                    for row in rows:
                        table, col, dtype = row
                        if table != current_table:
                            f.write(f"\nTable: {table}\n")
                            current_table = table
                        f.write(f"  - {col}: {dtype}\n")
                        
        except Exception as e:
            f.write(f"Error: {e}\n")

if __name__ == "__main__":
    inspect_full()
