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
    """Detect intent: normal or deep"""
    messages = state["messages"]
    if not messages:
        return {"intent": "normal"}
    
    last_message = messages[-1]
    query = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    # Simple keyword-based intent detection
    query_lower = query.lower()
    deep_keywords = [
        "giải thích", "phân tích", "từng bước", "ví dụ", 
        "cụ thể", "cách", "làm thế nào", "tại sao", "vì sao"
    ]
    
    intent = "deep" if any(kw in query_lower for kw in deep_keywords) else "normal"
    
    return {"intent": intent, "current_query": query}


def metadata_node(state: AgentState) -> dict:
    """Fetch lesson metadata"""
    from repositories.lessons import get_lesson
    
    lesson_id = state.get("lesson_id", None)
    metadata = DEFAULT_METADATA.copy()
    
    if lesson_id:
        lesson = get_lesson(lesson_id)
        if lesson:
            metadata["subject"] = lesson.get("subject", "Toán")
            metadata["grade"] = lesson.get("grade", 4)
            metadata["topic"] = lesson.get("title", "Bài học")
    
    return {"metadata": metadata}


def retrieve_node(state: AgentState) -> dict:
    """Retrieve context from RAG"""
    from services.rag.retriever import get_context
    
    query = state.get("current_query", "")
    intent = state.get("intent", "normal")
    lesson_id = state.get("lesson_id", None)
    
    # Adaptive k based on intent
    k = 5 if intent == "deep" else 3
    context = get_context(query, lesson_id=lesson_id, k=k, intent=intent)
    
    return {"context": context}


def answer_node(state: AgentState) -> dict:
    """Generate normal answer"""
    query = state.get("current_query", "")
    context = state.get("context", "")
    metadata = state.get("metadata", DEFAULT_METADATA)
    
    prompt = format_prompt(
        SYSTEM_PROMPTS["normal"],
        subject=metadata["subject"],
        grade=metadata["grade"],
        topic=metadata["topic"],
        context=context,
        question=query
    )
    
    response = llm.invoke(prompt)
    answer = response.content
    
    return {"messages": [AIMessage(content=answer)]}


def explain_node(state: AgentState) -> dict:
    """Generate detailed explanation"""
    query = state.get("current_query", "")
    context = state.get("context", "")
    metadata = state.get("metadata", DEFAULT_METADATA)
    
    prompt = format_prompt(
        SYSTEM_PROMPTS["deep"],
        subject=metadata["subject"],
        grade=metadata["grade"],
        topic=metadata["topic"],
        context=context,
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
