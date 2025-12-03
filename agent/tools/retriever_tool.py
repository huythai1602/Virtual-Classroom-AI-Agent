"""
Retriever tool - Truy vấn ngữ cảnh từ PostgreSQL + pgvector với Smart Query Expansion
"""
import os
import re
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI
from langchain_core.tools import tool
from database.chunks_repository import search_similar_chunks

# Load environment variables
load_dotenv()

# OpenAI client for embeddings
client = OpenAI()

# Topic Expansion Map - Mapping keywords to related concepts
TOPIC_EXPANSIONS = {
    r"chữ số|hàng|thuộc hàng": "hàng đơn vị hàng chục hàng trăm hàng nghìn hàng chục nghìn giá trị vị trí số đọc số viết số xác định hàng chữ số thuộc hàng nào",
    r"phân số|tử|mẫu": "phân số tử số mẫu số rút gọn so sánh phân số quy đồng",
    r"cộng|trừ|nhân|chia|tính|cách cộng|cách trừ": "phép tính phép cộng phép trừ phép nhân phép chia tổng hiệu tích thương cách cộng cách trừ cách nhân cách chia",
    r"số chẵn|số lẻ": "số chẵn số lẻ chia hết dư phép chia",
    r"làm tròn": "làm tròn số gần đúng ước lượng",
    r"hình|chu vi|diện tích": "hình học hình chữ nhật hình vuông chu vi diện tích",
}

def get_embedding(text: str) -> list:
    """Get OpenAI embedding for text"""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Lỗi khi tạo embedding: {e}")
        raise


class RetrieverTool:
    """
    Retriever tool using advanced RAG pipeline
    
    Features:
    - Hybrid Search (Vector + BM25)
    - Cross-Encoder Reranking  
    - MMR Diversification
    - Query Expansion
    """
    
    def __init__(self):
        # Import here to avoid circular dependency
        from agent.tools.advanced_retriever import get_retriever
        self._advanced_retriever = None
    
    @property
    def advanced_retriever(self):
        """Lazy load advanced retriever"""
        if self._advanced_retriever is None:
            from agent.tools.advanced_retriever import get_retriever
            self._advanced_retriever = get_retriever()
        return self._advanced_retriever
    
    def retrieve(
        self, 
        query: str, 
        k: int = 3, 
        lesson_id: str = None,
        use_advanced: bool = True
    ) -> List[Dict]:
        """
        Retrieve relevant chunks using advanced RAG pipeline
        
        Args:
            query: User query
            k: Number of results
            lesson_id: Filter by lesson
            use_advanced: Use advanced retriever (hybrid+rerank+mmr)
            
        Returns:
            List of relevant chunks with metadata
        """
        try:
            if use_advanced:
                # Use advanced retriever with all features
                results = self.advanced_retriever.retrieve(
                    query=query,
                    lesson_id=lesson_id,
                    k=k,
                    use_hybrid=True,
                    use_rerank=True,
                    use_mmr=True,
                    expand_query=True
                )
                return results
            else:
                # Fallback to simple vector search
                query_embedding = get_embedding(query)
                results = search_similar_chunks(
                    query_embedding=query_embedding,
                    lesson_id=lesson_id,
                    k=k
                )
                
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "content": result["text"],
                        "source": f"Bài {result['lesson_id']} (chunk {result['chunk_index']})",
                        "lesson_id": result["lesson_id"],
                        "similarity": result["similarity"]
                    })
                
                return formatted_results if formatted_results else [
                    {"content": "Không tìm thấy thông tin liên quan.", "source": "system"}
                ]
            
        except Exception as e:
            print(f"Lỗi khi truy vấn: {e}")
            import traceback
            traceback.print_exc()
            return [{"content": "Không thể truy vấn dữ liệu bài giảng.", "source": "error"}]

