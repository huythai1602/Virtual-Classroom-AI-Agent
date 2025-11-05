"""
Mindmap tool - Tạo sơ đồ tư duy dạng JSON cho React Flow
"""
import json
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from ..prompts import SYSTEM_PROMPT, MINDMAP_PROMPT
from .retriever_tool import get_context

# Load environment variables
load_dotenv()

# Khởi tạo LLM với JSON mode
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    model_kwargs={"response_format": {"type": "json_object"}}
)

@tool
def generate_mindmap(topic: str) -> str:
    """
    Tạo sơ đồ tư duy cho một chủ đề dưới dạng JSON React Flow.
    
    Args:
        topic: Chủ đề cần tạo sơ đồ tư duy
        
    Returns:
        JSON string với format React Flow (nodes và edges)
    """
    # Lấy ngữ cảnh từ vector store
    context = get_context(topic, k=5)
    
    # Tạo prompt
    prompt = MINDMAP_PROMPT.format(context=context, topic=topic)
    
    # Gọi LLM
    messages = [
        SystemMessage(content="Bạn là cô giáo Toán lớp 4 vui vẻ, đang giúp em học sinh tạo sơ đồ tư duy dễ nhớ. Chỉ trả về JSON thuần, không thêm text."),
        HumanMessage(content=prompt)
    ]
    
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

def generate_mindmap_with_context(topic: str, context: str) -> str:
    """
    Tạo sơ đồ tư duy với ngữ cảnh đã được cung cấp sẵn
    
    Args:
        topic: Chủ đề cần tạo sơ đồ tư duy
        context: Ngữ cảnh từ bài giảng
        
    Returns:
        JSON string với format React Flow
    """
    prompt = MINDMAP_PROMPT.format(context=context, topic=topic)
    
    messages = [
        SystemMessage(content="Bạn là cô giáo Toán lớp 4 vui vẻ, đang giúp em học sinh tạo sơ đồ tư duy dễ nhớ. Chỉ trả về JSON thuần, không thêm text."),
        HumanMessage(content=prompt)
    ]
    
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
