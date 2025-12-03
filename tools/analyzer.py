"""
Session analyzer tool
Consolidated from agent/tools/analyzer_tool.py
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config.prompts import SYSTEM_PROMPTS, format_prompt, DEFAULT_METADATA
from services.rag import get_context
from repositories.lessons import get_lesson

# Use GPT-3.5 for cost optimization
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)


def analyze_session(
    conversation_history: str,
    lesson_id: str = None,
    topic: str = ""
) -> dict:
    """
    Analyze learning session
    
    Args:
        conversation_history: Full conversation text
        lesson_id: Optional lesson ID
        topic: Optional topic
        
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
            metadata["topic"] = lesson.get("title", topic or "Bài học")
    elif topic:
        metadata["topic"] = topic
    
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
    response = llm.invoke([HumanMessage(content=prompt)])
    analysis = response.content
    
    # Simple level assessment based on message count
    messages_count = conversation_history.count("\n") // 2
    if messages_count >= 10:
        level = "Tốt"
        level_reason = "Học sinh tương tác tích cực với nhiều câu hỏi"
    elif messages_count >= 5:
        level = "Trung bình"
        level_reason = "Học sinh có tham gia nhưng chưa nhiều"
    else:
        level = "Cần cải thiện"
        level_reason = "Học sinh chưa tương tác đủ để đánh giá"
    
    return {
        "analysis": analysis,
        "level": level,
        "level_reason": level_reason
    }
