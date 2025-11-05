"""
Retriever tool - Truy vấn ngữ cảnh từ ChromaDB
"""
import os
from typing import List, Dict
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.tools import tool

# Load environment variables
load_dotenv()

# Đường dẫn đến ChromaDB
CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chroma_db")

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
    
    def retrieve(self, query: str, k: int = 3, lesson_id: str = None) -> List[str]:
        """
        Truy vấn các đoạn nội dung liên quan từ vector store
        
        Args:
            query: Câu hỏi/truy vấn
            k: Số lượng kết quả trả về
            lesson_id: ID của bài giảng (filter theo metadata)
            
        Returns:
            List các đoạn nội dung liên quan
        """
        if self.vectorstore is None:
            return ["Chưa có dữ liệu bài giảng trong hệ thống."]
        
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
            
            return [doc.page_content for doc in docs]
        except Exception as e:
            print(f"Lỗi khi truy vấn: {e}")
            return ["Không thể truy vấn dữ liệu bài giảng."]

# Khởi tạo retriever toàn cục
_retriever = RetrieverTool()

@tool
def retrieve_context(query: str, lesson_id: str = None) -> str:
    """
    Truy vấn ngữ cảnh từ transcript bài giảng Toán lớp 4.
    
    Args:
        query: Câu hỏi hoặc chủ đề cần tìm thông tin
        lesson_id: ID của bài giảng (tùy chọn)
        
    Returns:
        Nội dung liên quan từ bài giảng
    """
    results = _retriever.retrieve(query, k=3, lesson_id=lesson_id)
    return "\n\n".join(results)

def get_context(query: str, k: int = 3, lesson_id: str = None) -> str:
    """
    Hàm helper để lấy ngữ cảnh (không dùng decorator @tool)
    
    Args:
        query: Câu hỏi hoặc chủ đề cần tìm thông tin
        k: Số lượng kết quả
        lesson_id: ID của bài giảng (tùy chọn)
        
    Returns:
        Nội dung liên quan từ bài giảng
    """
    results = _retriever.retrieve(query, k=k, lesson_id=lesson_id)
    return "\n\n".join(results)
