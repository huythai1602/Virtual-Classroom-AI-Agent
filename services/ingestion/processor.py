"""
Ingestion Service
Handles reading files, parsing metadata, chunking, and indexing into the database.
"""
import os
import re
import json
from pathlib import Path
from typing import Dict, Any, List

from core.text_processing import TextProcessor
from repositories.lessons import insert_lesson, update_lesson_status, get_lesson
from repositories.chunks import insert_chunks_batch

class IngestionService:
    def __init__(self):
        self.processor = TextProcessor()

    def parse_filename(self, filename: str) -> Dict[str, Any]:
        """
        Parse filename to extract metadata.
        Supports patterns:
        1. "Toán lớp X Bài Y Title - ..."
        2. "bai_X_title.txt" (legacy)
        """
        # Pattern 1: Standard Format
        # e.g., "Toán lớp 4 Bài 1 Ôn tập các số đến 100000 - ..."
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
                "lesson_number": lesson_num,
                "metadata": {}
            }
        
        # Pattern 2: Legacy/Simple Format
        # e.g., "bai_2_phan_so.txt"
        match = re.search(r"bai[_\s](\d+)[_\s](.+)\.txt", filename, re.IGNORECASE)
        if match:
            lesson_num = int(match.group(1))
            title = match.group(2).replace("_", " ").title()
            return {
                "lesson_id": f"toan-lop-4-bai-{lesson_num}",
                "title": title,
                "subject": "Toán",
                "grade": 4, # Default to 4 for this format as per original script
                "lesson_number": lesson_num,
                "metadata": {}
            }
            
        # Fallback
        stem = Path(filename).stem
        return {
            "lesson_id": stem.lower().replace(" ", "-")[:50],
            "title": stem,
            "subject": "Unknown",
            "grade": 0,
            "lesson_number": 0,
            "metadata": {}
        }

    def process_file(self, file_path: str, force: bool = False) -> Dict[str, Any]:
        """
        Process a single text file:
        1. Parse metadata
        2. Check existing
        3. Insert Lesson
        4. Semantic Chunking
        5. Embedding
        6. Insert Chunks
        """
        path = Path(file_path)
        if not path.exists():
            return {"status": "error", "message": f"File not found: {file_path}"}
            
        filename = path.name
        print(f"📄 Processing: {filename}")
        
        # 1. Parse Metadata
        metadata = self.parse_filename(filename)
        lesson_id = metadata["lesson_id"]
        
        # 2. Check existing
        if not force:
            existing = get_lesson(lesson_id)
            if existing and existing.get("status") == "indexed":
                print(f"   ⏭️  Skipping {lesson_id} (already indexed)")
                return {"status": "skipped", "lesson_id": lesson_id}

        # Read content
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                
            if not content:
                print(f"   ⚠️  Empty file")
                return {"status": "error", "message": "Empty file"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

        # 3. Insert/Update Lesson
        lesson_data = {
            "lesson_id": lesson_id,
            "title": metadata["title"],
            "subject": metadata["subject"],
            "grade": metadata["grade"],
            "transcript": content,
            "metadata": {
                **metadata.get("metadata", {}),
                "source_file": filename,
                "lesson_number": metadata.get("lesson_number", 0)
            }
        }
        insert_lesson(lesson_data)
        
        # 4. Semantic Chunking
        print(f"   🧠 Semantic chunking...")
        chunks = self.processor.semantic_chunk(content)
        print(f"   Created {len(chunks)} chunks")
        
        # 5. Embedding & Preparation
        chunks_data = []
        for i, chunk_text in enumerate(chunks):
            embedding = self.processor.get_embedding(chunk_text)
            chunks_data.append({
                "chunk_index": i,
                "text": chunk_text,
                "embedding": embedding
            })
            
        # 6. Insert Chunks
        insert_chunks_batch(lesson_id, chunks_data)
        update_lesson_status(lesson_id, "indexed", len(chunks))
        
        return {
            "status": "success", 
            "lesson_id": lesson_id, 
            "chunks_count": len(chunks)
        }

    def process_directory(self, directory: str, force: bool = False) -> Dict[str, int]:
        """Process all .txt files in a directory"""
        path = Path(directory)
        if not path.exists():
             return {"status": "error", "message": "Directory not found"}
             
        results = {"success": 0, "skipped": 0, "error": 0, "total_chunks": 0}
        
        for file_path in path.glob("*.txt"):
            res = self.process_file(str(file_path), force)
            status = res.get("status")
            if status == "success":
                results["success"] += 1
                results["total_chunks"] += res.get("chunks_count", 0)
            elif status == "skipped":
                results["skipped"] += 1
            else:
                results["error"] += 1
                
        return results
