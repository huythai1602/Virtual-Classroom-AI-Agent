"""
FastAPI Application - Clean Architecture
Agentic RAG System for Grade 4 Math
"""
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from config.settings import settings
from core.agent import agent
from core.memory import session_memory
from core.state import ChatContext
from models import ChatRequest, MindmapRequest, AnalyzerRequest
from tools import generate_mindmap_json, analyze_session, summarize_conversation
from utils import get_optional_user, get_user_id


# Initialize app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    swagger_ui_parameters={"persistAuthorization": True}
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    print(f"[{request.method}] {request.url.path} | Origin: {request.headers.get('origin', 'N/A')}")
    response = await call_next(request)
    return response


# CORS preflight handler
@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


# Health check
@app.get("/")
async def root():
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# ============================================================
# LESSONS ENDPOINT
# ============================================================

@app.get("/api/lessons")
async def get_lessons(
    subject: str = None,
    grade: int = None,
    user_id: str = Depends(get_optional_user)
):
    """
    Get Lessons - Retrieve all lessons with optional filters
    
    Query params:
    - subject: Filter by subject (e.g., "Toán")
    - grade: Filter by grade (e.g., 4)
    
    Returns: List of lessons
    """
    try:
        from repositories.lessons import get_all_lessons
        
        lessons = get_all_lessons(subject=subject, grade=grade)
        
        return {
            "status": "success",
            "data": lessons,
            "message": f"Retrieved {len(lessons)} lessons",
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "data": [],
            "message": f"Failed to retrieve lessons: {str(e)}",
            "createdAt": datetime.now(timezone.utc).isoformat()
        }


# ============================================================
# CHAT ENDPOINT (Streaming with Auto Intent Detection)
# ============================================================

async def stream_agent_response(thread_id: str, question: str, lesson_id: int = None, user_id: str = None):
    """Stream agent response via SSE with automatic intent detection"""
    try:
        # Get or create session (with persistence)
        session = session_memory.get_session(thread_id, user_id=user_id)
        messages = session.get("messages", [])
        
        # Summarize old messages if needed
        if len(messages) > 10:
            messages = summarize_conversation(messages, keep_recent=6)
            session_memory.update_session(thread_id, {"messages": messages})
        
        # Add user message
        user_message = HumanMessage(content=question)
        messages.append(user_message)
        
        # Prepare config
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50
        }
        
        # Prepare input (convert lesson_id to string for agent)
        input_data = {
            "messages": messages,
            "lesson_id": str(lesson_id) if lesson_id else "",
            "thread_id": thread_id  # Pass thread_id for conversation context
        }
        
        # Stream response (agent auto-detects intent: normal or deep)
        buffer = ""
        async for event in agent.astream(input_data, config):
            for value in event.values():
                if "messages" in value:
                    ai_message = value["messages"][-1]
                    content = ai_message.content
                    
                    # Send word by word
                    words = content.split()
                    for word in words:
                        buffer += word + " "
                        yield f"data: {buffer.strip()}\n\n"
                        await asyncio.sleep(0.05)
        
        # Update session with persistence
        session["messages"] = messages
        session_memory.update_session(thread_id, session, persist=True)
        
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        error_msg = f"Lỗi: {str(e)}"
        yield f"data: {error_msg}\n\n"
        yield "data: [DONE]\n\n"


