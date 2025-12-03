"""
State definitions for LangGraph agent
"""
from typing import TypedDict, Union, Optional
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Agent state with context and metadata"""
    context: str = ""
    intent: str = ""  # normal or deep
    current_query: str = ""
    lesson_id: Optional[Union[str, int]] = None
    metadata: dict = {}
    conversation_history: str = ""  # Recent conversation for context
    thread_id: str = ""


class ChatContext(TypedDict):
    """Chat context for requests"""
    thread_id: str
    lesson_id: str
    user_id: str
