"""
Explain tool - Giải thích chi tiết
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from ..prompts import DEEP_EXPLAIN_PROMPT, TEACHER_ROLE, ACCURACY_CONSTRAINTS, format_prompt, DEFAULT_METADATA
from .retriever_tool import get_context
from database.lessons_repository import get_lesson

# Load environment variables
load_dotenv()

# Khởi tạo LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

@tool
def explain_question(query: str, lesson_id: str = None) -> str:
    """
    Giải thích chi tiết câu hỏi của học sinh dựa trên transcript bài giảng.
    
    Args:
        query: Câu hỏi của học sinh
        lesson_id: ID bài học (optional, dùng để lấy metadata)
        
    Returns:
        Giải thích chi tiết với các bước và ví dụ
    """
    # Lấy ngữ cảnh từ vector store
    context = get_context(query, k=5, lesson_id=lesson_id)  # Lấy nhiều context hơn cho giải thích chi tiết
    
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
        DEEP_EXPLAIN_PROMPT,
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

def explain_with_context(query: str, context: str, metadata: dict = None) -> str:
    """
    Giải thích chi tiết với ngữ cảnh đã được cung cấp sẵn.
    Bao gồm self-critique để đảm bảo độ chính xác.
    
    Args:
        query: Câu hỏi của học sinh
        context: Ngữ cảnh từ bài giảng
        metadata: Dict chứa subject, grade, topic (optional)
        
    Returns:
        Giải thích chi tiết đã được validate
    """
    from .validator_tool import validate_answer, should_use_validation
    
    # Use default metadata if not provided
    if metadata is None:
        metadata = DEFAULT_METADATA.copy()
    
    # Format prompt với metadata
    prompt = format_prompt(
        DEEP_EXPLAIN_PROMPT,
        context=context,
        question=query,
        subject=metadata.get("subject", "Toán"),
        grade=metadata.get("grade", 4),
        topic=metadata.get("topic", "Bài học")
    )
    
    messages = [HumanMessage(content=prompt)]
    
    response = llm.invoke(messages)
    answer = response.content
    
    # Self-critique cho deep mode
    if should_use_validation(intent="deep"):
        validation = validate_answer(query, answer, context)
        
        # Nếu validation phát hiện vấn đề và confidence < 70
        if not validation["is_valid"] or validation["confidence"] < 70:
            # Sử dụng corrected_answer nếu có
            if validation["corrected_answer"] and validation["corrected_answer"] != answer:
                answer = validation["corrected_answer"]
                print(f"[VALIDATION] Đã sửa câu trả lời. Issues: {validation['issues']}")
    
    return answer