@app.post("/api/agent/chat")
async def agent_chat(
    request: ChatRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Chat Endpoint - Streaming response with auto intent detection
    
    Request body:
    {
        "question": "Câu hỏi của học sinh",
        "lesson_id": 1  // optional integer
    }
    
    Headers:
    {
        "Authorization": "Bearer <JWT_TOKEN>"
    }
    
    Returns: text/event-stream (SSE)
    
    Note: Agent automatically detects intent (normal/deep) based on question keywords
    """
    # Auto-generate thread_id from user_id
    thread_id = f"user_{user_id}_session"
    
    return StreamingResponse(
        stream_agent_response(thread_id, request.question, request.lesson_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================
# MINDMAP ENDPOINT
# ============================================================

@app.post("/api/lessons/mindmap")
async def create_mindmap(
    request: MindmapRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Generate mindmap JSON for React Flow (JWT Required)
    
    Request body:
    {
        "topic": "Phân số",
        "lesson_id": 1  // optional integer
    }
    
    Returns:
    {
        "status": "success",
        "data": {
            "mindmap": {...},
            "topic": "Phân số"
        },
        "message": "Mindmap created",
        "createdAt": "2025-12-03T..."
    }
    """
    try:
        # Convert lesson_id to string for internal functions
        lesson_id_str = str(request.lesson_id) if request.lesson_id else None
        mindmap_data = generate_mindmap_json(request.topic, lesson_id_str)
        
        return {
            "status": "success",
            "data": {
                "mindmap": mindmap_data,
                "topic": request.topic
            },
            "message": "Mindmap created successfully",
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"Failed to create mindmap: {str(e)}",
            "createdAt": datetime.now(timezone.utc).isoformat()
        }


# ============================================================
# ANALYZER ENDPOINT
# ============================================================

@app.post("/api/agent/analyzer")
async def analyze(
    request: AnalyzerRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Analyze learning session (JWT Required)
    
    Request body:
    {
        "lesson_id": 1  // optional integer
    }
    
    Returns:
    {
        "status": "success",
        "data": {
            "analysis": "...",
            "level": "Tốt",
            "level_reason": "..."
        },
        "message": "Analysis completed",
        "createdAt": "..."
    }
    """
    try:
        # Auto-generate thread_id from user_id
        thread_id = f"user_{user_id}_session"
        
        # Get conversation history
        conversation_history = session_memory.get_conversation_history(thread_id)
        
        if not conversation_history:
            return {
                "status": "error",
                "data": None,
                "message": "No conversation found for this user",
                "createdAt": datetime.now(timezone.utc).isoformat()
            }
        
        # Analyze (convert lesson_id to string)
        lesson_id_str = str(request.lesson_id) if request.lesson_id else None
        result = analyze_session(conversation_history, lesson_id_str)
        
        return {
            "status": "success",
            "data": result,
            "message": "Analysis completed",
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "data": None,
            "message": f"Analysis failed: {str(e)}",
            "createdAt": datetime.now(timezone.utc).isoformat()
        }


# ============================================================
# SESSION MANAGEMENT
# ============================================================

@app.get("/api/session")
async def get_session_info(
    user_id: str = Depends(get_user_id)
):
    """
    Get Session Info - Retrieve current session status
    
    Returns session metadata (message count, conversation status)
    """
    thread_id = f"user_{user_id}_session"
    conversation_history = session_memory.get_conversation_history(thread_id)
    
    return {
        "status": "success",
        "data": {
            "has_conversation": bool(conversation_history),
            "message_count": conversation_history.count("\n") if conversation_history else 0
        },
        "message": "Session info retrieved",
        "createdAt": datetime.now(timezone.utc).isoformat()
    }


@app.delete("/api/session")
async def clear_session(
    user_id: str = Depends(get_user_id)
):
    """
    Clear Session - Delete user's conversation history
    
    Removes all messages from current session
    """
    thread_id = f"user_{user_id}_session"
    session_memory.clear_session(thread_id)
    
    return {
        "status": "success",
        "data": {"cleared": True},
        "message": "Session cleared",
        "createdAt": datetime.now(timezone.utc).isoformat()
    }


# ============================================================
# USER LEVEL ENDPOINT (Placeholder)
# ============================================================

@app.get("/api/user/level")
async def get_user_level(
    user_id: str = Depends(get_user_id)
):
    """
    Get User Level - Retrieve user's learning level assessment
    
    Returns user performance metrics and level
    """
    # TODO: Implement user level tracking in database
    return {
        "status": "success",
        "data": {
            "user_id": user_id,
            "level": "Chưa đánh giá",
            "message": "Chưa có đủ dữ liệu để đánh giá"
        },
        "message": "User level retrieved",
        "createdAt": datetime.now(timezone.utc).isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
