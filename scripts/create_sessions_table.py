"""
Create sessions table for persistent conversation history
Run this to add sessions storage to PostgreSQL
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from repositories.db import get_connection


def create_sessions_table():
    """Create sessions table for conversation persistence"""
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        print("📋 Creating sessions table...")
        
        # Create sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                thread_id VARCHAR(255) UNIQUE NOT NULL,
                user_id VARCHAR(255) NOT NULL,
                messages JSONB DEFAULT '[]',
                context TEXT DEFAULT '',
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ Created sessions table")
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_thread_id 
            ON sessions(thread_id);
        """)
        print("✅ Created index on thread_id")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id 
            ON sessions(user_id);
        """)
        print("✅ Created index on user_id")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_last_activity 
            ON sessions(last_activity DESC);
        """)
        print("✅ Created index on last_activity")
        
        # Create function to auto-update updated_at
        cursor.execute("""
            CREATE OR REPLACE FUNCTION update_sessions_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        cursor.execute("""
            DROP TRIGGER IF EXISTS sessions_updated_at_trigger ON sessions;
        """)
        
        cursor.execute("""
            CREATE TRIGGER sessions_updated_at_trigger
            BEFORE UPDATE ON sessions
            FOR EACH ROW
            EXECUTE FUNCTION update_sessions_updated_at();
        """)
        print("✅ Created auto-update trigger")
        
        conn.commit()
        cursor.close()
        
        print("\n🎉 Sessions table created successfully!")
        print("📊 Table structure:")
        print("   - thread_id: Unique session identifier")
        print("   - user_id: User identifier")
        print("   - messages: JSONB array of conversation messages")
        print("   - context: Last retrieved context")
        print("   - metadata: Additional session metadata")
        print("   - timestamps: created_at, updated_at, last_activity")


if __name__ == "__main__":
    create_sessions_table()
