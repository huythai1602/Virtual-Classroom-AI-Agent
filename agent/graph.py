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
from .tools.answer_tool import answer_with_context, answer_with_confidence
from .tools.explain_tool import explain_with_context
from .tools.retriever_tool import get_context, get_context_smart
from .tools.intent_classifier_tool import classify_intent, should_use_intent_classifier

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
    Node truy vấn ngữ cảnh từ ChromaDB với Smart Retrieval
    """
    query = state.get("current_query", "")
    intent = state.get("intent", "normal")
    lesson_id = state.get("lesson_id", None)  # Lấy lesson_id từ state
    
    # PHASE 1: Smart Retrieval với query expansion
    # Normal: 7 chunks với expansion
    # Deep: 10 chunks với expansion
    k = 10 if intent == "deep" else 7
    
    # Dùng smart retrieval thay vì get_context thông thường
    context = get_context_smart(query, k=k, lesson_id=lesson_id)
    
    return {"context": context}


def answer_node(state: AgentState) -> dict:
    """
    Node trả lời ngắn gọn với HYBRID APPROACH (Phase 1-4)
    """
    query = state.get("current_query", "")
    context = state.get("context", "")
    lesson_id = state.get("lesson_id", None)
    
    # PHASE 2: Answer với confidence scoring
    result = answer_with_confidence(query, context)
    
    confidence = result.get("confidence", 0.8)
    answer = result.get("answer", "")
    
    print(f"[ANSWER NODE] Confidence: {confidence:.2f}")
    
    # PHASE 3: Nếu low confidence → classify intent và retry
    if should_use_intent_classifier(confidence):
        print(f"[ANSWER NODE] Low confidence ({confidence:.2f}), using intent classifier...")
        
        intent_result = classify_intent(query)
        
        if intent_result["classification"] == "IN-SCOPE" and intent_result["confidence"] > 0.8:
            # Re-retrieve với lesson_id cụ thể
            better_lesson_id = intent_result.get("lesson_id")
            if better_lesson_id:
                print(f"[ANSWER NODE] Re-retrieving with lesson_id: {better_lesson_id}")
                better_context = get_context_smart(query, k=10, lesson_id=better_lesson_id)
                
                # Re-answer
                result = answer_with_confidence(query, better_context)
                answer = result.get("answer", "")
                print(f"[ANSWER NODE] Re-answer confidence: {result.get('confidence', 0):.2f}")
        
        elif intent_result["classification"] == "OUT-OF-SCOPE" and intent_result["confidence"] > 0.85:
            # Truly out-of-scope
            topic = intent_result.get("topic", "câu hỏi này")
            answer = (
                f"Ối, {topic} chưa nằm trong chương trình Toán lớp 4 em ạ! "
                f"Bây giờ chúng ta đang học về số học, phép tính và phân số. "
                f"Em có muốn hỏi về các chủ đề này không?"
            )
            print(f"[ANSWER NODE] OUT-OF-SCOPE confirmed: {topic}")
    
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
