"""
Script xây dựng ChromaDB vector store từ transcript files
Chạy script này để tạo vector store từ các file transcript trong data/transcripts/
"""
import os
from pathlib import Path
from typing import List
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_core.documents import Document
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Đường dẫn
BASE_DIR = Path(__file__).parent.parent
TRANSCRIPTS_DIR = BASE_DIR / "data" / "transcripts"
CHROMA_DB_PATH = BASE_DIR / "chroma_db"


def load_documents_from_directory(directory: Path) -> List[Document]:
    """
    Load tất cả documents từ thư mục transcripts
    Hỗ trợ .txt và .pdf files
    Thêm metadata: lesson_id, lesson_name
    """
    documents = []
    
    if not directory.exists():
        print(f"Thư mục {directory} không tồn tại!")
        return documents
    
    # Lấy tất cả files trong thư mục
    files = list(directory.glob("*"))
    
    if not files:
        print(f"Không tìm thấy file nào trong {directory}")
        return documents
    
    for file_path in files:
        try:
            if file_path.suffix == ".txt":
                loader = TextLoader(str(file_path), encoding="utf-8")
                docs = loader.load()
                
                # Thêm metadata cho mỗi document
                lesson_id = file_path.stem  # Tên file không có extension
                for doc in docs:
                    doc.metadata["lesson_id"] = lesson_id
                    doc.metadata["lesson_name"] = file_path.name
                    doc.metadata["source"] = str(file_path)
                
                documents.extend(docs)
                print(f"Đã load: {file_path.name} (lesson_id: {lesson_id})")
            
            elif file_path.suffix == ".pdf":
                loader = PyPDFLoader(str(file_path))
                docs = loader.load()
                
                # Thêm metadata cho mỗi document
                lesson_id = file_path.stem
                for doc in docs:
                    doc.metadata["lesson_id"] = lesson_id
                    doc.metadata["lesson_name"] = file_path.name
                    doc.metadata["source"] = str(file_path)
                
                documents.extend(docs)
                print(f"Đã load: {file_path.name} (lesson_id: {lesson_id})")
            
            else:
                print(f"Bỏ qua file không hỗ trợ: {file_path.name}")
        
        except Exception as e:
            print(f"Lỗi khi load {file_path.name}: {e}")
    
    return documents


def split_documents(documents: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
    """
    Chia nhỏ documents thành các chunks
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_documents(documents)
    print(f"Đã chia thành {len(chunks)} chunks")
    return chunks


def build_vector_store(documents: List[Document], persist_directory: Path):
    """
    Xây dựng và lưu ChromaDB vector store
    """
    # Khởi tạo embeddings
    embeddings = OpenAIEmbeddings()
    
    # Tạo vector store
    print("Đang tạo embeddings và lưu vào ChromaDB...")
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=str(persist_directory)
    )
    
    print(f"Đã lưu vector store tại: {persist_directory}")
    return vectorstore


def main():
    """
    Hàm chính để build vector store
    """
    print("=" * 60)
    print("XÂY DỰNG CHROMADB VECTOR STORE")
    print("=" * 60)
    
    # Kiểm tra API key
    if not os.getenv("OPENAI_API_KEY"):
        print("CẢNH BÁO: OPENAI_API_KEY chưa được thiết lập trong .env")
        return
    
    # Load documents
    print(f"\n1. Load documents từ {TRANSCRIPTS_DIR}")
    documents = load_documents_from_directory(TRANSCRIPTS_DIR)
    
    if not documents:
        print("Không có document nào để xử lý!")
        print(f"Vui lòng thêm file .txt hoặc .pdf vào thư mục: {TRANSCRIPTS_DIR}")
        return
    
    print(f"Đã load {len(documents)} documents")
    
    # Split documents
    print("\n2. Chia nhỏ documents thành chunks")
    chunks = split_documents(documents)
    
    # Build vector store
    print("\n3. Xây dựng vector store")
    build_vector_store(chunks, CHROMA_DB_PATH)
    
    print("\n" + "=" * 60)
    print("HOÀN THÀNH!")
    print("=" * 60)
    print(f"Vector store đã được lưu tại: {CHROMA_DB_PATH}")
    print(f"Tổng số documents: {len(documents)}")
    print(f"Tổng số chunks: {len(chunks)}")


if __name__ == "__main__":
    main()
