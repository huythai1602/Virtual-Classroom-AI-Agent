"""
Analyzer tool - Phân tích buổi học
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from ..prompts import ANALYZER_PROMPT
from .retriever_tool import get_context
from .level_assessment_tool import assess_student_level_from_conversation

# Load environment variables
load_dotenv()

# Tối ưu: Dùng GPT-3.5-turbo cho analyzer (rẻ hơn, vẫn đủ tốt)
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

@tool
def analyze_session(conversation_history: str, topic: str = "") -> str:
    """
    Phân tích buổi học dựa trên lịch sử hội thoại và transcript.
    
    Args:
        conversation_history: Lịch sử hội thoại đầy đủ
        topic: Chủ đề bài học (tùy chọn)
        
    Returns:
        Phân tích chi tiết về buổi học
    """
    # Lấy transcript tổng quan (hoặc theo topic nếu có)
    query = topic if topic else "Toán lớp 4"
    transcript = get_context(query, k=10)
    
    # Tạo prompt
    prompt = ANALYZER_PROMPT.format(
        transcript=transcript,
        conversation_history=conversation_history
    )
    
    # Gọi LLM
    messages = [
        SystemMessage(content="Bạn là cô giáo Toán lớp 4 thân thiện, đang viết nhận xét cho em học sinh sau buổi học. Giọng điệu nhẹ nhàng, động viên, đầy tình cảm."),
        HumanMessage(content=prompt)
    ]
    
    response = llm.invoke(messages)
    return response.content

def analyze_with_data(conversation_history: str, transcript: str) -> dict:
    """
    Phân tích với dữ liệu đã được cung cấp sẵn, bao gồm đánh giá level
    
    Args:
        conversation_history: Lịch sử hội thoại
        transcript: Nội dung bài giảng
        
    Returns:
        dict: {"analysis": str, "level": str, "level_reason": str}
    """
    # Phân tích buổi học
    prompt = ANALYZER_PROMPT.format(
        transcript=transcript,
        conversation_history=conversation_history
    )
    
    messages = [
        SystemMessage(content="Bạn là cô giáo Toán lớp 4 thân thiện, đang viết nhận xét cho em học sinh sau buổi học. Giọng điệu nhẹ nhàng, động viên, đầy tình cảm."),
        HumanMessage(content=prompt)
    ]
    
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
