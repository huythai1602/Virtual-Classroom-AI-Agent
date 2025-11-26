"""
Mindmap tool - Tạo sơ đồ tư duy dạng JSON cho React Flow
"""
import json
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from ..prompts import MINDMAP_PROMPT, format_prompt, DEFAULT_METADATA
from .retriever_tool import get_context
from database.lessons_repository import get_lesson

# Load environment variables
load_dotenv()

# Khởi tạo LLM với JSON mode
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    model_kwargs={"response_format": {"type": "json_object"}}
)

@tool
def generate_mindmap(topic: str, lesson_id: str = None) -> str:
    """
    Tạo sơ đồ tư duy cho một chủ đề dưới dạng JSON React Flow.
    
    Args:
        topic: Chủ đề cần tạo sơ đồ tư duy
        lesson_id: ID bài học (optional, dùng để lấy metadata)
        
    Returns:
        JSON string với format React Flow (nodes và edges)
    """
    # Lấy ngữ cảnh từ vector store
    context = get_context(topic, k=5, lesson_id=lesson_id)
    
    # Lấy metadata từ database nếu có lesson_id
    metadata = DEFAULT_METADATA.copy()
    if lesson_id:
        lesson = get_lesson(lesson_id)
        if lesson:
            metadata["subject"] = lesson.get("subject", "Toán")
            metadata["grade"] = lesson.get("grade", 4)
            metadata["topic"] = lesson.get("title", topic)
    else:
        metadata["topic"] = topic
    
    # Format prompt với metadata
    prompt = format_prompt(
        MINDMAP_PROMPT,
        context=context,
        topic=metadata["topic"],
        subject=metadata["subject"],
        grade=metadata["grade"]
    )
    
    # Gọi LLM
    messages = [HumanMessage(content=prompt)]
    
    response = llm.invoke(messages)
    
    # Validate JSON
    try:
        json_data = json.loads(response.content)
        # Đảm bảo có cấu trúc cơ bản
        if "nodes" not in json_data:
            json_data["nodes"] = []
        if "edges" not in json_data:
            json_data["edges"] = []
        return json.dumps(json_data, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        # Fallback nếu LLM không trả về JSON hợp lệ
        return json.dumps({
            "error": "Không thể tạo sơ đồ tư duy cho yêu cầu này."
        }, ensure_ascii=False)

def generate_mindmap_with_context(topic: str, context: str, metadata: dict = None) -> str:
    """
    Tạo sơ đồ tư duy với ngữ cảnh đã được cung cấp sẵn
    
    Args:
        topic: Chủ đề cần tạo sơ đồ tư duy
        context: Ngữ cảnh từ bài giảng
        metadata: Dict chứa subject, grade, topic (optional)
        
    Returns:
        JSON string với format React Flow
    """
    # Use default metadata if not provided
    if metadata is None:
        metadata = DEFAULT_METADATA.copy()
        metadata["topic"] = topic
    
    # Format prompt với metadata
    prompt = format_prompt(
        MINDMAP_PROMPT,
        context=context,
        topic=metadata.get("topic", topic),
        subject=metadata.get("subject", "Toán"),
        grade=metadata.get("grade", 4)
    )
    
    messages = [HumanMessage(content=prompt)]
    
    response = llm.invoke(messages)
    
    # Validate JSON
    try:
        json_data = json.loads(response.content)
        # Đảm bảo có cấu trúc cơ bản
        if "nodes" not in json_data:
            json_data["nodes"] = []
        if "edges" not in json_data:
            json_data["edges"] = []
        return json.dumps(json_data, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        # Fallback nếu LLM không trả về JSON hợp lệ
        return json.dumps({
            "error": "Không thể tạo sơ đồ tư duy cho yêu cầu này."
        }, ensure_ascii=False)
