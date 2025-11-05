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
