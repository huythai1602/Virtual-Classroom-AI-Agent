"""
Answer tool - Trả lời câu hỏi ngắn gọn
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from ..prompts import NORMAL_ANSWER_PROMPT, TEACHER_ROLE, ACCURACY_CONSTRAINTS, format_prompt, DEFAULT_METADATA
from .retriever_tool import get_context
from database.lessons_repository import get_lesson
from database.chunks_repository import search_similar_chunks

# Load environment variables
load_dotenv()

# Tối ưu: Dùng GPT-3.5-turbo cho normal mode (rẻ hơn 10 lần GPT-4)
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

@tool
def answer_question(query: str, lesson_id: str = None) -> str:
    """
    Trả lời ngắn gọn câu hỏi của học sinh dựa trên transcript bài giảng.
    
    Args:
        query: Câu hỏi của học sinh
        lesson_id: ID bài học (optional, dùng để lấy metadata)
        
    Returns:
        Câu trả lời ngắn gọn
    """
    # Lấy ngữ cảnh từ vector store
    context = get_context(query, lesson_id=lesson_id)
    
    # Lấy metadata từ database nếu có lesson_id
    metadata = DEFAULT_METADATA.copy()
    if lesson_id:
        lesson = get_lesson(lesson_id)
        if lesson:
            metadata["subject"] = lesson.get("subject", "Toán")
            metadata["grade"] = lesson.get("grade", 4)
            metadata["topic"] = lesson.get("title", "Bài học")
    
    # Format prompt với metadata
    prompt = format_prompt(
        NORMAL_ANSWER_PROMPT,
        context=context,
        question=query,
        subject=metadata["subject"],
        grade=metadata["grade"],
        topic=metadata["topic"]
    )
    
    # Gọi LLM
    messages = [HumanMessage(content=prompt)]
    
    response = llm.invoke(messages)
    return response.content

def answer_with_context(query: str, context: str, metadata: dict = None) -> str:
    """
    Trả lời câu hỏi với ngữ cảnh đã được cung cấp sẵn
    
    Args:
        query: Câu hỏi của học sinh
        context: Ngữ cảnh từ bài giảng
        metadata: Dict chứa subject, grade, topic (optional)
        
    Returns:
        Câu trả lời ngắn gọn
    """
    # Use default metadata if not provided
    if metadata is None:
        metadata = DEFAULT_METADATA.copy()
    
    # Format prompt với metadata
    prompt = format_prompt(
        NORMAL_ANSWER_PROMPT,
        context=context,
        question=query,
        subject=metadata.get("subject", "Toán"),
        grade=metadata.get("grade", 4),
        topic=metadata.get("topic", "Bài học")
    )
    
    messages = [HumanMessage(content=prompt)]
    
    response = llm.invoke(messages)
    return response.content


def answer_with_confidence(query: str, context: str, metadata: dict = None) -> dict:
    """
    Trả lời câu hỏi với confidence scoring
    
    Args:
        query: Câu hỏi của học sinh
        context: Ngữ cảnh từ bài giảng
        metadata: Dict chứa subject, grade, topic (optional)
        
    Returns:
        dict với answer, confidence, reasoning
    """
    import json
    from langchain_openai import ChatOpenAI
    
    # Use default metadata if not provided
    if metadata is None:
        metadata = DEFAULT_METADATA.copy()
    
    # Format base prompt
    base_prompt = format_prompt(
        NORMAL_ANSWER_PROMPT,
        context=context,
        question=query,
        subject=metadata.get("subject", "Toán"),
        grade=metadata.get("grade", 4),
        topic=metadata.get("topic", "Bài học")
    )
    
    # Enhanced prompt với confidence scoring
    enhanced_prompt = f"""{base_prompt}

---
AFTER ANSWERING, EVALUATE CONFIDENCE:

CONFIDENCE LEVELS:
- HIGH (0.8-1.0): Question clearly related to lesson content with sufficient information
- MEDIUM (0.5-0.8): Related but information incomplete or ambiguous
- LOW (0.0-0.5): No relevant information found in lesson

Return JSON:
{{
    "answer": "natural Vietnamese answer",
    "confidence": 0.9,
    "reasoning": "why this confidence score"
}}

Return ONLY JSON, no additional text:"""
    
    # Use JSON mode
    llm_json = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    messages = [HumanMessage(content=enhanced_prompt)]
    
    try:
        response = llm_json.invoke(messages)
        result = json.loads(response.content)
        
        # Validate keys
        if "answer" not in result:
            result["answer"] = response.content
        if "confidence" not in result:
            result["confidence"] = 0.8  # Default high
        if "reasoning" not in result:
            result["reasoning"] = "No reasoning provided"
            
        return result
    except Exception as e:
        print(f"[ERROR] Confidence scoring failed: {e}")
        # Fallback: return normal answer
        return {
            "answer": answer_with_context(query, context, metadata),
            "confidence": 0.8,
            "reasoning": "Fallback to normal mode"
        }
