"""
RAG Evaluation System with Metrics:
- Precision@K, Recall@K
- MRR (Mean Reciprocal Rank)
- NDCG@K (Normalized Discounted Cumulative Gain)
- Hit Rate
"""

from typing import List, Dict, Tuple
import numpy as np
import json
from pathlib import Path


class RAGEvaluator:
    """
    Evaluate RAG retrieval quality
    """
    
    def __init__(self, test_set_path: str = None):
        """
        Initialize evaluator with test dataset
        
        Test set format:
        [
            {
                "query": "Phân số là gì?",
                "relevant_chunks": [123, 456, 789],  # chunk IDs
                "lesson_id": "toan-lop-4-bai-2"
            },
            ...
        ]
        """
        self.test_set = []
        if test_set_path and Path(test_set_path).exists():
            with open(test_set_path, 'r', encoding='utf-8') as f:
                self.test_set = json.load(f)
    
    def precision_at_k(
        self,
        retrieved: List[int],
        relevant: List[int],
        k: int = 5
    ) -> float:
        """
        Precision@K = (relevant retrieved in top-K) / K
        
        Args:
            retrieved: List of retrieved chunk IDs in order
            relevant: List of relevant chunk IDs (ground truth)
            k: Cutoff position
        """
        if k == 0:
            return 0.0
        
        retrieved_at_k = retrieved[:k]
        relevant_retrieved = len(set(retrieved_at_k) & set(relevant))
        
        return relevant_retrieved / k
    
    def recall_at_k(
        self,
        retrieved: List[int],
        relevant: List[int],
        k: int = 5
    ) -> float:
        """
        Recall@K = (relevant retrieved in top-K) / total relevant
        """
        if len(relevant) == 0:
            return 0.0
        
        retrieved_at_k = retrieved[:k]
        relevant_retrieved = len(set(retrieved_at_k) & set(relevant))
        
        return relevant_retrieved / len(relevant)
    
    def mean_reciprocal_rank(
        self,
        retrieved: List[int],
        relevant: List[int]
    ) -> float:
        """
        MRR = 1 / rank of first relevant document
        
        Example:
            Retrieved: [100, 200, 300, 400]
            Relevant: [300, 500]
            First relevant at position 3 → MRR = 1/3 = 0.333
        """
        for i, chunk_id in enumerate(retrieved, 1):
            if chunk_id in relevant:
                return 1.0 / i
        return 0.0
    
    def ndcg_at_k(
        self,
        retrieved: List[int],
        relevant: List[int],
        k: int = 5
    ) -> float:
        """
        NDCG@K = DCG@K / IDCG@K
        
        DCG = sum(rel_i / log2(i+1)) for i in [1, k]
        IDCG = DCG of ideal ranking
        """
        retrieved_at_k = retrieved[:k]
        
        # Calculate DCG
        dcg = 0.0
        for i, chunk_id in enumerate(retrieved_at_k, 1):
            relevance = 1.0 if chunk_id in relevant else 0.0
            dcg += relevance / np.log2(i + 1)
        
        # Calculate IDCG (ideal DCG)
        ideal_relevances = [1.0] * min(len(relevant), k) + [0.0] * (k - len(relevant))
        idcg = sum(rel / np.log2(i + 2) for i, rel in enumerate(ideal_relevances))
        
        if idcg == 0:
            return 0.0
        
        return dcg / idcg
    
    def hit_rate_at_k(
        self,
        retrieved: List[int],
        relevant: List[int],
        k: int = 5
    ) -> float:
        """
        Hit Rate@K = 1 if at least one relevant doc in top-K, else 0
        """
        retrieved_at_k = retrieved[:k]
        return 1.0 if any(chunk_id in relevant for chunk_id in retrieved_at_k) else 0.0
    
    def evaluate_query(
        self,
        retrieved: List[int],
        relevant: List[int],
        k: int = 5
    ) -> Dict[str, float]:
        """
        Evaluate single query with all metrics
        """
        return {
            f"precision@{k}": self.precision_at_k(retrieved, relevant, k),
            f"recall@{k}": self.recall_at_k(retrieved, relevant, k),
            "mrr": self.mean_reciprocal_rank(retrieved, relevant),
            f"ndcg@{k}": self.ndcg_at_k(retrieved, relevant, k),
            f"hit_rate@{k}": self.hit_rate_at_k(retrieved, relevant, k)
        }
    
    def evaluate_retriever(
        self,
        retriever_fn,
        k: int = 5
    ) -> Dict[str, float]:
        """
        Evaluate retriever on full test set
        
        Args:
            retriever_fn: Function(query, lesson_id, k) -> List[chunk_ids]
            k: Cutoff for metrics
        
        Returns:
            Average metrics across all test queries
        """
        if not self.test_set:
            raise ValueError("No test set loaded!")
        
        all_metrics = []
        
        for test_case in self.test_set:
            query = test_case["query"]
            relevant = test_case["relevant_chunks"]
            lesson_id = test_case.get("lesson_id")
            
            # Retrieve
            results = retriever_fn(query, lesson_id, k)
            retrieved = [r["chunk_id"] for r in results]
            
            # Evaluate
            metrics = self.evaluate_query(retrieved, relevant, k)
            all_metrics.append(metrics)
        
        # Average metrics
        avg_metrics = {}
        for key in all_metrics[0].keys():
            avg_metrics[key] = np.mean([m[key] for m in all_metrics])
        
        # Add count
        avg_metrics["num_queries"] = len(self.test_set)
        
        return avg_metrics
    
    def compare_retrievers(
        self,
        retrievers: Dict[str, callable],
        k: int = 5
    ) -> Dict[str, Dict]:
        """
        Compare multiple retriever configurations
        
        Args:
            retrievers: {
                "baseline": retriever_fn,
                "with_rerank": retriever_fn,
                "with_mmr": retriever_fn
            }
        
        Returns:
            {
                "baseline": {metrics},
                "with_rerank": {metrics},
                ...
            }
        """
        results = {}
        
        for name, retriever_fn in retrievers.items():
            print(f"\n📊 Evaluating: {name}")
            metrics = self.evaluate_retriever(retriever_fn, k)
            results[name] = metrics
            
            # Print metrics
            print(f"   Precision@{k}: {metrics[f'precision@{k}']:.3f}")
            print(f"   Recall@{k}: {metrics[f'recall@{k}']:.3f}")
            print(f"   MRR: {metrics['mrr']:.3f}")
            print(f"   NDCG@{k}: {metrics[f'ndcg@{k}']:.3f}")
            print(f"   Hit Rate@{k}: {metrics[f'hit_rate@{k}']:.3f}")
        
        return results
    
    def create_test_set_template(
        self,
        output_path: str,
        num_examples: int = 10
    ):
        """
        Create template for manual test set creation
        """
        template = []
        
        for i in range(num_examples):
            template.append({
                "query": f"Example query {i+1}",
                "relevant_chunks": [1, 2, 3],  # Replace with actual chunk IDs
                "lesson_id": "toan-lop-4-bai-1",
                "notes": "Add notes about expected answer"
            })
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Created test set template: {output_path}")
    
    def save_results(
        self,
        results: Dict,
        output_path: str
    ):
        """Save evaluation results to file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Saved results: {output_path}")


# Example usage
if __name__ == "__main__":
    # Create test set template
    evaluator = RAGEvaluator()
    evaluator.create_test_set_template("evaluation/test_set.json", num_examples=20)
    
    print("\n📝 Next steps:")
    print("1. Fill in test_set.json with real queries and relevant chunks")
    print("2. Run evaluation: python -m agent.tools.rag_evaluator")