def expand_query(query: str) -> List[str]:
    """
    Mở rộng query với các keywords liên quan
    
    Args:
        query: Câu hỏi gốc
        
    Returns:
        List các query đã expand
    """
    expanded = [query]  # Luôn giữ query gốc
    
    query_lower = query.lower()
    
    # Check từng pattern
    for pattern, expansion in TOPIC_EXPANSIONS.items():
        if re.search(pattern, query_lower):
            expanded.append(expansion)
            break  # Chỉ lấy 1 expansion phù hợp nhất
    
    return expanded


def deduplicate_results(results: List[Dict]) -> List[Dict]:
    """
    Loại bỏ duplicate results dựa trên content
    
    Args:
        results: List các results
        
    Returns:
        List đã deduplicate
    """
    seen_contents = set()
    unique_results = []
    
    for result in results:
        content = result.get("content", "")
        # Dùng 100 ký tự đầu để check duplicate
        content_hash = content[:100]
        
        if content_hash not in seen_contents:
            seen_contents.add(content_hash)
            unique_results.append(result)
    
    return unique_results


def get_context_smart(query: str, k: int = 10, lesson_id: str = None) -> str:
    """
    Retrieve thông minh với query expansion
    
    Args:
        query: Câu hỏi gốc
        k: Số lượng results mong muốn
        lesson_id: ID của bài giảng (optional)
        
    Returns:
        Context đã format với trích dẫn
    """
    # Expand query
    expanded_queries = expand_query(query)
    
    all_results = []
    
    # Retrieve với mỗi expanded query
    k_per_query = max(k // len(expanded_queries), 3)
    
    for q in expanded_queries:
        results = _retriever.retrieve(q, k=k_per_query, lesson_id=lesson_id)
        all_results.extend(results)
    
    # Deduplicate
    unique_results = deduplicate_results(all_results)
    
    # Lấy top k results
    top_results = unique_results[:k]
    
    # Format với trích dẫn nguồn
    formatted_results = []
    for i, result in enumerate(top_results, 1):
        source = result.get("source", "unknown")
        content = result.get("content", "")
        formatted_results.append(f"[Nguồn {i}: {source}]\n{content}")
    
    return "\n\n".join(formatted_results)


# Khởi tạo retriever toàn cục
_retriever = RetrieverTool()

@tool
def retrieve_context(query: str, lesson_id: str = None) -> str:
    """
    Truy vấn ngữ cảnh từ transcript bài giảng Toán lớp 4 với trích dẫn nguồn.
    
    Args:
        query: Câu hỏi hoặc chủ đề cần tìm thông tin
        lesson_id: ID của bài giảng (tùy chọn)
        
    Returns:
        Nội dung liên quan từ bài giảng kèm nguồn trích dẫn
    """
    results = _retriever.retrieve(query, k=3, lesson_id=lesson_id)
    
    # Format với trích dẫn nguồn
    formatted_results = []
    for i, result in enumerate(results, 1):
        source = result.get("source", "unknown")
        content = result.get("content", "")
        formatted_results.append(f"[Nguồn {i}: {source}]\n{content}")
    
    return "\n\n".join(formatted_results)

def get_context(query: str, k: int = 3, lesson_id: str = None) -> str:
    """
    Hàm helper để lấy ngữ cảnh với trích dẫn nguồn
    
    Args:
        query: Câu hỏi hoặc chủ đề cần tìm thông tin
        k: Số lượng kết quả
        lesson_id: ID của bài giảng (tùy chọn)
        
    Returns:
        Nội dung liên quan từ bài giảng kèm nguồn trích dẫn
    """
    results = _retriever.retrieve(query, k=k, lesson_id=lesson_id)
    
    # Format với trích dẫn nguồn
    formatted_results = []
    for i, result in enumerate(results, 1):
        source = result.get("source", "unknown")
        content = result.get("content", "")
        formatted_results.append(f"[Nguồn {i}: {source}]\n{content}")
    
    return "\n\n".join(formatted_results)
