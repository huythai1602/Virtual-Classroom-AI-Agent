"""
Advanced Retrieval Pipeline with:
- Hybrid Search (Vector + BM25)
- Cross-Encoder Reranking
- MMR (Maximal Marginal Relevance)
- Query Expansion
"""

from typing import List, Dict, Optional
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from openai import OpenAI
import os
from dotenv import load_dotenv

from database.chunks_repository import search_similar_chunks, get_chunks_by_lesson

load_dotenv()
client = OpenAI()


class AdvancedRetriever:
    """
    Advanced RAG retriever with multiple techniques
    """
    
    def __init__(self, rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize retriever with reranking model
        
        Args:
            rerank_model: HuggingFace cross-encoder model for reranking
        """
        self.reranker = CrossEncoder(rerank_model)
        print(f"✅ Loaded reranker: {rerank_model}")
    
    def get_embedding(self, text: str) -> List[float]:
        """Get OpenAI embedding"""
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    
    def expand_query(self, query: str) -> List[str]:
        """
        Expand query with related keywords (Vietnamese math domain)
        """
        expanded = [query]
        query_lower = query.lower()
        
        # Math domain expansions
        expansions = {
            "phân số": ["tử số", "mẫu số", "phân số tối giản", "rút gọn phân số"],
            "số tự nhiên": ["đọc số", "viết số", "so sánh số", "thứ tự số"],
            "phép tính": ["cộng", "trừ", "nhân", "chia", "tính toán"],
            "hình học": ["góc", "đỉnh", "cạnh", "đo góc", "góc nhọn", "góc vuông"],
            "đo lường": ["độ dài", "khối lượng", "đơn vị đo", "chuyển đổi đơn vị"]
        }
        
        for keyword, related in expansions.items():
            if keyword in query_lower:
                expanded.extend(related)
                break
        
        return list(set(expanded))  # Remove duplicates
    
    def vector_search(
        self, 
        query: str, 
        lesson_id: Optional[str] = None,
        k: int = 20
    ) -> List[Dict]:
        """
        Vector similarity search (first stage - recall)
        
        Returns more candidates for reranking
        """
        query_embedding = self.get_embedding(query)
        results = search_similar_chunks(
            query_embedding=query_embedding,
            lesson_id=lesson_id,
            k=k
        )
        return results
    
    def bm25_search(
        self,
        query: str,
        lesson_id: Optional[str] = None,
        k: int = 10
    ) -> List[Dict]:
        """
        BM25 keyword search for exact matches
        
        Complements vector search for specific terms/formulas
        """
        # Get all chunks from lesson or all chunks
        from database.chunks_repository import get_chunks_by_lesson, get_all_chunks
        
        if lesson_id:
            chunks = get_chunks_by_lesson(lesson_id)
        else:
            chunks = get_all_chunks()  # Need to implement this
        
        if not chunks:
            return []
        
        # Tokenize corpus
        corpus = [chunk["text"] for chunk in chunks]
        tokenized_corpus = [doc.split() for doc in corpus]
        
        # Build BM25 index
        bm25 = BM25Okapi(tokenized_corpus)
        
        # Search
        tokenized_query = query.split()
        scores = bm25.get_scores(tokenized_query)
        
        # Get top-k
        top_indices = np.argsort(scores)[::-1][:k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include relevant results
                chunk = chunks[idx]
                results.append({
                    "chunk_id": chunk["id"],
                    "lesson_id": chunk["lesson_id"],
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                    "bm25_score": float(scores[idx])
                })
        
        return results
    
    def hybrid_search(
        self,
        query: str,
        lesson_id: Optional[str] = None,
        k: int = 20,
        alpha: float = 0.7
    ) -> List[Dict]:
        """
        Hybrid search combining vector + BM25
        
        Args:
            alpha: Weight for vector search (1-alpha for BM25)
                   0.7 = 70% vector, 30% BM25
        """
        # Get results from both methods
        vector_results = self.vector_search(query, lesson_id, k=k)
        bm25_results = self.bm25_search(query, lesson_id, k=k//2)
        
        # Normalize scores to [0, 1]
        if vector_results:
            max_sim = max(r["similarity"] for r in vector_results)
            for r in vector_results:
                r["norm_vector_score"] = r["similarity"] / max_sim if max_sim > 0 else 0
        
        if bm25_results:
            max_bm25 = max(r["bm25_score"] for r in bm25_results)
            for r in bm25_results:
                r["norm_bm25_score"] = r["bm25_score"] / max_bm25 if max_bm25 > 0 else 0
        
        # Combine results with weighted scores
        combined = {}
        
        # Add vector results
        for r in vector_results:
            chunk_id = r["chunk_id"]
            combined[chunk_id] = {
                **r,
                "hybrid_score": alpha * r.get("norm_vector_score", 0)
            }
        
        # Add BM25 results
        for r in bm25_results:
            chunk_id = r["chunk_id"]
            if chunk_id in combined:
                # Already exists, add BM25 score
                combined[chunk_id]["hybrid_score"] += (1 - alpha) * r.get("norm_bm25_score", 0)
            else:
                # New chunk from BM25
                combined[chunk_id] = {
                    **r,
                    "hybrid_score": (1 - alpha) * r.get("norm_bm25_score", 0)
                }
        
        # Sort by hybrid score
        results = sorted(
            combined.values(),
            key=lambda x: x["hybrid_score"],
            reverse=True
        )[:k]
        
        return results
    
    def rerank(
        self,
        query: str,
        candidates: List[Dict],
        k: int = 5
    ) -> List[Dict]:
        """
        Cross-encoder reranking for precision
        
        Args:
            query: User query
            candidates: List of candidate chunks from hybrid search
            k: Number of top results to return
        """
        if not candidates:
            return []
        
        # Prepare pairs for cross-encoder
        pairs = [[query, chunk["text"]] for chunk in candidates]
        
        # Get reranking scores
        rerank_scores = self.reranker.predict(pairs)
        
        # Add scores to candidates
        for chunk, score in zip(candidates, rerank_scores):
            chunk["rerank_score"] = float(score)
        
        # Sort by rerank score
        reranked = sorted(
            candidates,
            key=lambda x: x["rerank_score"],
            reverse=True
        )[:k]
        
        return reranked
    
    def mmr_selection(
        self,
        query: str,
        candidates: List[Dict],
        k: int = 5,
        lambda_param: float = 0.5
    ) -> List[Dict]:
        """
        Maximal Marginal Relevance for diversity
        
        Args:
            lambda_param: Balance between relevance and diversity
                         1.0 = only relevance, 0.0 = only diversity
        """
        if not candidates or len(candidates) <= k:
            return candidates
        
        # Get query embedding
        query_embedding = np.array(self.get_embedding(query))
        
        # Get embeddings for all candidates
        candidate_embeddings = []
        for chunk in candidates:
            emb = self.get_embedding(chunk["text"])
            candidate_embeddings.append(np.array(emb))
        
        candidate_embeddings = np.array(candidate_embeddings)
        
        # MMR algorithm
        selected_indices = []
        remaining_indices = list(range(len(candidates)))
        
        # Select first document (most relevant)
        similarities = np.dot(candidate_embeddings, query_embedding)
        first_idx = np.argmax(similarities)
        selected_indices.append(first_idx)
        remaining_indices.remove(first_idx)
        
        # Select remaining k-1 documents
        while len(selected_indices) < k and remaining_indices:
            mmr_scores = []
            
            for idx in remaining_indices:
                # Relevance to query
                relevance = np.dot(candidate_embeddings[idx], query_embedding)
                
                # Max similarity to already selected
                selected_embeddings = candidate_embeddings[selected_indices]
                similarities_to_selected = np.dot(
                    selected_embeddings,
                    candidate_embeddings[idx]
                )
                max_similarity = np.max(similarities_to_selected)
                
                # MMR score
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                mmr_scores.append(mmr_score)
            
            # Select document with highest MMR score
            best_idx = remaining_indices[np.argmax(mmr_scores)]
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)
        
        # Return selected chunks
        selected = [candidates[idx] for idx in selected_indices]
        
        # Add MMR scores
        for i, chunk in enumerate(selected):
            chunk["mmr_rank"] = i + 1
        
        return selected
    
    def retrieve(
        self,
        query: str,
        lesson_id: Optional[str] = None,
        k: int = None,  # Auto-determine if None
        use_hybrid: bool = True,
        use_rerank: bool = True,
        use_mmr: bool = True,
        expand_query: bool = True,
        intent: str = "normal"
    ) -> List[Dict]:
        """
        Complete retrieval pipeline with token optimization
        
        Pipeline:
        1. Adaptive k selection
        2. Query Expansion (optional)
        3. Hybrid Search (Vector + BM25) or Vector only
        4. Cross-Encoder Reranking
        5. MMR Diversification
        6. Token budget optimization
        
        Args:
            query: User query
            lesson_id: Filter by lesson
            k: Final number of results (auto if None)
            use_hybrid: Use hybrid search (vs vector only)
            use_rerank: Use cross-encoder reranking
            use_mmr: Use MMR for diversity
            expand_query: Expand query with related terms
            intent: Query intent for adaptive k
        """
        # Import token optimizer
        from agent.tools.token_optimizer import get_token_budget
        budget = get_token_budget()
        
        # Step 1: Adaptive k selection
        if k is None:
            k = budget.adaptive_k(query, intent)
        
        # Step 2: Query expansion (limited to avoid token waste)
        queries = self.expand_query(query) if expand_query else [query]
        
        # Step 3: Retrieve candidates (scaled with k)
        all_candidates = []
        candidate_k = min(k * 4, 20)  # Scale candidates with k, max 20
        
        for q in queries[:2]:  # Reduced: 3→2 queries
            if use_hybrid:
                candidates = self.hybrid_search(q, lesson_id, k=candidate_k)
            else:
                candidates = self.vector_search(q, lesson_id, k=candidate_k)
            all_candidates.extend(candidates)
        
        # Remove duplicates by chunk_id
        seen = set()
        unique_candidates = []
        for chunk in all_candidates:
            if chunk["chunk_id"] not in seen:
                seen.add(chunk["chunk_id"])
                unique_candidates.append(chunk)
        
        # Step 4: Reranking
        if use_rerank and unique_candidates:
            unique_candidates = self.rerank(query, unique_candidates, k=min(k*2, 10))
        
        # Step 5: MMR for diversity
        if use_mmr and unique_candidates:
            results = self.mmr_selection(query, unique_candidates, k=k)
        else:
            results = unique_candidates[:k]
        
        # Format for agent
        formatted = []
        for r in results:
            formatted.append({
                "content": r["text"],
                "source": f"Bài {r['lesson_id']} (chunk {r['chunk_index']})",
                "lesson_id": r["lesson_id"],
                "scores": {
                    "similarity": r.get("similarity", 0),
                    "hybrid": r.get("hybrid_score", 0),
                    "rerank": r.get("rerank_score", 0),
                    "mmr_rank": r.get("mmr_rank", 0)
                }
            })
        
        # Step 6: Token budget optimization
        formatted, total_tokens = budget.optimize_chunks(formatted)
        formatted = budget.compress_context(formatted)
        
        return formatted if formatted else [
            {"content": "Không tìm thấy thông tin liên quan.", "source": "system"}
        ]


# Global instance
_retriever_instance = None

def get_retriever() -> AdvancedRetriever:
    """Get or create global retriever instance"""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = AdvancedRetriever()
    return _retriever_instance
