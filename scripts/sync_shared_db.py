"""
Sync Shared DB to Local Vector DB
ETL Pipeline: Extract from Supabase -> Transform (Extract Grade) -> Load to pgvector
"""
import sys
import argparse
import re
import hashlib
from pathlib import Path
try:
    from slugify import slugify
except ImportError:
    slugify = None

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ingestion import IngestionService
from repositories.shared import fetch_full_lessons_from_shared
from repositories.db import test_connection

def simple_slugify(text: str) -> str:
    """Simple slugify if library not available"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')

def extract_grade(course_title: str) -> int:
    """
    Extract grade from course title.
    Examples: "Math 4" -> 4, "History 12" -> 12
    """
    match = re.search(r'(\d+)', course_title)
    if match:
        return int(match.group(1))
    return 0

def sync(dry_run: bool = False, force: bool = False):
    print("=" * 70)
    print("🚀 Starting Shared DB → Local DB Sync")
    if dry_run:
        print("🧪 MODE: DRY RUN (No modifications)")
    if force:
        print("⚠️  MODE: FORCE (Re-index all)")
    print("=" * 70)

    service = IngestionService()
    count = 0
    
    for row in fetch_full_lessons_from_shared():
        count += 1
        lesson_db_id = row['lesson_db_id']
        course_title = row['course_title']
        subject = row['subject'] # Dictionary key from query
        # Warning: 'subject' might be mapped from category.
        
        # Transform
        grade = extract_grade(course_title)
        
        # Generate stable ID
        # Format: {subject}-{grade}-{db_id} e.g. "math-4-102"
        # Using simple slugify for consistency
        if slugify:
             slug_subject = slugify(subject)
        else:
             slug_subject = simple_slugify(subject)
             
        lesson_id = f"{slug_subject}-{grade}-{lesson_db_id}"
        
        transcript = row['full_transcript']
        
        # Metadata
        checksum = hashlib.sha256(transcript.encode('utf-8')).hexdigest()
        
        lesson_data = {
            "lesson_id": lesson_id,
            "title": row['lesson_title'],
            "subject": subject,
            "grade": grade,
            "transcript": transcript,
            "metadata": {
                "source": "shared_db",
                "db_id": lesson_db_id,
                "lesson_order": row['lesson_order'],
                "course_title": course_title,
                "content_checksum": checksum
            }
        }
        
        print(f"\nProcessing [{count}]: {course_title} - {row['lesson_title']}")
        print(f"   🆔 Generated ID: {lesson_id}")
        
        if dry_run:
            print(f"   🔍 Preview Transcript: {transcript[:100]}...")
            print(f"   📊 Metadata: Grade={grade}, Subject={subject}")
            continue
            
        # Load
        service.process_lesson_data(lesson_data, force=force)

    print("\n" + "=" * 70)
    print("✨ Sync completed!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync Shared DB lessons to Local DB")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--force", action="store_true", help="Force re-indexing")
    args = parser.parse_args()
    
    if not test_connection():
        print("❌ Local Database connection failed.")
        sys.exit(1)
        
    sync(dry_run=args.dry_run, force=args.force)
