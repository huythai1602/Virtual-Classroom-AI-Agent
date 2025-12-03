"""
LangGraph Agent - Simplified and Clean
"""
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END

from config.settings import settings
from config.prompts import SYSTEM_PROMPTS, DEFAULT_METADATA, format_prompt
from .state import AgentState
from .memory import memory_saver


# Initialize LLM
llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0)


def intent_node(state: AgentState) -> dict:
    """Detect intent: normal or deep with conversation awareness"""
    messages = state["messages"]
    if not messages:
        return {"intent": "normal", "current_query": ""}
    
    last_message = messages[-1]
    query = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    # Check for follow-up questions
    query_lower = query.lower()
    follow_up_keywords = [
        "làm rõ", "giải thích thêm", "ý nghĩa", "nói rõ hơn",
        "câu trước", "vừa rồi", "ví dụ này", "phần này",
        "không hiểu", "chưa hiểu", "còn", "thế còn"
    ]
    
    deep_keywords = [
        "giải thích", "phân tích", "từng bước", "ví dụ", 
        "cụ thể", "cách", "làm thế nào", "tại sao", "vì sao"
    ]
    
    # If follow-up or deep keywords → always deep mode
    is_follow_up = any(kw in query_lower for kw in follow_up_keywords)
    is_deep = any(kw in query_lower for kw in deep_keywords)
    
    intent = "deep" if (is_follow_up or is_deep) else "normal"
    
    return {"intent": intent, "current_query": query}


# Metadata cache to avoid repeated DB queries
_metadata_cache = {}

def metadata_node(state: AgentState) -> dict:
    """Fetch lesson metadata with caching and enrichment"""
    from repositories.lessons import get_lesson
    import json
    
    lesson_id = state.get("lesson_id", None)
    metadata = DEFAULT_METADATA.copy()
    
    if lesson_id:
        # Check cache first
        if lesson_id in _metadata_cache:
            return {"metadata": _metadata_cache[lesson_id]}
        
        lesson = get_lesson(lesson_id)
        if lesson:
            # Basic metadata
            metadata["subject"] = lesson.get("subject", "Toán")
            metadata["grade"] = lesson.get("grade", 4)
            metadata["topic"] = lesson.get("title", "Bài học")
            
            # Extended metadata from DB
            db_metadata = lesson.get("metadata")
            if db_metadata:
                try:
                    if isinstance(db_metadata, str):
                        extra_metadata = json.loads(db_metadata)
                    else:
                        extra_metadata = db_metadata
                    
                    # Merge with defaults
                    metadata["curriculum"] = extra_metadata.get("curriculum", metadata["curriculum"])
                    metadata["difficulty"] = extra_metadata.get("difficulty", metadata["difficulty"])
                    metadata["prerequisites"] = extra_metadata.get("prerequisites", [])
                    metadata["learning_objectives"] = extra_metadata.get("learning_objectives", [])
                    metadata["keywords"] = extra_metadata.get("keywords", [])
                except:
                    pass
            
            # Cache it
            _metadata_cache[lesson_id] = metadata
    
    return {"metadata": metadata}


def retrieve_node(state: AgentState) -> dict:
    """Retrieve context from RAG with conversation awareness"""
    from services.rag.retriever import get_context
    from core.memory import session_memory
    
    query = state.get("current_query", "")
    intent = state.get("intent", "normal")
    lesson_id = state.get("lesson_id", None)
    thread_id = state.get("thread_id", "")
    
    # Get recent conversation for context
    conversation_window = ""
    if thread_id:
        conversation_window = session_memory.get_conversation_window(thread_id, n=2)
    
    # Enhance query with conversation context for better retrieval
    enhanced_query = query
    if conversation_window:
        # Add context to query for follow-up questions
        enhanced_query = f"Context from previous conversation:\n{conversation_window}\n\nCurrent question: {query}"
    
    # Adaptive k based on intent
    k = 5 if intent == "deep" else 3
    context = get_context(enhanced_query, lesson_id=lesson_id, k=k, intent=intent)
    
    return {
        "context": context,
        "conversation_history": conversation_window
    }


def answer_node(state: AgentState) -> dict:
    """Generate normal answer with conversation awareness"""
    query = state.get("current_query", "")
    context = state.get("context", "")
    metadata = state.get("metadata", DEFAULT_METADATA)
    conversation_history = state.get("conversation_history", "")
    
    # Add conversation history to context if available
    full_context = context
    if conversation_history:
        full_context = f"Previous conversation:\n{conversation_history}\n\n{context}"
    
    prompt = format_prompt(
        SYSTEM_PROMPTS["normal"],
        subject=metadata["subject"],
        grade=metadata["grade"],
        topic=metadata["topic"],
        context=full_context,
        question=query
    )
    
    response = llm.invoke(prompt)
    answer = response.content
    
    return {"messages": [AIMessage(content=answer)]}


def explain_node(state: AgentState) -> dict:
    """Generate detailed explanation with conversation awareness"""
    query = state.get("current_query", "")
    context = state.get("context", "")
    metadata = state.get("metadata", DEFAULT_METADATA)
    conversation_history = state.get("conversation_history", "")
    
    # Add conversation history to context if available
    full_context = context
    if conversation_history:
        full_context = f"Previous conversation:\n{conversation_history}\n\n{context}"
    
    prompt = format_prompt(
        SYSTEM_PROMPTS["deep"],
        subject=metadata["subject"],
        grade=metadata["grade"],
        topic=metadata["topic"],
        context=full_context,
        question=query
    )
    
    response = llm.invoke(prompt)
    explanation = response.content
    
    return {"messages": [AIMessage(content=explanation)]}


def route_intent(state: AgentState) -> Literal["answer", "explain"]:
    """Route by intent"""
    return "explain" if state.get("intent") == "deep" else "answer"


def create_agent():
    """Create and compile LangGraph agent"""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("intent", intent_node)
    workflow.add_node("metadata", metadata_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("explain", explain_node)
    
    # Build edges
    workflow.add_edge(START, "intent")
    workflow.add_edge("intent", "metadata")
    workflow.add_edge("metadata", "retrieve")
    
    # Conditional routing by intent
    workflow.add_conditional_edges(
        "retrieve",
        route_intent,
        {"answer": "answer", "explain": "explain"}
    )
    
    workflow.add_edge("answer", END)
    workflow.add_edge("explain", END)
    
    # Compile with memory
    return workflow.compile(checkpointer=memory_saver)


# Global agent instance
agent = create_agent()
