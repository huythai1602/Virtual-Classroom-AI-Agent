"""
Centralized configuration for the application
"""
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    APP_NAME: str = "Agentic RAG - Trợ giảng Toán lớp 4"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    
    # Database
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", 5432))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "virtual_classroom")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "agent_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    

    
    # RabbitMQ
    RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "")
    RABBITMQ_OUT_QUEUE: str = os.getenv("RABBITMQ_OUT_QUEUE", "ai_to_course") 
    RABBITMQ_IN_QUEUE: str = os.getenv("RABBITMQ_IN_QUEUE", "course_to_ai")
    RABBITMQ_TIMEOUT: int = 15 # seconds for RPC timeout
    
    # JWT Authentication
    # Support both JWT_SECRET (common) and JWT_SECRET_KEY
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET") or "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    
    # RAG Configuration
    MAX_CONTEXT_TOKENS: int = 2700
    DEFAULT_TOP_K: int = 3
    HYBRID_ALPHA: float = 0.7  # 70% vector, 30% BM25
    SEMANTIC_THRESHOLD: float = 0.85
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    
    # Cohere Rerank API (replaces local sentence-transformers)
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",          # React dev
        "http://localhost:5173",          # Vite dev
        "http://localhost:5174",          # Vite dev (alternative)
        "https://virtual-classroom-ai-agent-production.up.railway.app",  # Backend Railway
        "https://doan2025-production-f7c9.up.railway.app",  # Frontend Railway
        # Add more origins via env var
        os.getenv("FRONTEND_URL", "")
    ]
    
    class Config:
        case_sensitive = True


settings = Settings()

# Validate critical settings
if not settings.OPENAI_API_KEY:
    print("⚠️ WARNING: OPENAI_API_KEY not set!")
if not settings.POSTGRES_PASSWORD:
    print("⚠️ WARNING: POSTGRES_PASSWORD not set!")
