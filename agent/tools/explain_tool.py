"""
Explain tool - Giải thích chi tiết
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from ..prompts import SYSTEM_PROMPT, DEEP_EXPLAIN_PROMPT
from .retriever_tool import get_context

# Load environment variables
load_dotenv()

# Khởi tạo LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

@tool
def explain_question(query: str) -> str:
    """
    Giải thích chi tiết câu hỏi của học sinh dựa trên transcript bài giảng.
    
    Args:
        query: Câu hỏi của học sinh
        
    Returns:
        Giải thích chi tiết với các bước và ví dụ
    """
    # Lấy ngữ cảnh từ vector store
    context = get_context(query, k=5)  # Lấy nhiều context hơn cho giải thích chi tiết
    
    # Tạo prompt
    prompt = DEEP_EXPLAIN_PROMPT.format(context=context, question=query)
    
    # Gọi LLM
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    
    response = llm.invoke(messages)
    return response.content

def explain_with_context(query: str, context: str) -> str:
    """
    Giải thích chi tiết với ngữ cảnh đã được cung cấp sẵn
    
    Args:
        query: Câu hỏi của học sinh
        context: Ngữ cảnh từ bài giảng
        
    Returns:
        Giải thích chi tiết
    """
    prompt = DEEP_EXPLAIN_PROMPT.format(context=context, question=query)
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    
    response = llm.invoke(messages)
    return response.content
