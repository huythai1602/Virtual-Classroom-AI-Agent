"""
Migration script: Transcript TXT files → PostgreSQL + pgvector

This script:
1. Reads all .txt files from data/transcripts/
2. Parses metadata from filenames
3. Inserts lessons into PostgreSQL
4. Performs chunking and embedding
5. Inserts chunks with vectors into PostgreSQL
"""

import os
import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from database.db_connection import test_connection
from database.lessons_repository import insert_lesson, update_lesson_status, get_lesson
from database.chunks_repository import insert_chunks_batch
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

# Text splitter configuration (same as ChromaDB)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    separators=["\n\n", "\n", " ", ""]
)


def parse_filename(filename: str) -> dict:
    """
    Parse filename to extract metadata
    
    Examples:
        "Toán lớp 4 Bài 1 Ôn tập các số đến 100000 - ..."
        → {lesson_id: "toan-lop-4-bai-1", title: "Ôn tập các số đến 100000", ...}
        
        "bai_2_phan_so.txt"
        → {lesson_id: "toan-lop-4-bai-2", title: "Phân số", ...}
    """
    
    # Pattern 1: "Toán lớp X Bài Y Title - ..."
    match = re.search(r"Toán lớp (\d+) Bài (\d+) (.+?) -", filename)
    if match:
        grade = int(match.group(1))
        lesson_num = int(match.group(2))
        title = match.group(3).strip()
        
        return {
            "lesson_id": f"toan-lop-{grade}-bai-{lesson_num}",
            "title": title,
            "subject": "Toán",
            "grade": grade,
            "lesson_number": lesson_num
        }
    
    # Pattern 2: "bai_X_title.txt"
    match = re.search(r"bai[_\s](\d+)[_\s](.+)\.txt", filename, re.IGNORECASE)
    if match:
        lesson_num = int(match.group(1))
        title = match.group(2).replace("_", " ").title()
        
        return {
            "lesson_id": f"toan-lop-4-bai-{lesson_num}",
            "title": title,
            "subject": "Toán",
            "grade": 4,
            "lesson_number": lesson_num
        }
    
    # Fallback
    print(f"⚠️  Cannot parse filename: {filename}, using defaults")
    return {
        "lesson_id": Path(filename).stem.lower().replace(" ", "-")[:50],
        "title": Path(filename).stem,
        "subject": "Unknown",
        "grade": 0,
        "lesson_number": 0
    }


def get_embedding(text: str) -> list:
    """Get OpenAI embedding for text"""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ Embedding error: {e}")
        raise


def process_and_index_lesson(lesson_id: str):
    """
    Main indexing workflow:
    1. Get lesson transcript from DB
    2. Chunking
    3. Embedding each chunk
    4. Insert chunks with embeddings
    5. Update lesson status
    
    Returns:
        Number of chunks created
    """
    print(f"\n🔄 Processing lesson: {lesson_id}")
    
    # 1. Get transcript
    lesson = get_lesson(lesson_id)
    if not lesson:
        print(f"❌ Lesson not found: {lesson_id}")
        return 0
    
    transcript = lesson["transcript"]
    
    # 2. Chunking
    print(f"   📄 Chunking transcript ({len(transcript)} chars)...")
    chunks = text_splitter.split_text(transcript)
    print(f"   ✅ Created {len(chunks)} chunks")
    
    # 3. Embedding + Prepare data
    print(f"   🧠 Creating embeddings...")
    chunks_data = []
    
    for i, chunk_text in enumerate(chunks):
        if i % 10 == 0:
            print(f"      ... Processing chunk {i+1}/{len(chunks)}")
        
        try:
            embedding = get_embedding(chunk_text)
            
            chunks_data.append({
                "chunk_index": i,
                "text": chunk_text,
                "embedding": embedding
            })
        except Exception as e:
            print(f"      ❌ Failed to embed chunk {i}: {e}")
            continue
    
    # 4. Insert to DB
    print(f"   💾 Inserting chunks to PostgreSQL...")
    insert_chunks_batch(lesson_id, chunks_data)
    
    # 5. Update status
    update_lesson_status(lesson_id, "indexed", len(chunks))
    print(f"   ✅ Lesson indexed successfully: {len(chunks)} chunks")
    
    return len(chunks)


