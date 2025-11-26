"""
LangGraph workflow definition
Defines nodes and edges for agent
"""
import os
from typing import Literal, TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver

from .prompts import DEFAULT_METADATA
from .tools.answer_tool import answer_with_context, answer_with_confidence
from .tools.explain_tool import explain_with_context
from .tools.retriever_tool import get_context, get_context_smart
from .tools.router_tool import get_route_decision
from .tools.external_search_tool import get_external_context
from .tools.synthesis_tool import create_hybrid_answer
from .tools.verification_tool import get_verification_result
from database.lessons_repository import get_lesson

# Load environment variables
load_dotenv()

# Initialize LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

# Define State
class AgentState(MessagesState):
    """Agent state including messages and metadata"""
    context: str = ""
    intent: str = ""
    current_query: str = ""
    lesson_id: str = ""  # Lesson ID for metadata
    route: str = ""  # Routing decision: internal/external/hybrid
    external_context: str = ""  # External search results
    metadata: dict = {}  # Subject, grade, topic metadata


def intent_node(state: AgentState) -> dict:
    """
    Node to detect user intent
    Returns: "normal" or "deep"
    Does NOT include "mindmap" - mindmap has separate API
    """
    messages = state["messages"]
    if not messages:
        return {"intent": "normal"}
    
    # Get latest question from user
    last_message = messages[-1]
    if isinstance(last_message, HumanMessage):
        query = last_message.content
    else:
        query = ""
    
    # Intent detection based on keywords and question patterns
    query_lower = query.lower()
    
    # Deep mode triggers (detailed explanation needed)
    deep_keywords = [
        "giải thích chi tiết", "giải thích", "phân tích", "từng bước", 
        "ví dụ", "cụ thể", "cách", "làm thế nào", "làm như thế nào",
        "tại sao", "vì sao", "cho em hỏi cách", "hướng dẫn"
    ]
    
    if any(keyword in query_lower for keyword in deep_keywords):
        intent = "deep"
    else:
        intent = "normal"
    
    return {
        "intent": intent,
        "current_query": query
    }


def metadata_node(state: AgentState) -> dict:
    """
    Node to fetch metadata from database if lesson_id exists
    """
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
    """
    Node to retrieve context from PostgreSQL pgvector with Smart Retrieval
    """
    query = state.get("current_query", "")
    intent = state.get("intent", "normal")
    lesson_id = state.get("lesson_id", None)
    
    # Smart Retrieval with query expansion
    k = 10 if intent == "deep" else 7
    context = get_context_smart(query, k=k, lesson_id=lesson_id)
    
    return {"context": context}


def router_node(state: AgentState) -> dict:
    """
    Routing node: decide to use internal RAG, external search, or hybrid
    """
    query = state.get("current_query", "")
    context = state.get("context", "")
    metadata = state.get("metadata", DEFAULT_METADATA)
    
    # Get routing decision
    route_result = get_route_decision(
        question=query,
        rag_preview=context[:1000],  # Preview for routing decision
        subject=metadata.get("subject", "Toán"),
        grade=metadata.get("grade", 4),
        topic=metadata.get("topic", "Bài học")
    )
    
    route = route_result.get("route", "internal")
    confidence = route_result.get("confidence", 0.7)
    
    print(f"[ROUTER] Route: {route}, Confidence: {confidence:.2f}")
    print(f"[ROUTER] Reasoning: {route_result.get('reasoning', 'N/A')}")
    
    return {"route": route}


def external_search_node(state: AgentState) -> dict:
    """
    Node to search information from external sources (Google + Wikipedia)
    """
    query = state.get("current_query", "")
    
    print(f"[EXTERNAL SEARCH] Searching for: {query}")
    
    # Get external context
    external_context = get_external_context(query, max_results=5)
    
    return {"external_context": external_context}


def answer_node(state: AgentState) -> dict:
    """
    Answer node with routing intelligence (internal/external/hybrid)
    """
    query = state.get("current_query", "")
    context = state.get("context", "")
    route = state.get("route", "internal")
    external_context = state.get("external_context", "")
    metadata = state.get("metadata", DEFAULT_METADATA)
    
    print(f"[ANSWER NODE] Route: {route}")
    print(f"[ANSWER NODE] Context length: {len(context)}, External length: {len(external_context)}")
    
    # CRITICAL: If internal route but context is empty/poor, force hybrid
    if route == "internal" and len(context.strip()) < 100:
        print(f"[ANSWER NODE] WARNING: Internal route but context too short, forcing hybrid")
        route = "hybrid"
    
    # Route-based answer generation
    if route == "out_of_scope":
        # Out of scope - politely decline without external search
        subject = metadata.get("subject", "Toán")
        grade = metadata.get("grade", 4)
        topic = metadata.get("topic", "bài học")
        answer = f"Em ơi, câu hỏi này không thuộc môn {subject} lớp {grade} mà chúng ta đang học nhé! Giờ học hôm nay cô đang giảng về {topic}. Em muốn hỏi gì về bài học này không?"
        print(f"[ANSWER NODE] Out of scope - declining politely")
        
    elif route == "internal":
        # Pure internal RAG - apply theory from transcript
        result = answer_with_confidence(query, context, metadata)
        answer = result.get("answer", "")
        confidence = result.get("confidence", 0.8)
        print(f"[ANSWER NODE] Internal confidence: {confidence:.2f}")
            
    else:  # hybrid
        # Hybrid: Combine internal theory + external deep knowledge
        if external_context and "Không tìm thấy" not in external_context:
            answer = create_hybrid_answer(
                question=query,
                internal_context=context,
                external_context=external_context,
                metadata=metadata
            )
            print(f"[ANSWER NODE] Hybrid synthesis: internal theory + external knowledge")
            
            # Verify hybrid answer
            verification = get_verification_result(
                question=query,
                answer=answer,
                source_context=f"INTERNAL:\n{context[:500]}\n\nEXTERNAL:\n{external_context[:500]}",
                metadata=metadata
            )
            
            if not verification.get("is_valid", True) or verification.get("overall_score", 1.0) < 0.6:
                print(f"[ANSWER NODE] Verification failed: {verification.get('issues', [])}")
                # Fallback to internal only
                result = answer_with_confidence(query, context, metadata)
                answer = result.get("answer", "")
        else:
            # External search failed, fallback to internal
            print(f"[ANSWER NODE] External search failed, using internal only")
            result = answer_with_confidence(query, context, metadata)
            answer = result.get("answer", "")
    
    new_message = AIMessage(content=answer)
    return {"messages": [new_message]}


