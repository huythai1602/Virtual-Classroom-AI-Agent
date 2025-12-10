"""Session analyzer tool
Consolidated from agent/tools/analyzer_tool.py
"""
from typing import Union
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config.prompts import SYSTEM_PROMPTS, format_prompt, DEFAULT_METADATA
from services.rag import get_context
from repositories.lessons import get_lesson

# Lazy init
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    return _llm



def analyze_session(
    conversation_history: str,
    lesson_id: Union[str, int]
) -> dict:
    """
    Analyze learning session
    
    Args:
        conversation_history: Full conversation text
        lesson_id: Lesson ID
        
    Returns:
        dict with analysis and level assessment
    """
    # Get metadata
    metadata = DEFAULT_METADATA.copy()
    if lesson_id:
        lesson = get_lesson(lesson_id)
        if lesson:
            metadata["subject"] = lesson.get("subject", "Toán")
            metadata["grade"] = lesson.get("grade", 4)
            metadata["topic"] = lesson.get("title", "Bài học")
    
    # Get transcript
    transcript = get_context(metadata["topic"], k=10, lesson_id=lesson_id)
    
    # Format prompt
    prompt = format_prompt(
        SYSTEM_PROMPTS["analyzer"],
        conversation_history=conversation_history,
        subject=metadata["subject"],
        grade=metadata["grade"],
        topic=metadata["topic"]
    )
    
    # Generate analysis
    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    analysis = response.content
    
    # Simple level assessment based on message count
    messages_count = conversation_history.count("\n") // 2
    
    # If the history is empty/short but analyzer is called, we assume 90% video completion (Passive Learner)
    # The Prompt will handle the textual feedback, but we need to force the "Level" tag.
    if messages_count >= 10:
        level = "Tốt"
        level_reason = "Học sinh tương tác tích cực với nhiều câu hỏi"
    elif messages_count >= 5:
        level = "Trung bình"
        level_reason = "Học sinh có tham gia nhưng chưa nhiều"
    elif messages_count < 5:
        # Changed logic for Passive Learners
        level = "Cơ bản" # "Basic" instead of "Needs Improvement"
        level_reason = "Học sinh tập trung xem video (Passive Learner), đã nắm kiến thức nền"
    else: 
        # Fallback (unlikely to reach here given logic above covers all ints)
        level = "Cần cải thiện"
        level_reason = "Học sinh chưa tương tác đủ để đánh giá"
    
    return {
        "analysis": analysis,
        "level": level,
        "level_reason": level_reason
    }
