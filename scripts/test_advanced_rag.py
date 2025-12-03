"""
Test Advanced RAG Pipeline
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tools.advanced_retriever import get_retriever
from agent.tools.rag_evaluator import RAGEvaluator
import json


def test_retrieval():
    """Test retrieval with different configurations"""
    
    print("🚀 Testing Advanced RAG Pipeline\n")
    print("="*60)
    
    retriever = get_retriever()
    
    # Test queries
    test_queries = [
        {
            "query": "Phân số là gì?",
            "lesson_id": None,
            "description": "General concept question"
        },
        {
            "query": "Cách đọc số 12345",
            "lesson_id": "toan-lop-4-bai-1",
            "description": "Specific lesson question"
        },
        {
            "query": "Góc nhọn khác góc vuông như thế nào?",
            "lesson_id": None,
            "description": "Comparison question"
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {test['description']}")
        print(f"Query: {test['query']}")
        print(f"Lesson: {test['lesson_id'] or 'All'}")
        print(f"{'='*60}\n")
        
        # Test different configurations
        configs = [
            {"name": "Vector Only", "use_hybrid": False, "use_rerank": False, "use_mmr": False},
            {"name": "Hybrid Search", "use_hybrid": True, "use_rerank": False, "use_mmr": False},
            {"name": "Hybrid + Rerank", "use_hybrid": True, "use_rerank": True, "use_mmr": False},
            {"name": "Full Pipeline", "use_hybrid": True, "use_rerank": True, "use_mmr": True}
        ]
        
        for config in configs:
            print(f"\n📊 {config['name']}:")
            print("-" * 40)
            
            results = retriever.retrieve(
                query=test['query'],
                lesson_id=test['lesson_id'],
                k=3,
                **{k: v for k, v in config.items() if k != 'name'}
            )
            
            for j, result in enumerate(results[:3], 1):
                print(f"{j}. {result['source']}")
                print(f"   Scores: {result.get('scores', {})}")
                print(f"   Preview: {result['content'][:100]}...")
                print()


def benchmark_performance():
    """Benchmark retrieval speed"""
    import time
    
    print("\n" + "="*60)
    print("⏱️  Performance Benchmark")
    print("="*60 + "\n")
    
    retriever = get_retriever()
    query = "Phân số là gì?"
    
    configs = [
        {"name": "Vector Only", "use_hybrid": False, "use_rerank": False, "use_mmr": False},
        {"name": "Full Pipeline", "use_hybrid": True, "use_rerank": True, "use_mmr": True}
    ]
    
    for config in configs:
        times = []
        for _ in range(5):
            start = time.time()
            retriever.retrieve(
                query=query,
                k=5,
                **{k: v for k, v in config.items() if k != 'name'}
            )
            times.append(time.time() - start)
        
        avg_time = sum(times) / len(times)
        print(f"{config['name']}: {avg_time*1000:.1f}ms (avg)")


def create_sample_test_set():
    """Create sample test set for evaluation"""
    
    print("\n" + "="*60)
    print("📝 Creating Sample Test Set")
    print("="*60 + "\n")
    
    sample_test_set = [
        {
            "query": "Phân số là gì?",
            "relevant_chunks": [],  # Fill manually after inspection
            "lesson_id": "toan-lop-4-bai-2",
            "notes": "Should retrieve definition and basic concept"
        },
        {
            "query": "Cách đọc số 12345",
            "relevant_chunks": [],
            "lesson_id": "toan-lop-4-bai-1",
            "notes": "Should retrieve reading numbers section"
        },
        {
            "query": "Góc nhọn là góc có số đo bao nhiêu độ?",
            "relevant_chunks": [],
            "lesson_id": "toan-lop-4-bai-8",
            "notes": "Should retrieve angle definitions"
        }
    ]
    
    output_path = "evaluation/sample_test_set.json"
    Path(output_path).parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sample_test_set, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Created: {output_path}")
    print("\n📝 Next steps:")
    print("1. Retrieve results for each query")
    print("2. Manually inspect and fill in relevant_chunks")
    print("3. Run evaluation with RAGEvaluator")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run retrieval tests")
    parser.add_argument("--benchmark", action="store_true", help="Run performance benchmark")
    parser.add_argument("--create-testset", action="store_true", help="Create sample test set")
    
    args = parser.parse_args()
    
    if args.test or not any([args.test, args.benchmark, args.create_testset]):
        test_retrieval()
    
    if args.benchmark:
        benchmark_performance()
    
    if args.create_testset:
        create_sample_test_set()
    
    print("\n" + "="*60)
    print("✅ Done!")
    print("="*60)
