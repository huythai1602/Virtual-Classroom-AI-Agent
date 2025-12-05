"""
Migration script: Transcript TXT files → PostgreSQL + pgvector
Refactored to use services.ingestion.IngestionService for robust processing.
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ingestion import IngestionService
from repositories.db import test_connection
from dotenv import load_dotenv

load_dotenv()

def migrate(force: bool = False):
    print("=" * 70)
    print("🚀 Starting TXT Files → PostgreSQL Migration (Refactored)")
    if force:
        print("⚠️  FORCE MODE: Will re-index all lessons")
    print("=" * 70)
    
    transcripts_dir = Path(__file__).parent.parent / "data/transcripts"
    
    service = IngestionService()
    results = service.process_directory(str(transcripts_dir), force=force)
    
    print("\n" + "=" * 70)
    print("✨ Migration completed!")
    print(f"   ✅ Success: {results['success']}")
    print(f"   ⏭️  Skipped: {results['skipped']}")
    print(f"   ❌ Errors:  {results['error']}")
    print(f"   📦 Total chunks: {results['total_chunks']}")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate transcript files to PostgreSQL")
    parser.add_argument("--force", action="store_true", help="Force re-index all lessons")
    args = parser.parse_args()
    
    if not test_connection():
        print("❌ Database connection failed.")
        sys.exit(1)
        
    migrate(force=args.force)
