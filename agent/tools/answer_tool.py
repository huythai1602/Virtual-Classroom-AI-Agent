"""
Answer tool - Trả lời câu hỏi ngắn gọn
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from ..prompts import SYSTEM_PROMPT, NORMAL_ANSWER_PROMPT
from .retriever_tool import get_context

# Load environment variables
load_dotenv()

# Tối ưu: Dùng GPT-3.5-turbo cho normal mode (rẻ hơn 10 lần GPT-4)
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

@tool
def answer_question(query: str) -> str:
    """
    Trả lời ngắn gọn câu hỏi của học sinh dựa trên transcript bài giảng.
    
    Args:
        query: Câu hỏi của học sinh
        
    Returns:
        Câu trả lời ngắn gọn
    """
    # Lấy ngữ cảnh từ vector store
    context = get_context(query)
    
    # Tạo prompt
    prompt = NORMAL_ANSWER_PROMPT.format(context=context, question=query)
    
    # Gọi LLM
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    
    response = llm.invoke(messages)
    return response.content

def answer_with_context(query: str, context: str) -> str:
    """
    Trả lời câu hỏi với ngữ cảnh đã được cung cấp sẵn
    
    Args:
        query: Câu hỏi của học sinh
        context: Ngữ cảnh từ bài giảng
        
    Returns:
        Câu trả lời ngắn gọn
    """
    prompt = NORMAL_ANSWER_PROMPT.format(context=context, question=query)
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    
    response = llm.invoke(messages)
    return response.content


def answer_with_confidence(query: str, context: str) -> dict:
    """
    Trả lời câu hỏi với confidence scoring (PHASE 2)
    
    Args:
        query: Câu hỏi của học sinh
        context: Ngữ cảnh từ bài giảng
        
    Returns:
        dict với answer, confidence, reasoning
    """
    import json
    from langchain_openai import ChatOpenAI
    
    # Enhanced prompt với confidence scoring
    enhanced_prompt = f"""{NORMAL_ANSWER_PROMPT.format(context=context, question=query)}

---
SAU KHI TRẢ LỜI, ĐÁNH GIÁ CONFIDENCE:

CONFIDENCE LEVELS:
- HIGH (0.8-1.0): Chắc chắn câu hỏi liên quan BÀI HỌC và có đủ thông tin rõ ràng
- MEDIUM (0.5-0.8): Có thể liên quan nhưng thông tin không đầy đủ hoặc mơ hồ
- LOW (0.0-0.5): Không tìm thấy thông tin liên quan trong bài học

Trả về JSON:
{{
    "answer": "câu trả lời tự nhiên của cô",
    "confidence": 0.9,
    "reasoning": "tại sao đánh giá confidence này"
}}

CHỈ trả về JSON, không thêm text:"""
    
    # Dùng JSON mode
    llm_json = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=enhanced_prompt)
    ]
    
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
            "answer": answer_with_context(query, context),
            "confidence": 0.8,
            "reasoning": "Fallback to normal mode"
        }
