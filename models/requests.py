"""Request models"""
from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """Chat request model"""
    question: str = Field(..., description="User question", min_length=1)
    lesson_id: Optional[int] = Field(None, description="Lesson ID (integer)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Cho em hỏi số 12345 có mấy chữ số?",
                "lesson_id": 1
            }
        }


class MindmapRequest(BaseModel):
    """Mindmap generation request"""
    topic: str = Field(..., description="Topic for mindmap", min_length=1)
    lesson_id: Optional[int] = Field(None, description="Lesson ID (integer)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Phân số",
                "lesson_id": 2
            }
        }


class AnalyzerRequest(BaseModel):
    """Session analysis request - no body needed, uses JWT user_id"""
    lesson_id: Optional[int] = Field(None, description="Lesson ID (integer)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "lesson_id": 1
            }
        }
