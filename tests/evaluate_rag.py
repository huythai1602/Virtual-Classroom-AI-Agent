import sys
import os
import json
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.rag.retriever import get_retriever

def evaluate_retrieval():
    print("🚀 Starting RAG Evaluation...")
    retriever = get_retriever()
    
    # Synthetic Test Set (Question -> Expected substring/content or Chunk ID)
    # Ideally this comes from a golden dataset file.
    test_cases = [
        {
            "query": "Cách đọc số 123456",
            "expected_content": ["đọc là", "một trăm hai mươi ba nghìn"],
            "lesson_id": None 
        },
        {
             "query": "Trung bình cộng là gì",
             "expected_content": ["trung bình cộng", "chia cho số các số hạng"],
             "lesson_id": None
        }
    ]
    
    # Metrics
    metrics = {
        "total": 0,
        "hit_rate_top_1": 0,
        "hit_rate_top_5": 0,
        "mrr": 0.0
    }
    
    for case in test_cases:
        query = case["query"]
        expected_keywords = case["expected_content"]
        
        print(f"\n❓ Query: {query}")
        
        # Get results directly from hybrid_search + rerank layer (skipping context formatting)
        # We use retrieve() but with high K to inspect
        
        # To strictly test the ranking, let's call hybrid_search -> rerank manually similar to retrieve
        candidates = retriever.hybrid_search(query, k=20)
        reranked = retriever.rerank(query, candidates, k=10)
        
        # Check rank
        rank = -1
        found = False
        
        for i, res in enumerate(reranked):
            content = res["text"].lower()
            # Loose match: chunks containing at least one expected keyword phrase
            if any(kw.lower() in content for kw in expected_keywords):
                rank = i + 1
                found = True
                print(f"   ✅ Found at Rank {rank}: {res['text'][:50]}...")
                break
        
        metrics["total"] += 1
        if found:
            metrics["mrr"] += 1.0 / rank
            if rank == 1:
                metrics["hit_rate_top_1"] += 1
            if rank <= 5:
                metrics["hit_rate_top_5"] += 1
        else:
            print("   ❌ Not found in top 10")

    # Aggregation
    if metrics["total"] > 0:
        print("\n" + "="*50)
        print(f"📊 Evaluation Results (N={metrics['total']})")
        print(f"   🎯 Hit Rate @ 1: {metrics['hit_rate_top_1']/metrics['total']:.2f}")
        print(f"   🎯 Hit Rate @ 5: {metrics['hit_rate_top_5']/metrics['total']:.2f}")
        print(f"   ⭐ MRR: {metrics['mrr']/metrics['total']:.2f}")
        print("="*50)
    else:
        print("No test cases run.")

if __name__ == "__main__":
    try:
        evaluate_retrieval()
    except Exception as e:
        print(f"Evaluation failed: {e}")
