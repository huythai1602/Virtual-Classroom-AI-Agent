"""
FastAPI Application - Clean Architecture
Agentic RAG System for Grade 4 Math
"""
import asyncio
import json
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, Header, Response, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from config.settings import settings
from core.agent import agent
from core.memory import session_memory
from core.state import ChatContext
from models import ChatRequest, MindmapRequest, AnalyzerRequest
from models.responses import StandardResponse, MindmapData, AnalyzerData, LessonsData, SessionData, UserLevelData, LessonItem
from tools import generate_mindmap_json, analyze_session, summarize_conversation
from utils import get_optional_user, get_user_id


# Security scheme for Swagger UI
security = HTTPBearer(
    scheme_name="Bearer Token",
    description="Enter your JWT token (without 'Bearer' prefix)"
)

# Initialize app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "docExpansion": "none"
    }
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


@app.get(
    "/health",
    response_model=StandardResponse[dict],
    summary="Health Check",
    description="Check if the API is running"
)
async def health_check():
    return StandardResponse(
        status="success",
        data={"healthy": True},
        message="API is running",
        createdAt=datetime.now(timezone.utc).isoformat()
    )


# ============================================================
# LESSONS ENDPOINT
# ============================================================

@app.get(
    "/api/lessons",
    response_model=StandardResponse[LessonsData],
    summary="Get All Lessons",
    description="Retrieve all lessons with optional filters",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "lessons": [
                                {
                                    "lessonId": "bai_2_phan_so",
                                    "title": "Phân số",
                                    "subject": "Toán",
                                    "grade": 4,
                                    "totalChunks": 32,
                                    "status": "active"
                                }
                            ],
                            "total": 1
                        },
                        "message": "Retrieved 1 lessons",
                        "createdAt": "2025-12-03T18:30:00Z"
                    }
                }
            }
        }
    }
)
async def get_lessons(
    subject: str = None,
    grade: int = None,
    user_id: str = Depends(get_optional_user)
):
    try:
        from repositories.lessons import get_all_lessons
        
        lessons_raw = get_all_lessons(subject=subject, grade=grade)
        
        # Convert to camelCase
        lessons = [
            LessonItem(
                lessonId=lesson["lesson_id"],
                title=lesson["title"],
                subject=lesson["subject"],
                grade=lesson["grade"],
                totalChunks=lesson["total_chunks"],
                status=lesson["status"]
            )
            for lesson in lessons_raw
        ]
        
        return StandardResponse(
            status="success",
            data=LessonsData(lessons=lessons, total=len(lessons)),
            message=f"Retrieved {len(lessons)} lessons",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return StandardResponse(
            status="error",
            data=None,
            message=f"Failed to retrieve lessons: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


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
        full_response = ""
        
        async for event in agent.astream(input_data, config):
            for value in event.values():
                if "messages" in value:
                    ai_message = value["messages"][-1]
                    content = ai_message.content
                    
                    # Check if this is new content
                    if content != full_response:
                        # Get the new part
                        new_content = content[len(full_response):]
                        full_response = content
                        
                        # Send chunk
                        chunk_data = {
                            "type": "content",
                            "chunk": new_content,
                            "fullText": full_response
                        }
                        yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
        
        # Add AI response to messages
        if full_response:
            from langchain_core.messages import AIMessage
            messages.append(AIMessage(content=full_response))
        
        # Update session with persistence
        session["messages"] = messages
        session_memory.update_session(thread_id, session, persist=True)
        
        # Send done signal
        done_data = {"type": "done", "fullText": full_response}
        yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        error_data = {"type": "error", "message": f"Lỗi: {str(e)}"}
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


@app.post(
    "/api/agent/chat",
    summary="Chat with AI Agent",
    description="Stream AI responses with automatic intent detection (normal/deep mode)",
    responses={
        200: {
            "description": "Streaming response (Server-Sent Events)",
            "content": {
                "text/event-stream": {
                    "example": "data: Phân số là số biểu diễn một phần của tổng thể...\n\ndata: [DONE]\n\n"
                }
            }
        }
    }
)
async def agent_chat(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Security(security),
    user_id: str = Depends(get_user_id)
):
    """
    **Chat Endpoint** - Streaming AI response
    
    **Authentication:** Bearer token in Authorization header
    
    **Request Body:**
    ```json
    {
        "userMessage": "Phân số là gì?",
        "lessonId": 2
    }
    ```
    
    **Returns:** Server-Sent Events (text/event-stream)
    
    **Features:**
    - Automatic intent detection (normal/deep)
    - Conversation history awareness
    - Context from lesson materials
    """
    # Auto-generate thread_id from user_id
    thread_id = f"user_{user_id}_session"
    
    return StreamingResponse(
        stream_agent_response(thread_id, request.userMessage, request.lessonId, user_id),
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

@app.post(
    "/api/lessons/mindmap",
    response_model=StandardResponse[MindmapData],
    summary="Generate Mindmap",
    description="Generate React Flow compatible mindmap JSON from topic",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "mindmap": {
                                "nodes": [
                                    {"id": "1", "data": {"label": "Phân số"}, "position": {"x": 0, "y": 0}}
                                ],
                                "edges": []
                            },
                            "topic": "Phân số"
                        },
                        "message": "Mindmap created successfully",
                        "createdAt": "2025-12-03T18:30:00Z"
                    }
                }
            }
        }
    }
)
async def create_mindmap(
    request: MindmapRequest,
    credentials: HTTPAuthorizationCredentials = Security(security),
    user_id: str = Depends(get_user_id)
):
    """
    **Generate Mindmap** - Create React Flow compatible mindmap
    
    **Authentication:** Bearer token in Authorization header
    
    **Request Body:**
    ```json
    {
        "topic": "Phân số",
        "lessonId": 2
    }
    ```
    """
    try:
        # Convert lessonId to string for internal functions
        lesson_id_str = str(request.lessonId) if request.lessonId else None
        mindmap_data = generate_mindmap_json(request.topic, lesson_id_str)
        
        return StandardResponse(
            status="success",
            data=MindmapData(
                mindmap=mindmap_data,
                topic=request.topic
            ),
            message="Mindmap created successfully",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return StandardResponse(
            status="error",
            data=None,
            message=f"Failed to create mindmap: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


# ============================================================
# ANALYZER ENDPOINT
# ============================================================

@app.post(
    "/api/agent/analyzer",
    response_model=StandardResponse[AnalyzerData],
    summary="Analyze Student Session",
    description="Get AI-powered analysis of student's understanding and performance",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "analysis": "Học sinh đã nắm vững khái niệm phân số cơ bản, có thể nhận biết và đọc phân số chính xác. Tuy nhiên, cần luyện tập thêm về so sánh phân số.",
                            "level": "Khá",
                            "levelReason": "Trả lời đúng 75% câu hỏi, hiểu rõ khái niệm cơ bản nhưng chưa thạo về ứng dụng",
                            "threadId": "user_123_session"
                        },
                        "message": "Analysis completed successfully",
                        "createdAt": "2025-12-03T18:30:00Z"
                    }
                }
            }
        }
    }
)
async def analyzer(
    request: AnalyzerRequest,
    credentials: HTTPAuthorizationCredentials = Security(security),
    user_id: str = Depends(get_user_id)
):
    """
    **Session Analyzer** - AI analysis of student understanding
    
    **Authentication:** Bearer token in Authorization header
    
    **Request Body:**
    ```json
    {
        "topic": "Phân số",
        "lessonId": 2
    }
    ```
    
    **Analysis includes:**
    - Detailed understanding assessment
    - Proficiency level (Xuất sắc/Giỏi/Khá/Trung bình)
    - Reasoning for the level
    - Specific recommendations
    """
    try:
        # Auto-generate thread_id from user_id
        thread_id = f"user_{user_id}_session"
        
        # Get session
        session = session_memory.get_session(thread_id, user_id=user_id)
        messages = session.get("messages", [])
        
        if not messages:
            return StandardResponse(
                status="error",
                data=None,
                message="No conversation history found",
                createdAt=datetime.now(timezone.utc).isoformat()
            )
        
        # Convert lessonId to string
        lesson_id_str = str(request.lessonId) if request.lessonId else None
        
        # Analyze session with topic
        analysis_result = analyze_session(messages, lesson_id_str, topic=request.topic)
        
        return StandardResponse(
            status="success",
            data=AnalyzerData(
                analysis=analysis_result["analysis"],
                level=analysis_result["level"],
                levelReason=analysis_result["level_reason"],
                threadId=thread_id
            ),
            message="Analysis completed successfully",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return StandardResponse(
            status="error",
            data=None,
            message=f"Analysis failed: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


# ============================================================
# SESSION MANAGEMENT
# ============================================================

@app.get(
    "/api/session",
    response_model=StandardResponse[SessionData],
    summary="Get Session Info",
    description="Retrieve current session information",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "threadId": "user_123_session",
                            "messageCount": 10,
                            "lastActivity": "2025-12-03T18:30:00Z"
                        },
                        "message": "Session info retrieved",
                        "createdAt": "2025-12-03T18:30:00Z"
                    }
                }
            }
        }
    }
)
async def get_session_info(
    credentials: HTTPAuthorizationCredentials = Security(security),
    user_id: str = Depends(get_user_id)
):
    """
    **Get Session Info** - Retrieve current session data
    
    **Authentication:** Bearer token in Authorization header
    """
    try:
        thread_id = f"user_{user_id}_session"
        session = session_memory.get_session(thread_id, user_id=user_id)
        messages = session.get("messages", [])
        
        return StandardResponse(
            status="success",
            data=SessionData(
                threadId=thread_id,
                messageCount=len(messages),
                lastActivity=session.get("updated_at", datetime.now(timezone.utc).isoformat())
            ),
            message="Session info retrieved",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return StandardResponse(
            status="error",
            data=None,
            message=f"Failed to retrieve session: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


@app.delete(
    "/api/session",
    response_model=StandardResponse[dict],
    summary="Clear Session",
    description="Delete conversation history and reset session",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {"cleared": True},
                        "message": "Session cleared successfully",
                        "createdAt": "2025-12-03T18:30:00Z"
                    }
                }
            }
        }
    }
)
async def clear_session(
    credentials: HTTPAuthorizationCredentials = Security(security),
    user_id: str = Depends(get_user_id)
):
    """
    **Clear Session** - Delete all conversation history
    
    **Authentication:** Bearer token in Authorization header
    """
    try:
        thread_id = f"user_{user_id}_session"
        session_memory.clear_session(thread_id)
        
        return StandardResponse(
            status="success",
            data={"cleared": True},
            message="Session cleared successfully",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return StandardResponse(
            status="error",
            data=None,
            message=f"Failed to clear session: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


# ============================================================
# USER LEVEL ENDPOINT (Placeholder)
# ============================================================

@app.get(
    "/api/user/level",
    response_model=StandardResponse[UserLevelData],
    summary="Get User Level",
    description="Retrieve user's proficiency level and progress",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "level": "Intermediate",
                            "score": 850,
                            "progress": 75.5
                        },
                        "message": "User level retrieved",
                        "createdAt": "2025-12-03T18:30:00Z"
                    }
                }
            }
        }
    }
)
async def get_user_level(
    credentials: HTTPAuthorizationCredentials = Security(security),
    user_id: str = Depends(get_user_id)
):
    """
    **Get User Level** - Retrieve proficiency level and progress
    
    **Authentication:** Bearer token in Authorization header
    
    **Note:** Placeholder endpoint - implement with actual level calculation logic
    """
    return StandardResponse(
        status="success",
        data=UserLevelData(
            level="Beginner",
            score=0,
            progress=0.0
        ),
        message="User level retrieved (placeholder)",
        createdAt=datetime.now(timezone.utc).isoformat()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
