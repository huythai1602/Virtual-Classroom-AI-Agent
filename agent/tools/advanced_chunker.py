"""
Advanced Chunking with Semantic Boundary Detection
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Dict
import re
import numpy as np
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()


class AdvancedChunker:
    """
    Advanced chunking with:
    - Context windows (surrounding chunks)
    - Section-aware splitting
    - Metadata extraction
    """
    
    def __init__(
        self,
        chunk_size: int = 800,  # Reduced from 1000
        chunk_overlap: int = 150,  # Reduced from 200
        context_window: int = 1,
        use_semantic: bool = True
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.context_window = context_window
        self.use_semantic = use_semantic
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for semantic similarity"""
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000]  # Limit input
            )
            return response.data[0].embedding
        except:
            return None
    
    def preprocess_transcript(self, text: str) -> str:
        """
        Clean transcript text
        - Remove timestamps
        - Normalize whitespace
        - Fix common OCR errors
        """
        # Remove timestamps [00:00]
        text = re.sub(r'\[\d{2}:\d{2}(:\d{2})?\]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Fix common errors
        text = text.replace('﻿', '')
        text = text.strip()
        
        return text
    
    def extract_section_headers(self, text: str) -> List[Dict]:
        """
        Extract section headers for better metadata
        
        Returns:
            List of {position: int, header: str, level: int}
        """
        headers = []
        
        # Pattern: "Bài X:", "Phần X:", numbers followed by dot
        patterns = [
            (r'^(Bài \d+[:.])(.+)$', 1),
            (r'^(Phần \d+[:.])(.+)$', 2),
            (r'^(\d+\.)(.+)$', 3),
            (r'^([IVX]+\.)(.+)$', 2)  # Roman numerals
        ]
        
        lines = text.split('\n')
        position = 0
        
        for line in lines:
            line = line.strip()
            for pattern, level in patterns:
                match = re.match(pattern, line, re.MULTILINE)
                if match:
                    headers.append({
                        'position': position,
                        'header': line,
                        'level': level
                    })
                    break
            position += len(line) + 1
        
        return headers
    
    def semantic_merge_chunks(self, chunks: List[str], similarity_threshold: float = 0.85) -> List[str]:
        """
        Merge chunks that are semantically similar (same topic)
        Reduces redundancy and token usage
        """
        if not self.use_semantic or len(chunks) <= 1:
            return chunks
        
        merged = []
        current_chunk = chunks[0]
        
        for next_chunk in chunks[1:]:
            # Get embeddings
            emb1 = self.get_embedding(current_chunk[-500:])  # Last 500 chars
            emb2 = self.get_embedding(next_chunk[:500])  # First 500 chars
            
            if emb1 and emb2:
                # Calculate similarity
                similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
                
                # If very similar, merge
                if similarity > similarity_threshold and len(current_chunk) + len(next_chunk) < self.chunk_size * 1.5:
                    current_chunk = current_chunk + "\n\n" + next_chunk
                else:
                    merged.append(current_chunk)
                    current_chunk = next_chunk
            else:
                merged.append(current_chunk)
                current_chunk = next_chunk
        
        merged.append(current_chunk)
        return merged

    def chunk_with_context(
        self,
        text: str,
        lesson_id: str
    ) -> List[Dict]:
        """
        Create chunks with semantic boundaries and context windows
        Optimized for token efficiency
        """
        # Preprocess
        text = self.preprocess_transcript(text)
        
        # Extract sections
        sections = self.extract_section_headers(text)
        
        # Split into initial chunks
        raw_chunks = self.splitter.split_text(text)
        
        # Semantic merging to reduce redundancy
        if self.use_semantic:
            raw_chunks = self.semantic_merge_chunks(raw_chunks)
        
        # Add context windows
        chunks_with_context = []
        
        for i, chunk_text in enumerate(raw_chunks):
            # Find current section
            chunk_position = text.find(chunk_text)
            current_section = None
            for section in reversed(sections):
                if section['position'] <= chunk_position:
                    current_section = section['header']
                    break
            
            # Context windows (reduced size for token efficiency)
            context_before = raw_chunks[i-1] if i > 0 else ""
            context_after = raw_chunks[i+1] if i < len(raw_chunks) - 1 else ""
            
            # Metadata
            metadata = {
                "section": current_section,
                "position": i,
                "total_chunks": len(raw_chunks),
                "char_count": len(chunk_text),
                "has_context_before": bool(context_before),
                "has_context_after": bool(context_after)
            }
            
            chunks_with_context.append({
                "chunk_index": i,
                "text": chunk_text,
                "context_before": context_before[-150:] if context_before else "",  # Reduced: 200→150
                "context_after": context_after[:150] if context_after else "",  # Reduced: 200→150
                "metadata": metadata
            })
        
        return chunks_with_context
    
    def get_full_context(
        self,
        chunks: List[Dict],
        target_index: int,
        window: int = 1
    ) -> str:
        """
        Get full context for a specific chunk
        
        Args:
            chunks: All chunks for a lesson
            target_index: Index of target chunk
            window: Number of surrounding chunks
        """
        start_idx = max(0, target_index - window)
        end_idx = min(len(chunks), target_index + window + 1)
        
        context_chunks = chunks[start_idx:end_idx]
        
        # Combine with markers
        full_context = ""
        for chunk in context_chunks:
            if chunk["chunk_index"] == target_index:
                full_context += f"\n\n[TARGET CHUNK]\n{chunk['text']}\n[/TARGET CHUNK]\n\n"
            else:
                full_context += f"\n{chunk['text']}\n"
        
        return full_context.strip()


# Global instance
_chunker_instance = None

def get_chunker() -> AdvancedChunker:
    """Get or create global chunker instance"""
    global _chunker_instance
    if _chunker_instance is None:
        _chunker_instance = AdvancedChunker()
    return _chunker_instance
