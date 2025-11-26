"""
Analyzer tool - Phân tích buổi học
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from ..prompts import ANALYZER_PROMPT, ASSESSOR_ROLE, ACCURACY_CONSTRAINTS, format_prompt, DEFAULT_METADATA
from .retriever_tool import get_context
from .level_assessment_tool import assess_student_level_from_conversation
from database.lessons_repository import get_lesson

# Load environment variables
load_dotenv()

# Tối ưu: Dùng GPT-3.5-turbo cho analyzer (rẻ hơn, vẫn đủ tốt)
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

@tool
def analyze_session(conversation_history: str, lesson_id: str = None, topic: str = "") -> str:
    """
    Phân tích buổi học dựa trên lịch sử hội thoại và transcript.
    
    Args:
        conversation_history: Lịch sử hội thoại đầy đủ
        lesson_id: ID bài học (optional, dùng để lấy metadata)
        topic: Chủ đề bài học (tùy chọn)
        
    Returns:
        Phân tích chi tiết về buổi học
    """
    # Lấy metadata từ database nếu có lesson_id
    metadata = DEFAULT_METADATA.copy()
    if lesson_id:
        lesson = get_lesson(lesson_id)
        if lesson:
            metadata["subject"] = lesson.get("subject", "Toán")
            metadata["grade"] = lesson.get("grade", 4)
            metadata["topic"] = lesson.get("title", topic or "Bài học")
    elif topic:
        metadata["topic"] = topic
    
    # Lấy transcript tổng quan
    query = metadata["topic"]
    transcript = get_context(query, k=10, lesson_id=lesson_id)
    
    # Format prompt với metadata
    prompt = format_prompt(
        ANALYZER_PROMPT,
        transcript=transcript,
        conversation_history=conversation_history,
        subject=metadata["subject"],
        grade=metadata["grade"],
        topic=metadata["topic"]
    )
    
    # Gọi LLM
    messages = [HumanMessage(content=prompt)]
    
    response = llm.invoke(messages)
    return response.content

def analyze_with_data(conversation_history: str, transcript: str, metadata: dict = None) -> dict:
    """
    Phân tích với dữ liệu đã được cung cấp sẵn, bao gồm đánh giá level
    
    Args:
        conversation_history: Lịch sử hội thoại
        transcript: Nội dung bài giảng
        metadata: Dict chứa subject, grade, topic (optional)
        
    Returns:
        dict: {"analysis": str, "level": str, "level_reason": str}
    """
    # Use default metadata if not provided
    if metadata is None:
        metadata = DEFAULT_METADATA.copy()
    
    # Format prompt với metadata
    prompt = format_prompt(
        ANALYZER_PROMPT,
        transcript=transcript,
        conversation_history=conversation_history,
        subject=metadata.get("subject", "Toán"),
        grade=metadata.get("grade", 4),
        topic=metadata.get("topic", "Bài học")
    )
    
    messages = [HumanMessage(content=prompt)]
    
    response = llm.invoke(messages)
    analysis = response.content
    
    # Đánh giá level dựa trên conversation (rule-based, không gọi LLM)
    messages_count = conversation_history.count("\n") // 2  # Ước lượng số cặp Q&A
    level_result = assess_student_level_from_conversation(conversation_history, messages_count)
    
    return {
        "analysis": analysis,
        "level": level_result.get("level", "Beginner"),
        "level_reason": level_result.get("reason", "")
    }
