"""Response models with standard wrapper"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Generic, TypeVar
from datetime import datetime

T = TypeVar('T')


class StandardResponse(BaseModel, Generic[T]):
    """Standard API response wrapper"""
    status: str = Field(..., description="Response status: success or error")
    data: Optional[T] = Field(None, description="Response data")
    message: str = Field(..., description="Response message")
    createdAt: str = Field(..., description="ISO 8601 timestamp", alias="createdAt")
    
    class Config:
        populate_by_name = True
    class Config:
        populate_by_name = True


class ChatData(BaseModel):
    """Chat response data structure"""
    reply: str = Field(..., description="The AI's full response")
    intent: str = Field("normal", description="Detected intent (normal/deep)")
    createdAt: str = Field(..., description="Response timestamp", alias="createdAt")
    # threadId removed as per user request
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "reply": "Chào em, hôm nay chúng ta sẽ ôn tập về các số đến 100000 nhé! Em đã sẵn sàng chưa?",
                "intent": "normal",
                "createdAt": "2025-12-15T12:00:00Z"
            }
        }


class MindmapData(BaseModel):
    """Mindmap data structure"""
    mindmap: Dict[str, Any] = Field(..., description="React Flow compatible mindmap JSON")
    topic: str = Field(..., description="Mindmap topic")
    
    class Config:
        json_schema_extra = {
            "example": {
                "mindmap": {
                    "nodes": [{"id": "1", "data": {"label": "Phân số"}, "position": {"x": 0, "y": 0}}],
                    "edges": []
                },
                "topic": "Phân số"
            }
        }


class AnalyzerData(BaseModel):
    """Analyzer data structure"""
    analysis: str = Field(..., description="Detailed analysis of student's understanding")
    level: str = Field(..., description="Student's proficiency level")
    levelReason: str = Field(..., description="Reason for the assessed level", alias="levelReason")
    quizStats: Optional[Dict[str, Any]] = Field(None, description="Detailed quiz statistics", alias="quizStats")
    threadId: str = Field(..., description="Session thread ID", alias="threadId")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "analysis": "Học sinh đã nắm vững khái niệm phân số. Tuy nhiên, cần rèn luyện thêm về kỹ năng quy đồng mẫu số. Thông qua các câu trả lời, em cho thấy khả năng tư duy logic tốt nhưng còn vội vàng.",
                "level": "Khá",
                "levelReason": "Trả lời đúng 80% câu hỏi về lý thuyết, nhưng sai ở bài tập vận dụng cao.",
                "threadId": "user_123_session_abc"
            }
        }


class LessonItem(BaseModel):
    """Single lesson item"""
    lessonId: str = Field(..., alias="lessonId")
    title: str
    subject: str
    grade: int
    totalChunks: int = Field(..., alias="totalChunks")
    status: str
    
    class Config:
        populate_by_name = True


class LessonsData(BaseModel):
    """Lessons list data"""
    lessons: list[LessonItem]
    total: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "lessons": [
                    {
                        "lessonId": "bai_1_on_tap",
                        "title": "Ôn tập các số đến 100000",
                        "subject": "Toán",
                        "grade": 4,
                        "totalChunks": 45,
                        "status": "active"
                    }
                ],
                "total": 1
            }
        }


class SessionData(BaseModel):
    """Session data structure"""
    threadId: str = Field(..., alias="threadId")
    messageCount: int = Field(..., alias="messageCount")
    lastActivity: Optional[str] = Field(None, alias="lastActivity")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "threadId": "user_123_session_abc",
                "messageCount": 10,
                "lastActivity": "2025-12-15T18:30:00Z"
            }
        }


class UserLevelData(BaseModel):
    """User level data structure"""
    level: str
    score: int
    progress: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "level": "Intermediate",
                "score": 850,
                "progress": 75.5
            }
        }
