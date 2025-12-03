"""
Advanced Chunking Strategies with Context Windows
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Dict
import re


class AdvancedChunker:
    """
    Advanced chunking with:
    - Context windows (surrounding chunks)
    - Section-aware splitting
    - Metadata extraction
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        context_window: int = 1  # Number of surrounding chunks to include
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.context_window = context_window
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
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
    
    def chunk_with_context(
        self,
        text: str,
        lesson_id: str
    ) -> List[Dict]:
        """
        Create chunks with context windows
        
        Returns:
            [
                {
                    "chunk_index": 0,
                    "text": "main chunk",
                    "context_before": "previous chunk",
                    "context_after": "next chunk",
                    "metadata": {...}
                },
                ...
            ]
        """
        # Preprocess
        text = self.preprocess_transcript(text)
        
        # Extract sections
        sections = self.extract_section_headers(text)
        
        # Split into chunks
        raw_chunks = self.splitter.split_text(text)
        
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
            
            # Context windows
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
                "context_before": context_before[-200:] if context_before else "",  # Last 200 chars
                "context_after": context_after[:200] if context_after else "",  # First 200 chars
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