def migrate_all_txt_files(transcripts_dir: str = "data/transcripts", force: bool = False):
    """
    Main migration function:
    - Read all .txt files
    - Parse metadata
    - Insert lessons
    - Chunking + Embedding + Index
    
    Args:
        transcripts_dir: Directory containing .txt files
        force: If True, re-index lessons even if already indexed
    """
    
    print("=" * 70)
    print("🚀 Starting TXT Files → PostgreSQL Migration")
    if force:
        print("⚠️  FORCE MODE: Will re-index all lessons")
    print("=" * 70)
    
    transcripts_path = Path(__file__).parent.parent / transcripts_dir
    txt_files = list(transcripts_path.glob("*.txt"))
    
    if not txt_files:
        print(f"\n⚠️  No .txt files found in {transcripts_path}")
        return
    
    print(f"\n📂 Found {len(txt_files)} transcript files in {transcripts_path}")
    
    total_chunks = 0
    success_count = 0
    
    for i, txt_file in enumerate(txt_files, 1):
        print(f"\n{'='*70}")
        print(f"📄 [{i}/{len(txt_files)}] Processing: {txt_file.name}")
        print(f"{'='*70}")
        
        try:
            # 1. Read transcript
            with open(txt_file, 'r', encoding='utf-8') as f:
                transcript = f.read().strip()
            
            if not transcript:
                print(f"⚠️  Empty file, skipping...")
                continue
            
            print(f"   📊 Transcript length: {len(transcript)} characters")
            
            # 2. Parse metadata
            metadata = parse_filename(txt_file.name)
            print(f"   📋 Metadata:")
            print(f"      - lesson_id: {metadata['lesson_id']}")
            print(f"      - title: {metadata['title']}")
            print(f"      - subject: {metadata['subject']}, grade: {metadata['grade']}")
            
            lesson_id = metadata["lesson_id"]
            
            # 3. Check if already indexed (skip if not force mode)
            if not force:
                existing_lesson = get_lesson(lesson_id)
                if existing_lesson and existing_lesson.get('status') == 'indexed':
                    print(f"   ⏭️  SKIPPING: Lesson already indexed ({existing_lesson.get('total_chunks', 0)} chunks)")
                    print(f"      Use --force to re-index")
                    success_count += 1
                    total_chunks += existing_lesson.get('total_chunks', 0)
                    continue
            
            # 4. Insert/update lesson
            lesson_data = {
                "lesson_id": lesson_id,
                "title": metadata["title"],
                "subject": metadata["subject"],
                "grade": metadata["grade"],
                "transcript": transcript,
                "metadata": {
                    "source_file": txt_file.name,
                    "lesson_number": metadata.get("lesson_number", 0)
                }
            }
            
            insert_lesson(lesson_data)
            print(f"   ✅ Lesson inserted/updated: {lesson_id}")
            
            # 5. Process chunks
            chunks_count = process_and_index_lesson(lesson_id)
            total_chunks += chunks_count
            success_count += 1
            
            print(f"\n   🎉 SUCCESS: {chunks_count} chunks indexed")
            
        except Exception as e:
            print(f"\n   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "=" * 70)
    print("✨ Migration completed!")
    print(f"   📊 Successfully migrated: {success_count}/{len(txt_files)} lessons")
    print(f"   📦 Total chunks created: {total_chunks}")
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate transcript files to PostgreSQL + pgvector")
    parser.add_argument("--force", action="store_true", help="Force re-index all lessons (even if already indexed)")
    args = parser.parse_args()
    
    print("\n🔍 Testing database connection...")
    
    if not test_connection():
        print("\n❌ Database connection failed. Please check:")
        print("   1. PostgreSQL is running")
        print("   2. .env file has correct POSTGRES_* variables")
        print("   3. pgvector extension is installed: CREATE EXTENSION vector;")
        sys.exit(1)
    
    print("\n✅ Database connection successful!\n")
    
    # Run migration
    migrate_all_txt_files(force=args.force)
