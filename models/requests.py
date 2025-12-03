"""Request models"""
from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """Chat request model"""
    userMessage: str = Field(..., description="User message", min_length=1, alias="userMessage")
    lessonId: Optional[int] = Field(None, description="Lesson ID (integer)", alias="lessonId")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "userMessage": "Phân số là gì?",
                "lessonId": 2
            }
        }


class MindmapRequest(BaseModel):
    """Mindmap generation request"""
    topic: str = Field(..., description="Topic for mindmap", min_length=1)
    lessonId: Optional[int] = Field(None, description="Lesson ID (integer)", alias="lessonId")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "topic": "Phân số",
                "lessonId": 2
            }
        }


class AnalyzerRequest(BaseModel):
    """Session analysis request"""
    topic: str = Field(..., description="Topic to analyze", min_length=1)
    lessonId: Optional[int] = Field(None, description="Lesson ID (integer)", alias="lessonId")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "topic": "Phân số",
                "lessonId": 2
            }
        }
