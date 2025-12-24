"""
Ingestion Service
Handles reading files, parsing metadata, chunking, and indexing into the database.
"""
import os
import re
import json
import time
import hashlib
import uuid
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


    def calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def process_lesson_data(self, lesson_data: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
        """
        Process lesson data (agnostic of source):
        1. Check existing
        2. Insert Lesson
        3. Semantic Chunking
        4. Embedding
        5. Insert Chunks
        """
        lesson_id = lesson_data["lesson_id"]
        print(f"📄 Processing Lesson: {lesson_id} ({lesson_data.get('title')})")
        
        # Metrics initialization
        start_time = time.time()
        metrics = {
            "lesson_id": lesson_data["lesson_id"],
            "title": lesson_data.get("title"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_time)),
            "timings": {},
            "stats": {},
            "source_metadata": lesson_data.get("metadata", {})
        }

        # 1. Check existing
        if not force:
            existing = get_lesson(lesson_id)
            if existing and existing.get("status") == "indexed":
                print(f"   ⏭️  Skipping {lesson_id} (already indexed)")
                return {"status": "skipped", "lesson_id": lesson_id}

        content = lesson_data.get("transcript", "")
        if not content:
             print(f"   ⚠️  Empty content")
             return {"status": "error", "message": "Empty content"}

        # 2. Insert/Update Lesson
        insert_start = time.time()
        insert_lesson(lesson_data)
        metrics["timings"]["db_insert_lesson_ms"] = (time.time() - insert_start) * 1000
        
        # 3. Semantic Chunking
        print(f"   🧠 Semantic chunking (creating Parent Chunks)...")
        chunk_start = time.time()
        parent_chunks = self.processor.semantic_chunk(content, max_chunk_size=2000, min_chunk_size=200) 
        metrics["timings"]["chunking_ms"] = (time.time() - chunk_start) * 1000
        metrics["stats"]["parent_chunk_count"] = len(parent_chunks)
        
        print(f"   Created {len(parent_chunks)} parent chunks. Generating child chunks...")
        
        # 4. Child Chunk Generation & Embedding
        embed_start = time.time()
        chunks_data = []
        chunks_metadata_list = []
        
        total_child_chunks = 0
        
        for p_idx, parent_text in enumerate(parent_chunks):
            child_texts = self.processor.split_by_tokens(parent_text, chunk_size=512, overlap=100)
            
            for c_idx, child_text in enumerate(child_texts):
                embedding = self.processor.get_embedding(child_text)
                
                chunk_id = f"{lesson_id}_p{p_idx}_c{c_idx}"
                
                chunk_meta = {
                    "chunk_id": chunk_id,
                    "lesson_id": lesson_id,
                    "parent_index": p_idx,
                    "child_index": c_idx,
                    "text": child_text,
                    "tokens_count": self.processor.count_tokens(child_text),
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
                }
                
                chunks_data.append({
                    "chunk_index": total_child_chunks,
                    "text": child_text,
                    "embedding": embedding,
                    "parent_content": parent_text 
                })
                
                chunks_metadata_list.append(chunk_meta)
                total_child_chunks += 1
            
        metrics["chunks_metadata"] = chunks_metadata_list
        metrics["timings"]["embedding_ms"] = (time.time() - embed_start) * 1000
        metrics["stats"]["total_child_chunks"] = total_child_chunks

        # 5. Insert Chunks
        chunk_insert_start = time.time()
        insert_chunks_batch(lesson_id, chunks_data)
        update_lesson_status(lesson_id, "indexed", total_child_chunks)
        metrics["timings"]["db_insert_chunks_ms"] = (time.time() - chunk_insert_start) * 1000
        
        metrics["timings"]["total_process_ms"] = (time.time() - start_time) * 1000
        
        # Save metadata
        try:
            metadata_dir = Path("data/metadata")
            metadata_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = metadata_dir / f"{lesson_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
            print(f"   💾 Metadata saved to {output_file}")
        except Exception as e:
            print(f"   ⚠️ Failed to save metadata: {e}")
            
        return {
            "status": "success", 
            "lesson_id": lesson_id, 
            "chunks_count": total_child_chunks
        }

    def process_file(self, file_path: str, force: bool = False) -> Dict[str, Any]:
        """
        Wrapper to process a file by converting it to lesson_data format
        """
        path = Path(file_path)
        if not path.exists():
            return {"status": "error", "message": f"File not found: {file_path}"}
            
        filename = path.name
        
        # Parse Metadata
        metadata = self.parse_filename(filename)
        lesson_id = metadata["lesson_id"]
        
        # Check existing (optimization: check before reading file)
        if not force:
            existing = get_lesson(lesson_id)
            if existing and existing.get("status") == "indexed":
                print(f"📄 Skipping file {filename} (already indexed as {lesson_id})")
                return {"status": "skipped", "lesson_id": lesson_id}

        # Read content
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception as e:
            return {"status": "error", "message": str(e)}

        file_checksum = self.calculate_checksum(str(path))

        # Construct Lesson Data
        lesson_data = {
            "lesson_id": lesson_id,
            "title": metadata["title"],
            "subject": metadata["subject"],
            "grade": metadata["grade"],
            "transcript": content,
            "metadata": {
                **metadata.get("metadata", {}),
                "source_file": filename,
                "lesson_number": metadata.get("lesson_number", 0),
                "file_checksum": file_checksum,
                "file_size_bytes": path.stat().st_size
            }
        }
        
        return self.process_lesson_data(lesson_data, force)

    def process_event_data(self, payload: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
        """
        Process raw event payload from RabbitMQ.
        Auto-extracts metadata from Title if missing in payload.
        """
        lesson_id = str(payload.get("lesson_id", ""))
        title = payload.get("title", "")
        content = payload.get("transcript", "") or payload.get("content", "")
        
        try:
            grade = int(payload.get("grade", 0))
        except (ValueError, TypeError):
            # If grade is "Medium" or other string, default to 0
            grade = 0

        # 1. Base Lesson Data
        lesson_data = {
            "lesson_id": lesson_id,
            "title": title,
            "transcript": content,
            "subject": payload.get("subject", "Unknown"),
            "grade": grade,
            "metadata": payload.get("metadata", {})
        }
        
        # 2. Enrich if Grade/Subject are missing or default
        # Priority:
        # 1. 'course_title' (Perfect source, e.g. "Math 4")
        # 2. 'title' (Lesson Title, e.g. "Toán lớp 4 Bài 1...")
        
        course_title = payload.get("course_title", "")
        if grade == 0 and course_title:
             # Try to extract number from course title
             match = re.search(r"(\d+)", course_title)
             if match:
                 grade = int(match.group(1))
                 lesson_data["grade"] = grade
                 print(f"🕵️ Extracted grade {grade} from course_title: '{course_title}'")
        
        if lesson_data["grade"] == 0 or lesson_data["subject"] == "Unknown":
            print(f"🕵️ Extracting metadata from title: '{title}'")
            # Reuse parse_filename logic by treating title as filename
            extracted = self.parse_filename(title)
            
            # Only override if we found something useful
            if extracted["grade"] != 0:
                lesson_data["grade"] = extracted["grade"]
                lesson_data["subject"] = extracted["subject"]
                lesson_data["lesson_number"] = extracted.get("lesson_number")
                
                # Merge extra metadata
                if "metadata" in extracted:
                    lesson_data["metadata"].update(extracted["metadata"])
                    
        return self.process_lesson_data(lesson_data, force)

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
