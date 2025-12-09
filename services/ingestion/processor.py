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
        
        # Metrics collection
        start_time = time.time()
        file_checksum = self.calculate_checksum(str(path))
        
        # Root Metadata Schema
        metrics = {
            "lesson_id": lesson_id,
            "filename": filename,
            "file_size_bytes": path.stat().st_size,
            "file_checksum": file_checksum,
            "version": "1.0",
            "source_type": "transcript",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_time)),
            "provenance": {
                "asr_engine": "unknown", 
                "human_reviewed": False
            },
            "timings": {},
            "stats": {},
            "chunks_metadata": []
        }
        
        # 2. Check existing
        if not force:
            existing = get_lesson(lesson_id)
            if existing and existing.get("status") == "indexed":
                print(f"   ⏭️  Skipping {lesson_id} (already indexed)")
                return {"status": "skipped", "lesson_id": lesson_id}

        # Read content
        read_start = time.time()
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            
            metrics["timings"]["read_file_ms"] = (time.time() - read_start) * 1000
                
            if not content:
                print(f"   ⚠️  Empty file")
                return {"status": "error", "message": "Empty file"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

        # 3. Insert/Update Lesson
        insert_start = time.time()
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
                "file_checksum": file_checksum
            }
        }
        insert_lesson(lesson_data)
        metrics["timings"]["db_insert_lesson_ms"] = (time.time() - insert_start) * 1000
        
        # 4. Semantic Chunking (PARENT CHUNKS)
        print(f"   🧠 Semantic chunking (creating Parent Chunks)...")
        chunk_start = time.time()
        # Semantic chunking now creates PARENT chunks (large context contexts)
        parent_chunks = self.processor.semantic_chunk(content, max_chunk_size=2000, min_chunk_size=200) 
        metrics["timings"]["chunking_ms"] = (time.time() - chunk_start) * 1000
        metrics["stats"]["parent_chunk_count"] = len(parent_chunks)
        
        print(f"   Created {len(parent_chunks)} parent chunks. Generating child chunks...")
        
        # 5. Child Chunk Generation & Embedding
        embed_start = time.time()
        chunks_data = []
        chunks_metadata_list = []
        
        total_child_chunks = 0
        
        for p_idx, parent_text in enumerate(parent_chunks):
            # Create Child Chunks (fixed size for precision search)
            child_texts = self.processor.split_by_tokens(parent_text, chunk_size=512, overlap=100)
            
            for c_idx, child_text in enumerate(child_texts):
                embedding = self.processor.get_embedding(child_text)
                
                # Logic ID
                chunk_id = f"{lesson_id}_p{p_idx}_c{c_idx}"
                
                # Chunk Metadata Record
                chunk_meta = {
                    "chunk_id": chunk_id,
                    "lesson_id": lesson_id,
                    "parent_index": p_idx,
                    "child_index": c_idx,
                    "text": child_text,
                    # We don't save full parent text in JSON metadata to save space if needed, 
                    # but we DO save it in DB.
                    "tokens_count": self.processor.count_tokens(child_text),
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
                }
                
                chunks_data.append({
                    "chunk_index": total_child_chunks, # Global index for the lesson
                    "text": child_text,
                    "embedding": embedding,
                    "parent_content": parent_text 
                })
                
                chunks_metadata_list.append(chunk_meta)
                total_child_chunks += 1
            
        metrics["chunks_metadata"] = chunks_metadata_list
        metrics["timings"]["embedding_ms"] = (time.time() - embed_start) * 1000
        metrics["stats"]["total_child_chunks"] = total_child_chunks

        # 6. Insert Chunks
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
