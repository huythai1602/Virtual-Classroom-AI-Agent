"""
LangGraph workflow definition
Định nghĩa các node và edges cho agent
"""
import os
from typing import Literal, TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver

from .prompts import SYSTEM_PROMPT, INTENT_DETECTION_PROMPT
from .tools.answer_tool import answer_with_context
from .tools.explain_tool import explain_with_context
from .tools.retriever_tool import get_context

# Load environment variables
load_dotenv()

# Khởi tạo LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

# Định nghĩa State
class AgentState(MessagesState):
    """State của agent bao gồm messages và metadata"""
    context: str = ""
    intent: str = ""
    current_query: str = ""
    lesson_id: str = ""  # Thêm lesson_id vào state


def intent_node(state: AgentState) -> dict:
    """
    Node phát hiện ý định của người dùng
    Trả về: "normal" hoặc "deep"
    KHÔNG BAO GỒM "mindmap" - mindmap có API riêng
    """
    messages = state["messages"]
    if not messages:
        return {"intent": "normal"}
    
    # Lấy câu hỏi mới nhất từ user
    last_message = messages[-1]
    if isinstance(last_message, HumanMessage):
        query = last_message.content
    else:
        query = ""
    
    # Phát hiện intent đơn giản dựa trên keywords
    query_lower = query.lower()
    
    # CHỈ phát hiện deep hoặc normal
    if any(keyword in query_lower for keyword in ["giải thích chi tiết", "phân tích", "từng bước", "ví dụ", "cụ thể"]):
        intent = "deep"
    else:
        intent = "normal"
    
    return {
        "intent": intent,
        "current_query": query
    }


def retrieve_node(state: AgentState) -> dict:
    """
    Node truy vấn ngữ cảnh từ ChromaDB
    Đã tối ưu: Giảm k để giảm tokens
    """
    query = state.get("current_query", "")
    intent = state.get("intent", "normal")
    lesson_id = state.get("lesson_id", None)  # Lấy lesson_id từ state
    
    # Tối ưu: Giảm k từ 3/5/10 xuống 3/5
    # Normal: 3 chunks (~600-1500 tokens)
    # Deep: 5 chunks (~1000-2500 tokens)
    k = 5 if intent == "deep" else 3
    
    # Truy vấn với lesson_id filter
    context = get_context(query, k=k, lesson_id=lesson_id)
    
    return {"context": context}


def answer_node(state: AgentState) -> dict:
    """
    Node trả lời ngắn gọn (Normal mode)
    """
    query = state.get("current_query", "")
    context = state.get("context", "")
    
    # Gọi tool trả lời
    answer = answer_with_context(query, context)
    
    # Cập nhật messages
    new_message = AIMessage(content=answer)
    
    return {"messages": [new_message]}


def explain_node(state: AgentState) -> dict:
    """
    Node giải thích chi tiết (Deep mode)
    """
    query = state.get("current_query", "")
    context = state.get("context", "")
    
    # Gọi tool giải thích
    explanation = explain_with_context(query, context)
    
    # Cập nhật messages
    new_message = AIMessage(content=explanation)
    
    return {"messages": [new_message]}


def route_intent(state: AgentState) -> Literal["answer", "explain"]:
    """
    Điều hướng dựa trên intent đã phát hiện
    CHỈ CÒN 2 ROUTE: answer hoặc explain
    """
    intent = state.get("intent", "normal")
    
    if intent == "deep":
        return "explain"
    else:
        return "answer"


def create_graph() -> StateGraph:
    """
    Tạo và cấu hình LangGraph workflow
    CHỈ CÒN 2 MODES: normal và deep (mindmap có API riêng)
    """
    # Khởi tạo StateGraph
    workflow = StateGraph(AgentState)
    
    # Thêm các nodes
    workflow.add_node("intent", intent_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("explain", explain_node)
    
    # Thêm edges
    # START -> intent
    workflow.add_edge(START, "intent")
    
    # intent -> retrieve
    workflow.add_edge("intent", "retrieve")
    
    # retrieve -> conditional routing dựa trên intent
    workflow.add_conditional_edges(
        "retrieve",
        route_intent,
        {
            "answer": "answer",
            "explain": "explain"
        }
    )
    
    # Tất cả nodes kết thúc đều đi đến END
    workflow.add_edge("answer", END)
    workflow.add_edge("explain", END)
    
    return workflow


def get_compiled_graph():
    """
    Compile graph với MemorySaver checkpointer
    """
    workflow = create_graph()
    memory = MemorySaver()
    compiled_graph = workflow.compile(checkpointer=memory)
    return compiled_graph


# Tạo graph instance toàn cục
compiled_graph = get_compiled_graph()
