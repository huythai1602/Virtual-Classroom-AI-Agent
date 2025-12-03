"""Response models"""
from pydantic import BaseModel
from typing import Optional, Dict, Any


class ChatResponse(BaseModel):
    """Chat response model"""
    answer: str
    thread_id: str
    intent: Optional[str] = None


class MindmapResponse(BaseModel):
    """Mindmap response model"""
    mindmap: Dict[str, Any]
    topic: str


class AnalyzerResponse(BaseModel):
    """Analyzer response model"""
    analysis: str
    level: str
    level_reason: str
    thread_id: str
