"""
Database schema update for rich chunk metadata
Run this to add metadata columns
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_connection import get_db_connection


def update_schema():
    """Add metadata columns to chunks table"""
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        print("📋 Updating database schema...")
        
        # Add JSONB metadata column if not exists
        cursor.execute("""
            ALTER TABLE chunks 
            ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
        """)
        print("✅ Added metadata column")
        
        # Add context columns
        cursor.execute("""
            ALTER TABLE chunks 
            ADD COLUMN IF NOT EXISTS context_before TEXT DEFAULT '';
        """)
        print("✅ Added context_before column")
        
        cursor.execute("""
            ALTER TABLE chunks 
            ADD COLUMN IF NOT EXISTS context_after TEXT DEFAULT '';
        """)
        print("✅ Added context_after column")
        
        # Create index on metadata for fast filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_metadata 
            ON chunks USING gin(metadata);
        """)
        print("✅ Created GIN index on metadata")
        
        conn.commit()
        cursor.close()
        
        print("\n✅ Schema update complete!")
        print("\n📝 New columns:")
        print("   - metadata (JSONB): section, position, char_count, etc.")
        print("   - context_before (TEXT): Previous chunk context")
        print("   - context_after (TEXT): Next chunk context")


if __name__ == "__main__":
    update_schema()
