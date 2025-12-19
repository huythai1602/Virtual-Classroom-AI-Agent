import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.db import get_shared_connection

def check_users():
    print("Checking users table...")
    try:
        with get_shared_connection() as conn:
            if not conn:
                print("Could not connect")
                return
            
            with conn.cursor() as cur:
                # Check columns
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'users'
                """)
                columns = cur.fetchall()
                print("\nColumns in users:")
                for col in columns:
                    print(f"- {col[0]}: {col[1]}")
                
                # Check sample data
                cur.execute("SELECT * FROM users LIMIT 1")
                row = cur.fetchone()
                print(f"\nSample data: {row}")
                
                # Check if we can find 'huythai'
                cur.execute("SELECT id FROM users WHERE username = 'huythai'")
                user = cur.fetchone()
                print(f"\nUser 'huythai' ID: {user}")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_users()
