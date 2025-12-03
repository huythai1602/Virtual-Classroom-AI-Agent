"""
Conversation summarizer
Consolidated from agent/tools/summarizer_tool.py
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import List

# Use GPT-3.5 for cost optimization
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

SUMMARIZE_PROMPT = """Tóm tắt cuộc hội thoại sau thành 2-3 câu ngắn gọn, giữ lại thông tin quan trọng:

{conversation}

Tóm tắt:"""


def summarize_conversation(messages: List, keep_recent: int = 4) -> List:
    """
    Summarize old messages, keep recent ones
    
    Args:
        messages: List of messages
        keep_recent: Number of recent messages to keep (default 4 = 2 Q&A pairs)
        
    Returns:
        [SystemMessage(summary), ...recent_messages]
    """
    if len(messages) <= keep_recent:
        return messages
    
    old_messages = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]
    
    # Build conversation text
    conversation_text = ""
    for msg in old_messages:
        if isinstance(msg, HumanMessage):
            conversation_text += f"Học sinh: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            conversation_text += f"Trợ giảng: {msg.content}\n"
    
    # Summarize
    try:
        prompt = SUMMARIZE_PROMPT.format(conversation=conversation_text)
        summary = llm.invoke([HumanMessage(content=prompt)])
        
        summary_message = SystemMessage(
            content=f"Tóm tắt cuộc hội thoại trước: {summary.content}"
        )
        
        return [summary_message] + recent_messages
    except Exception as e:
        print(f"Summarization error: {e}")
        return recent_messages
