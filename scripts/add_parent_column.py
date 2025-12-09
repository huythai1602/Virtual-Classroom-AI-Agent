import psycopg2
from psycopg2 import sql
from config.settings import settings

def migrate():
    conn = psycopg2.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD
    )
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='chunks' AND column_name='parent_content';
        """)
        if cursor.fetchone():
            print("✅ Column 'parent_content' already exists.")
        else:
            print("🔄 Adding column 'parent_content' to table 'chunks'...")
            cursor.execute("ALTER TABLE chunks ADD COLUMN parent_content TEXT;")
            print("✅ Column added successfully.")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    migrate()
