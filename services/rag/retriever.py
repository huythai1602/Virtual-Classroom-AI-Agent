"""
RAG Retrieval Service
Consolidated from agent/tools/advanced_retriever.py
Refactored to use core.text_processing
"""
from typing import List, Dict, Optional, Union
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from config.settings import settings
from core.text_processing import TextProcessor

class RAGRetriever:
    """Advanced RAG retriever with hybrid search, reranking, and semantic chunking"""
    
    def __init__(self):
        self.reranker = CrossEncoder(settings.RERANK_MODEL)
        self.processor = TextProcessor()
        print(f"✅ RAG Retriever initialized")
    
    def adaptive_k(self, query: str, intent: str = "normal") -> int:
        """Adaptive k based on intent and query complexity"""
        if intent == "deep":
            return 5
        elif intent == "normal":
            if len(query) > 100:
                return 4
            return 3
        return settings.DEFAULT_TOP_K
    
    def vector_search(
        self,
        query: str,
        lesson_id: Optional[Union[str, int]] = None,
        k: int = 20
    ) -> List[Dict]:
        """Vector similarity search"""
        from repositories.chunks import search_similar_chunks
        
        query_embedding = self.processor.get_embedding(query)
        results = search_similar_chunks(
            query_embedding=query_embedding,
            lesson_id=lesson_id,
            k=k
        )
        return results
    
    def bm25_search(
        self,
        query: str,
        lesson_id: Optional[Union[str, int]] = None,
        k: int = 10
    ) -> List[Dict]:
        """BM25 keyword search"""
        from repositories.chunks import get_chunks_by_lesson, get_all_chunks
        
        chunks = get_chunks_by_lesson(lesson_id) if lesson_id else get_all_chunks()
        if not chunks:
            return []
        
        # Build BM25 index
        corpus = [chunk["text"] for chunk in chunks]
        tokenized_corpus = [self.processor.tokenize(doc) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        
        # Search
        tokenized_query = self.processor.tokenize(query)
        scores = bm25.get_scores(tokenized_query)
        
        # Top-k
        top_indices = np.argsort(scores)[::-1][:k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
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
        lesson_id: Optional[Union[str, int]] = None,
        k: int = 20
    ) -> List[Dict]:
        """Hybrid: 70% vector + 30% BM25"""
        alpha = settings.HYBRID_ALPHA
        
        vector_results = self.vector_search(query, lesson_id, k=k)
        bm25_results = self.bm25_search(query, lesson_id, k=k//2)
        
        # Normalize scores
        if vector_results:
            max_sim = max(r["similarity"] for r in vector_results)
            for r in vector_results:
                r["norm_vector"] = r["similarity"] / max_sim if max_sim > 0 else 0
        
        if bm25_results:
            max_bm25 = max(r["bm25_score"] for r in bm25_results)
            for r in bm25_results:
                r["norm_bm25"] = r["bm25_score"] / max_bm25 if max_bm25 > 0 else 0
        
        # Combine
        combined = {}
        for r in vector_results:
            chunk_id = r["chunk_id"]
            combined[chunk_id] = {
                **r,
                "hybrid_score": alpha * r.get("norm_vector", 0)
            }
        
        for r in bm25_results:
            chunk_id = r["chunk_id"]
            if chunk_id in combined:
                combined[chunk_id]["hybrid_score"] += (1 - alpha) * r.get("norm_bm25", 0)
            else:
                combined[chunk_id] = {
                    **r,
                    "hybrid_score": (1 - alpha) * r.get("norm_bm25", 0)
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
        """Cross-encoder reranking"""
        if not candidates:
            return []
        
        pairs = [[query, chunk["text"]] for chunk in candidates]
        rerank_scores = self.reranker.predict(pairs)
        
        for chunk, score in zip(candidates, rerank_scores):
            chunk["rerank_score"] = float(score)
        
        return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:k]
    
    def mmr_selection(
        self,
        query: str,
        candidates: List[Dict],
        k: int = 5,
        lambda_param: float = 0.5
    ) -> List[Dict]:
        """Maximal Marginal Relevance for diversity"""
        if not candidates or len(candidates) <= k:
            return candidates
        
        query_embedding = np.array(self.processor.get_embedding(query))
        candidate_embeddings = np.array([
            self.processor.get_embedding(chunk["text"]) for chunk in candidates
        ])
        
        selected_indices = []
        remaining_indices = list(range(len(candidates)))
        
        # First: most relevant
        similarities = np.dot(candidate_embeddings, query_embedding)
        first_idx = np.argmax(similarities)
        selected_indices.append(first_idx)
        remaining_indices.remove(first_idx)
        
        # Select remaining with MMR
        while len(selected_indices) < k and remaining_indices:
            mmr_scores = []
            
            for idx in remaining_indices:
                relevance = np.dot(candidate_embeddings[idx], query_embedding)
                selected_embeddings = candidate_embeddings[selected_indices]
                similarities_to_selected = np.dot(selected_embeddings, candidate_embeddings[idx])
                max_similarity = np.max(similarities_to_selected)
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                mmr_scores.append(mmr_score)
            
            best_idx = remaining_indices[np.argmax(mmr_scores)]
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)
        
        return [candidates[idx] for idx in selected_indices]
    
    def retrieve(
        self,
        query: str,
        lesson_id: Optional[Union[str, int]] = None,
        k: Optional[int] = None,
        intent: str = "normal",
        use_semantic_chunking: bool = True
    ) -> str:
        """
        Complete retrieval pipeline with semantic chunking
        Returns formatted context string
        """
        # Adaptive k
        if k is None:
            k = self.adaptive_k(query, intent)
        
        # Hybrid search
        candidates = self.hybrid_search(query, lesson_id, k=k*4)
        
        # Rerank
        candidates = self.rerank(query, candidates, k=k*2)
        
        # MMR for diversity
        results = self.mmr_selection(query, candidates, k=k)
        
        # Apply semantic chunking to results if enabled
        # Note: We re-chunk the retrieved chunks to find the exact best snippet
        if use_semantic_chunking:
            refined_results = []
            for r in results:
                semantic_chunks = self.processor.semantic_chunk(r["text"])
                
                # Re-evaluate each semantic chunk against query
                for chunk_text in semantic_chunks:
                    refined_results.append({
                        **r,
                        "text": chunk_text,
                        "original_text": r["text"],
                        "is_semantic_chunk": True
                    })
            
            # Re-rank semantic chunks
            if refined_results:
                results = self.rerank(query, refined_results, k=k*2)[:k]
        
        # Format with token budget
        formatted_chunks = []
        total_tokens = 0
        
        for r in results:
            content = r["text"]
            tokens = self.processor.count_tokens(content)
            
            if total_tokens + tokens > settings.MAX_CONTEXT_TOKENS:
                if total_tokens < settings.MAX_CONTEXT_TOKENS:
                    remaining = settings.MAX_CONTEXT_TOKENS - total_tokens
                    # Crude truncation to fit
                    content = content[:remaining * 4] 
                    total_tokens = settings.MAX_CONTEXT_TOKENS
                else:
                    break
            else:
                total_tokens += tokens
            
            formatted_chunks.append({
                "content": content,
                "source": f"Bài {r['lesson_id']} (chunk {r['chunk_index']})"
            })
            
            if total_tokens >= settings.MAX_CONTEXT_TOKENS:
                break
        
        # Format as string
        if not formatted_chunks:
            return "Không tìm thấy thông tin liên quan."
        
        context_parts = []
        for i, chunk in enumerate(formatted_chunks, 1):
            context_parts.append(f"[Nguồn {i}: {chunk['source']}]\n{chunk['content']}")
        
        return "\n\n".join(context_parts)

# Global instance
_retriever = None

def get_retriever() -> RAGRetriever:
    """Get global retriever instance"""
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever

def get_context(
    query: str,
    lesson_id: Optional[Union[str, int]] = None,
    k: Optional[int] = None,
    intent: str = "normal"
) -> str:
    """Convenience function for retrieval"""
    retriever = get_retriever()
    return retriever.retrieve(query, lesson_id=lesson_id, k=k, intent=intent)