def explain_node(state: AgentState) -> dict:
    """
    Detailed explanation node (Deep mode) with hybrid support
    """
    query = state.get("current_query", "")
    context = state.get("context", "")
    route = state.get("route", "internal")
    external_context = state.get("external_context", "")
    metadata = state.get("metadata", DEFAULT_METADATA)
    
    print(f"[EXPLAIN NODE] Route: {route}")
    print(f"[EXPLAIN NODE] Context length: {len(context)}, External length: {len(external_context)}")
    
    # Handle out_of_scope
    if route == "out_of_scope":
        subject = metadata.get("subject", "Toán")
        grade = metadata.get("grade", 4)
        topic = metadata.get("topic", "bài học")
        explanation = f"Em ơi, câu hỏi này không thuộc môn {subject} lớp {grade} mà chúng ta đang học nhé! Giờ học hôm nay cô đang giảng về {topic}. Em muốn cô giải thích chi tiết phần nào trong bài này không?"
        print(f"[EXPLAIN NODE] Out of scope - declining politely")
        new_message = AIMessage(content=explanation)
        return {"messages": [new_message]}
    
    # CRITICAL: If internal route but context is empty/poor, force hybrid
    if route == "internal" and len(context.strip()) < 100:
        print(f"[EXPLAIN NODE] WARNING: Internal route but context too short, forcing hybrid")
        route = "hybrid"
    
    # For deep mode, prefer internal but can supplement with external
    if route == "hybrid" and external_context and "Không tìm thấy" not in external_context:
        # Combine contexts for richer explanation
        combined_context = f"{context}\n\n[Thông tin bổ sung từ nguồn ngoài]\n{external_context[:1000]}"
        explanation = explain_with_context(query, combined_context, metadata)
        print(f"[EXPLAIN NODE] Using hybrid context")
    else:
        # Use internal context only
        explanation = explain_with_context(query, context, metadata)
        print(f"[EXPLAIN NODE] Using internal context only")
    
    new_message = AIMessage(content=explanation)
    return {"messages": [new_message]}


def route_by_source(state: AgentState) -> Literal["process_answer", "external_search"]:
    """
    Route based on routing decision
    - out_of_scope: Skip external search, go directly to answer (will decline)
    - internal: Skip external search, use transcript theory
    - hybrid: Trigger external search for deeper knowledge
    """
    route = state.get("route", "internal")
    
    if route == "hybrid":
        return "external_search"
    else:
        # out_of_scope and internal both skip external search
        return "process_answer"


def intent_routing_node(state: AgentState) -> dict:
    """
    Passthrough node for intent routing after internal-only path
    """
    return {}


def route_intent(state: AgentState) -> Literal["answer", "explain"]:
    """
    Route based on detected intent
    Only 2 routes: answer or explain
    """
    intent = state.get("intent", "normal")
    
    if intent == "deep":
        return "explain"
    else:
        return "answer"


def create_graph() -> StateGraph:
    """
    Create and configure LangGraph workflow with external search routing
    Workflow: intent -> metadata -> retrieve -> router -> [external_search] -> answer/explain
    """
    workflow = StateGraph(AgentState)
    
    # Add all nodes
    workflow.add_node("intent", intent_node)
    workflow.add_node("metadata", metadata_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("router", router_node)
    workflow.add_node("external_search", external_search_node)
    workflow.add_node("intent_routing", intent_routing_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("explain", explain_node)
    
    # Build workflow edges
    workflow.add_edge(START, "intent")
    workflow.add_edge("intent", "metadata")
    workflow.add_edge("metadata", "retrieve")
    workflow.add_edge("retrieve", "router")
    
    # Router decides: internal (skip external) or external/hybrid (fetch external)
    workflow.add_conditional_edges(
        "router",
        route_by_source,
        {
            "process_answer": "intent_routing",  # Internal only, skip external search
            "external_search": "external_search"  # Need external data
        }
    )
    
    # After external search, route by intent
    workflow.add_conditional_edges(
        "external_search",
        route_intent,
        {
            "answer": "answer",
            "explain": "explain"
        }
    )
    
    # Direct intent routing (for internal-only path)
    workflow.add_conditional_edges(
        "intent_routing",
        route_intent,
        {
            "answer": "answer",
            "explain": "explain"
        }
    )
    
    # All processing nodes end at END
    workflow.add_edge("answer", END)
    workflow.add_edge("explain", END)
    
    return workflow


def get_compiled_graph():
    """
    Compile graph with MemorySaver checkpointer
    """
    workflow = create_graph()
    memory = MemorySaver()
    compiled_graph = workflow.compile(checkpointer=memory)
    return compiled_graph


# Create global graph instance
compiled_graph = get_compiled_graph()
