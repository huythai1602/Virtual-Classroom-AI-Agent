import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.db import get_shared_connection

def inspect():
    with open("users_info.txt", "w", encoding="utf-8") as f:
        try:
            with get_shared_connection() as conn:
                if not conn:
                    f.write("No connection to shared DB\n")
                    return
                
                with conn.cursor() as cur:
                    # 1. Get Columns
                    cur.execute("""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'users'
                        ORDER BY ordinal_position
                    """)
                    columns = cur.fetchall()
                    f.write("Columns:\n")
                    col_names = []
                    for col in columns:
                        f.write(f"- {col[0]} ({col[1]})\n")
                        col_names.append(col[0])
                    
                    # 2. Check for username 'huythai'
                    if 'username' in col_names:
                        cur.execute("SELECT id, username FROM users WHERE username = 'huythai'")
                        row = cur.fetchone()
                        f.write(f"\nSearch 'huythai' by username: {row}\n")
                    else:
                        f.write("\nNo 'username' column found.\n")
                        
                    # 3. Sample Data
                    cur.execute("SELECT * FROM users LIMIT 1")
                    row = cur.fetchone()
                    f.write(f"\nSample Row: {row}\n")

        except Exception as e:
            f.write(f"Error: {e}\n")

if __name__ == "__main__":
    inspect()
