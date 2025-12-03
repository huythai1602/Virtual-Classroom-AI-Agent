"""Reset database - Drop and recreate tables"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_connection import get_db_connection

def reset_database():
    """Drop and recreate all tables with correct schema"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        print("🗑️  Dropping existing tables...")
        cursor.execute("DROP TABLE IF EXISTS chunks CASCADE")
        cursor.execute("DROP TABLE IF EXISTS lessons CASCADE")
        print("✅ Tables dropped")
        
        print("\n📋 Creating tables with correct schema...")
        
        # Create lessons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id SERIAL PRIMARY KEY,
                lesson_id VARCHAR(50) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                subject VARCHAR(50) NOT NULL,
                grade INTEGER NOT NULL,
                transcript TEXT NOT NULL,
                summary TEXT,
                total_chunks INTEGER DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                metadata JSONB
            )
        """)
        print("✅ Created lessons table")
        
        # Create chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id SERIAL PRIMARY KEY,
                lesson_id VARCHAR(50) NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedding VECTOR(1536),
                created_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT fk_lesson 
                    FOREIGN KEY (lesson_id) 
                    REFERENCES lessons(lesson_id) 
                    ON DELETE CASCADE,
                UNIQUE(lesson_id, chunk_index)
            )
        """)
        print("✅ Created chunks table")
        
        # Create indexes
        print("\n📊 Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lessons_lesson_id ON lessons(lesson_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lessons_subject_grade ON lessons(subject, grade)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lessons_status ON lessons(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_lesson_id ON chunks(lesson_id)")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks 
            USING ivfflat (embedding vector_cosine_ops) 
            WITH (lists = 100)
        """)
        print("✅ Indexes created")
        
        conn.commit()
        cursor.close()
        
        print("\n✅ Database reset complete!")

if __name__ == "__main__":
    reset_database()
