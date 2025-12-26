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


def metadata_node(state: AgentState) -> dict:
    """Fetch lesson metadata with enrichmnent"""
    from repositories.lessons import get_lesson
    import json
    
    lesson_id = state.get("lesson_id", None)
    metadata = DEFAULT_METADATA.copy()
    
    if lesson_id:
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
    
    return {"metadata": metadata}


def retrieve_node(state: AgentState) -> dict:
    """Retrieve context from RAG with conversation awareness"""
    from services.rag.retriever import get_context
    from core.memory import session_memory
    
    query = state.get("current_query", "")
    intent = state.get("intent", "normal")
    lesson_id = state.get("lesson_id", None)
    thread_id = state.get("thread_id", "")
    
def retrieve_node(state: AgentState) -> dict:
    """Retrieve context from RAG with conversation awareness"""
    from services.rag.retriever import get_context
    # No longer depend on session_memory (local DB)
    
    query = state.get("current_query", "")
    intent = state.get("intent", "normal")
    lesson_id = state.get("lesson_id", None)
    messages = state.get("messages", [])
    
    # Get recent conversation for context from State (injected by app.py)
    conversation_window = ""
        if messages:
        # Use last 10 messages (excluding current query if it's there)
        # 5 turns of conversation should be enough context
        history_msgs = messages[:-1][-10:] 
        for msg in history_msgs:
            role = "Student" if isinstance(msg, HumanMessage) else "Teacher"
            conversation_window += f"{role}: {msg.content}\n"
    
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


def rewrite_node(state: AgentState) -> dict:
    """Rewrite query to be standalone based on history (Context Awareness)"""
    from langchain_core.messages import HumanMessage
    
    messages = state["messages"]
    if not messages:
        return {"current_query": ""}
        
    # Get last message (current user query)
    last_message = messages[-1]
    original_query = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    # Get recent history (excluding the very last new message for context)
    # We want to see what came BEFORE this query
    # However, state["messages"] includes the current query at the end.
    conversation_window = ""
    if len(messages) > 1:
        # Use last 10 messages as context for rewriting (5 turns)
        history_msgs = messages[:-1][-10:] 
        for msg in history_msgs:
            role = "Student" if isinstance(msg, HumanMessage) else "Teacher"
            conversation_window += f"{role}: {msg.content}\n"
            
    # If no history, no need to rewrite (or just identical)
    if not conversation_window:
        return {"current_query": original_query}
        
    # Format Rewrite Prompt
    prompt = format_prompt(
        "CONDENSE_QUESTION_PROMPT", # Special key string, or we import variable directly if not in dict
        # Wait, format_prompt uses kwargs matching keys in template. 
        # But prompts.py stores templates in SYSTEM_PROMPTS dict usually.
        # Let's import CONDENSE_QUESTION_PROMPT provided it's in config/prompts.py 
        # (I just added it as a variable, not in SYSTEM_PROMPTS dict yet. 
        #  Use direct string or add to dict. I will use direct variable import here or format manually).
        # To be safe and consistent with previous code usage (if any), let's see. 
        # Previous code used format_prompt with SYSTEM_PROMPTS["normal"]. 
        # I should assume I can import it.
    )
    
    # Let's do the import inside function to avoid circular if needed, or stick to pattern.
    from config.prompts import CONDENSE_QUESTION_PROMPT
    
    formatted_prompt = CONDENSE_QUESTION_PROMPT.format(
        chat_history=conversation_window,
        question=original_query
    )
    
    # Call LLM
    response = llm.invoke(formatted_prompt)
    rewritten_query = response.content.strip()
    
    print(f"🔄 Query Rewritten: '{original_query}' -> '{rewritten_query}'")
    
    return {"current_query": rewritten_query}


def mindmap_node(state: AgentState) -> dict:
    """Generate Mindmap Node"""
    from tools import generate_mindmap_json
    
    lesson_id = state.get("lesson_id")
    try:
        result = generate_mindmap_json(str(lesson_id))
        return {"final_output": result}
    except Exception as e:
        return {"final_output": {"error": str(e)}}


def analyzer_node(state: AgentState) -> dict:
    """Analyze Session Node"""
    from tools import analyze_session
    from repositories import chat_history as chat_repo
    
    lesson_id = state.get("lesson_id")
    user_id = state.get("user_id")
    
    # Needs full history string for analysis
    # If app.py didn't load it into messages, we fetch it here.
    # However, standard AgentState messages might be empty for analyzer task.
    
    try:
        # Fetch history from DB if not provided in messages or distinct format needed
        # Analyzer expects a string transcript.
        # We can re-fetch for safety or use what's passed.
        # Let's re-fetch to ensure we have the full session, 
        # as state["messages"] might be limited or empty in this flow.
        
        # Ensure user_id is int for DB
        db_user_id = int(str(user_id))
        messages = chat_repo.get_messages(db_user_id, str(lesson_id))
        
        history_str = ""
        for msg in messages:
            # msg is HumanMessage or AIMessage or generic structure from repo
            # Repo returns Pydantic models or dicts? msg.type suggests object.
            # Let's assume repo returns objects as per app.py usage.
            role = "Student" if getattr(msg, "type", "") == "human" else "AI"
            history_str += f"{role}: {getattr(msg, 'content', '')}\n"
            
        result = analyze_session(history_str, str(lesson_id), user_id=str(user_id))
        return {"final_output": result}
        
    except Exception as e:
        return {"final_output": {"error": str(e)}}


def route_task(state: AgentState) -> Literal["intent", "mindmap", "analyzer"]:
    """Route based on task type"""
    task = state.get("task", "chat")
    if task == "mindmap":
        return "mindmap"
    elif task == "analyzer":
        return "analyzer"
    return "intent"


def create_agent():
    """Create and compile LangGraph agent"""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("intent", intent_node)
    workflow.add_node("rewrite", rewrite_node)
    workflow.add_node("metadata", metadata_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("explain", explain_node)
    
    # New Nodes
    workflow.add_node("mindmap", mindmap_node)
    workflow.add_node("analyzer", analyzer_node)
    
    # Build edges
    # START -> route_task -> [intent, mindmap, analyzer]
    
    workflow.add_conditional_edges(
        START,
        route_task,
        {
            "intent": "intent",
            "mindmap": "mindmap",
            "analyzer": "analyzer"
        }
    )
    
    # Chat Flow
    workflow.add_edge("intent", "rewrite")
    workflow.add_edge("rewrite", "metadata")
    workflow.add_edge("metadata", "retrieve")
    
    workflow.add_conditional_edges(
        "retrieve",
        route_intent,
        {"answer": "answer", "explain": "explain"}
    )
    
    workflow.add_edge("answer", END)
    workflow.add_edge("explain", END)
    
    # Task Flow End
    workflow.add_edge("mindmap", END)
    workflow.add_edge("analyzer", END)
    
    # Compile with memory
    return workflow.compile(checkpointer=memory_saver)


# Global agent instance
agent = create_agent()
