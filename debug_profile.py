import time
import sys
import os
from typing import List, Dict

# Setup path
sys.path.insert(0, os.getcwd())

from services.rag.retriever import get_retriever
from config.settings import settings

def profile_retrieval():
    print("🚀 Starting Performance Profiling...")
    
    # 1. Initialization
    t0 = time.time()
    try:
        retriever = get_retriever()
        print(f"✅ Init RAGRetriever: {time.time() - t0:.4f}s")
    except Exception as e:
        print(f"❌ Init failed: {e}")
        return

    query = "Phân số là gì?"
    lesson_id = None # Global search (worst case)
    
    # 2. Vector Search (PGVector)
    t0 = time.time()
    try:
        vectors = retriever.vector_search(query, lesson_id, k=20)
        print(f"✅ Vector Search (k=20): {time.time() - t0:.4f}s (Results: {len(vectors)})")
    except Exception as e:
        print(f"❌ Vector Search failed: {e}")
        vectors = []

    # 3. BM25 Search (In-Memory Build)
    t0 = time.time()
    try:
        bm25 = retriever.bm25_search(query, lesson_id, k=10)
        print(f"✅ BM25 Search (k=10): {time.time() - t0:.4f}s (In-Memory Index Build)")
    except Exception as e:
        print(f"❌ BM25 Search failed: {e}")
        bm25 = []

    # 4. Reranking using Cross-Encoder
    # Combine results for a realistic test set
    candidates = vectors + bm25
    t0 = time.time()
    try:
        reranked = retriever.rerank(query, candidates, k=10)
        print(f"✅ Reranking ({len(candidates)} pairs): {time.time() - t0:.4f}s")
    except Exception as e:
        print(f"❌ Reranking failed: {e}")
        reranked = []

    # 5. Semantic Chunking (The suspect)
    # Take top 1 result to test chunking speed
    if reranked:
        top_chunk = reranked[0]["text"]
        print(f"   ℹ️  Chunk size: {len(top_chunk)} chars")
        t0 = time.time()
        try:
            chunks = retriever.processor.semantic_chunk(top_chunk)
            print(f"✅ Semantic Chunking (1 chunk): {time.time() - t0:.4f}s")
        except Exception as e:
            print(f"❌ Semantic Chunking failed: {e}")

if __name__ == "__main__":
    profile_retrieval()
