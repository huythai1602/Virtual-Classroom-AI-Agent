"""
Tool để summarize conversation history nhằm giảm tokens
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import List
from dotenv import load_dotenv

load_dotenv()

# LLM rẻ hơn cho summarization
summarizer_llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

SUMMARIZE_PROMPT = """Bạn là trợ lý tóm tắt cuộc hội thoại. Hãy tóm tắt cuộc hội thoại sau thành 2-3 câu ngắn gọn, giữ lại các thông tin quan trọng:

{conversation}

Tóm tắt (ngắn gọn, súc tích):"""


def summarize_old_messages(messages: List, keep_recent: int = 4) -> List:
    """
    Summarize old messages, chỉ giữ lại messages gần nhất
    
    Args:
        messages: List of messages (HumanMessage, AIMessage)
        keep_recent: Số messages gần nhất cần giữ nguyên (mặc định 4 = 2 cặp Q&A)
        
    Returns:
        List mới với: [SystemMessage(summary), ...recent_messages]
    """
    # Nếu ít messages thì không cần summarize
    if len(messages) <= keep_recent:
        return messages
    
    # Chia messages thành old và recent
    old_messages = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]
    
    # Tạo text từ old messages
    conversation_text = ""
    for msg in old_messages:
        if isinstance(msg, HumanMessage):
            conversation_text += f"Học sinh: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            conversation_text += f"Trợ giảng: {msg.content}\n"
    
    # Summarize
    try:
        prompt = SUMMARIZE_PROMPT.format(conversation=conversation_text)
        summary = summarizer_llm.invoke([HumanMessage(content=prompt)])
        
        # Tạo SystemMessage chứa summary
        summary_message = SystemMessage(
            content=f"Tóm tắt cuộc hội thoại trước: {summary.content}"
        )
        
        # Trả về: summary + recent messages
        return [summary_message] + recent_messages
        
    except Exception as e:
        print(f"Lỗi khi summarize: {e}")
        # Fallback: chỉ giữ recent messages
        return recent_messages
