"""
Retriever tool - Truy vấn ngữ cảnh từ ChromaDB với Smart Query Expansion
"""
import os
import re
from typing import List, Dict
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.tools import tool

# Load environment variables
load_dotenv()

# Đường dẫn đến ChromaDB
CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chroma_db")

# Topic Expansion Map - Mapping keywords to related concepts
TOPIC_EXPANSIONS = {
    r"chữ số|hàng": "hàng đơn vị hàng chục hàng trăm hàng nghìn hàng vạn giá trị vị trí số đọc số viết số",
    r"phân số|tử|mẫu": "phân số tử số mẫu số rút gọn so sánh phân số quy đồng",
    r"cộng|trừ|nhân|chia|tính": "phép tính phép cộng phép trừ phép nhân phép chia tổng hiệu tích thương",
    r"số chẵn|số lẻ": "số chẵn số lẻ chia hết dư phép chia",
    r"làm tròn": "làm tròn số gần đúng ước lượng",
    r"hình|chu vi|diện tích": "hình học hình chữ nhật hình vuông chu vi diện tích",
}

class RetrieverTool:
    """Class quản lý việc truy vấn vector store"""
    
    def __init__(self, db_path: str = CHROMA_DB_PATH):
        self.db_path = db_path
        self.vectorstore = None
        self._initialize_vectorstore()
    
    def _initialize_vectorstore(self):
        """Khởi tạo vector store từ ChromaDB"""
        try:
            embeddings = OpenAIEmbeddings()
            self.vectorstore = Chroma(
                persist_directory=self.db_path,
                embedding_function=embeddings
            )
        except Exception as e:
            print(f"Lỗi khi khởi tạo vectorstore: {e}")
            self.vectorstore = None
    
    def retrieve(self, query: str, k: int = 3, lesson_id: str = None) -> List[Dict]:
        """
        Truy vấn các đoạn nội dung liên quan từ vector store với metadata
        
        Args:
            query: Câu hỏi/truy vấn
            k: Số lượng kết quả trả về
            lesson_id: ID của bài giảng (filter theo metadata)
            
        Returns:
            List các dict chứa content và metadata (source, lesson_id)
        """
        if self.vectorstore is None:
            return [{"content": "Chưa có dữ liệu bài giảng trong hệ thống.", "source": "system"}]
        
        try:
            # Nếu có lesson_id, filter theo metadata
            if lesson_id:
                docs = self.vectorstore.similarity_search(
                    query, 
                    k=k,
                    filter={"lesson_id": lesson_id}
                )
            else:
                docs = self.vectorstore.similarity_search(query, k=k)
            
            # Trả về content + metadata
            results = []
            for doc in docs:
                results.append({
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "unknown"),
                    "lesson_id": doc.metadata.get("lesson_id", "")
                })
            return results
        except Exception as e:
            print(f"Lỗi khi truy vấn: {e}")
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
