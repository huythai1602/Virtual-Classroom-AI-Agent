"""
Text Processing Utilities
Shared logic for chunking and embedding to ensure consistency between ingestion and retrieval.
"""
import re
import numpy as np
import tiktoken
from typing import List, Union, Optional
from openai import OpenAI
from rank_bm25 import BM25Okapi
try:
    from pyvi import ViTokenizer
except ImportError:
    ViTokenizer = None

from config.settings import settings

# Lazy initialization
_client = None
_encoding = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client

def get_encoding():
    global _encoding
    if _encoding is None:
        try:
            # Use model from settings, fallback to standard encoding
            model = settings.OPENAI_MODEL
            _encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            _encoding = tiktoken.get_encoding("cl100k_base")
    return _encoding

class TextProcessor:
    """
    Handles text processing tasks:
    - Token counting
    - Semantic chunking (based on embedding similarity)
    - Embedding generation
    """
    
    @staticmethod
    def count_tokens(text: str) -> int:
        """Count tokens using tiktoken"""
        try:
            encoding = get_encoding()
            return len(encoding.encode(text))
        except:
            return len(text) // 4
            
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text for BM25 (words/syllables)"""
        if ViTokenizer:
            # PyVi returns string with underscores for compounds, we split by space
            return ViTokenizer.tokenize(text).split()
        return text.lower().split()


    @staticmethod
    def get_embedding(text: str, model: str = settings.OPENAI_EMBEDDING_MODEL) -> List[float]:
        """Get OpenAI embedding"""
        text = text.replace("\n", " ")
        try:
            client = get_client()
            response = client.embeddings.create(
                model=model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ Embedding error: {e}")
            # Return zero vector on failure to avoid crashing pipeline, 
            # though in production you might want to retry or raise
            return [0.0] * 1536

    @classmethod
    def semantic_chunk(cls, text: str, max_chunk_size: int = 300, min_chunk_size: int = 50, threshold: float = None) -> List[str]:
        """
        Split text into semantically coherent chunks using embedding similarity.
        
        Args:
            text: Input text
            max_chunk_size: Max tokens approx per chunk (target 250-400)
            min_chunk_size: Min tokens to avoid tiny chunks
            threshold: Similarity threshold to split (defaults to settings.SEMANTIC_THRESHOLD)
        """
        if threshold is None:
            threshold = settings.SEMANTIC_THRESHOLD

        # Normalize and split into sentences
        sentences = cls.split_sentences_vn(text)
        if len(sentences) <= 1:
            return [text]
        
        # Get embeddings for each sentence to calculate similarity
        embeddings = []
        valid_sentences = []
        for sent in sentences:
            if sent.strip():
                valid_sentences.append(sent)
                embeddings.append(cls.get_embedding(sent))
        
        sentences = valid_sentences
        if len(embeddings) <= 1:
            return [text]
        
        # Calculate cosine similarity between consecutive sentences
        embeddings_array = np.array(embeddings)
        similarities = []
        for i in range(len(embeddings_array) - 1):
            # dot product of normalized vectors = cosine similarity
            # OpenAI embeddings are normalized, so dot product is sufficient
            sim = np.dot(embeddings_array[i], embeddings_array[i + 1])
            similarities.append(sim)
        
        # Find split points
        split_indices = [0]
        current_chunk_tokens = 0
        
        for i, sim in enumerate(similarities):
            # Estimate tokens roughly or use count_tokens (slower but accurate)
            # For speed in loop, we can estimate: words * 1.3 or just use count_tokens if cached/fast.
            # Let's use count_tokens for accuracy as requested.
            sent_tokens = cls.count_tokens(sentences[i])
            current_chunk_tokens += sent_tokens
            
            # Logic:
            # 1. Force split if chunk gets too big (> max)
            # 2. Split if similarity is low AND we have enough content (> min)
            # 3. Otherwise keep accumulating
            
            is_max_reached = current_chunk_tokens >= max_chunk_size
            is_sim_low = sim < threshold
            is_min_satisfied = current_chunk_tokens >= min_chunk_size

            if is_max_reached or (is_sim_low and is_min_satisfied):
                split_indices.append(i + 1)
                current_chunk_tokens = 0
        
        split_indices.append(len(sentences))
        
        # Reconstruct chunks
        chunks = []
        for i in range(len(split_indices) - 1):
            start = split_indices[i]
            end = split_indices[i + 1]
            chunk_text = ' '.join(sentences[start:end])
            
            # Post-processing: Check if chunk is too small and merge with previous if possible
            # (Simple heuristic: if chunk < min_size/2, maybe it's orphan. 
            # But let's stick to the generated splits for now to preserve semantic breaks)
            
            if chunk_text.strip():
                chunks.append(chunk_text.strip())
        
        return chunks if chunks else [text]

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize Vietnamese text for consistent processing:
        1. Parse numbers (e.g. 100.000 -> 100000)
        2. Clean extra whitespace
        """
        if not text:
            return ""
            
        # 1. Normalize numbers: "100.000" -> "100000" (Vietnamese style dots in numbers)
        # Matches digits + dot + digits (e.g., 52.431 -> 52431)
        # Be careful not to replace decimal commas if they exist, but VN usually uses comma for decimal.
        # This regex removes DOTS between digits provided they are part of a thousand separator pattern.
        # Simple heuristic: remove dots if surrounded by digits
        text = re.sub(r'(?<=\d)\.(?=\d{3})', '', text)
        
        # 2. Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    @staticmethod
    def split_sentences_vn(text: str) -> List[str]:
        """Split sentences using simple heuristic or pyvi if available"""
        # Try to use PyVi for better segmentation
        try:
            # PyVi doesn't have a direct sentence splitter, it has a tokenizer.
            # However, for sentence splitting, regex is often "good enough" if we handle common abbreviations.
            # Let's rely on standard regex but enhanced for common Vietnamese punctuation.
            
            # Normalize first
            text = TextProcessor.normalize_text(text)
            
            # Split by common ending punctuation [.!?] followed by whitespace and uppercase/number
            # This is a heuristic.
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZĐ0-9])', text)
            return [s.strip() for s in sentences if s.strip()]
        except:
             # Fallback
             return re.split(r'(?<=[.!?])\s+', text)
