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
from langchain_core.messages import HumanMessage, AIMessage

from config.settings import settings
from core.agent import agent
from core.memory import session_memory
from core.state import ChatContext
from models import ChatRequest, MindmapRequest, AnalyzerRequest
from models.responses import StandardResponse, MindmapData, AnalyzerData, LessonsData, SessionData, LessonItem, ChatData
from tools import summarize_conversation
from utils import get_optional_user, get_user_id
from services.rabbitmq import rabbitmq_service
from routers.audio import router as audio_router

from utils.auth import security

# Initialize app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "docExpansion": "none"
    }
)

@app.on_event("startup")
async def startup_event():
    print("🚀 Starting Agent Service...")
    
    # helper handler
    def handle_lesson_update(data):
        try:
            print(f"🔄 RabbitMQ: Received lesson update for {data.get('lesson_id')}")
            from services.ingestion.processor import IngestionService
            service = IngestionService()
            # process_event_data handles metadata extraction from title if needed
            # PULL MODEL: Fetch fresh data from Course Service
            lesson_id = data.get("lesson_id") or data.get("id")
            if not lesson_id:
                print("⚠️ RabbitMQ: No lesson_id in update event")
                return

            print(f"📥 Fetching fresh details for Lesson {lesson_id}...")
            # Pattern must match what Course Service expects. Validated as 'GET_LESSON'
            fresh_data = rabbitmq_service.rpc_call_safe("GET_LESSON", {"id": lesson_id})
            
            if not fresh_data:
                print(f"❌ Failed to fetch data for Lesson {lesson_id}")
                return
            
            if "err" in fresh_data or "error" in fresh_data:
                 print(f"❌ RPC Error for {lesson_id}: {fresh_data.get('err') or fresh_data.get('error')}")
                 return

            service.process_event_data(fresh_data, force=True)
            print(f"✅ RabbitMQ: Lesson {data.get('lesson_id')} processed successfully.")
        except Exception as e:
            print(f"❌ RabbitMQ Handler Error: {e}")

    # Initialize RabbitMQ connection and consumer
    try:
        rabbitmq_service.connect()
        
        # Start Consumer with Handlers
        handlers = {
            "lesson.updated": handle_lesson_update
        }
        rabbitmq_service.start_consumer(handlers)
        
    except Exception as e:
        print(f"⚠️ Warning: RabbitMQ Connection Failed on Startup: {e}")


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(audio_router)


# Logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    auth_header = request.headers.get('authorization')
    auth_status = f"Auth: {'PRESENT (' + str(len(auth_header)) + ' chars)' if auth_header else 'MISSING'}"
    print(f"[{request.method}] {request.url.path} | Origin: {request.headers.get('origin', 'N/A')} | {auth_status}")
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

from models.responses import StandardResponse, MindmapData, AnalyzerData, LessonsData, SessionData, LessonItem, ChatData

# ... (Previous imports are fine, just make sure ChatData is available if not adding it here - wait, I can't easily add it to the import line without knowing the exact line. Let's assume the user handles imports or I do another pass. Actually, I can replace the import line separately or just use fully qualified if needed, let's try to update the imports at the top first or just rewrite the endpoint and let Python resolve if I imported it. 
# Wait, I see "from models.responses import ..." at line 19. I should update that too.
# Let's do the endpoint replacement first, assuming I will fix imports.)

@app.post(
    "/api/agent/chat",
    response_model=StandardResponse[ChatData],
    summary="Chat with AI Agent",
    description="Get AI response with automatic intent detection (normal/deep mode)",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "reply": "Chào em, hôm nay chúng ta sẽ ôn tập về các số đến 100000 nhé! Em đã sẵn sàng chưa?",
                            "intent": "normal",
                            "createdAt": "2025-12-15T12:00:00Z"
                        },
                        "message": "Response generated",
                        "createdAt": "2025-12-15T12:00:00Z"
                    }
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
    **Chat Endpoint** - Get AI response
    
    **Authentication:** Bearer token in Authorization header
    
    **Request Body:**
    ```json
    {
        "userMessage": "Phân số là gì?",
        "lessonId": 2
    }
    ```
    """
    try:
        # Auto-generate thread_id from user_id
        # Unique thread_id per user AND lesson
        thread_id = f"user_{user_id}_lesson_{request.lessonId}"
        
        # Validate and convert user_id to int
        try:
            db_user_id = int(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid User ID (must be numeric for shared DB)")
            
        # Load history from Shared DB
        from repositories import chat_history as chat_repo
        messages = chat_repo.get_messages(db_user_id, request.lessonId)
        
        # Add current user message to DB
        chat_repo.add_message(db_user_id, request.lessonId, "user", request.userMessage)
        
        # Create input messages list (history + new)
        # Note: We append the new user message to the list for the Agent logic
        messages.append(HumanMessage(content=request.userMessage))
        
        # Prepare input
        input_data = {
            "messages": messages,
            "lesson_id": request.lessonId,
            "thread_id": thread_id
        }
        
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50
        }
        
        # Run agent
        result = await agent.ainvoke(input_data, config)
        
        # Extract response
        full_response = ""
        intent = "normal"
        
        if "messages" in result:
             # Find last AI message from the result
            for msg in reversed(result["messages"]):
                if hasattr(msg, 'type') and msg.type == 'ai':
                    full_response = msg.content
                    break
        
        # Rough intent detection from result state
        if "intent" in result:
            intent = result["intent"]
            
        # Save AI response to DB
        if full_response:
             chat_repo.add_message(db_user_id, request.lessonId, "ai", full_response)
        
        # We no longer use local session_memory for persistence
        # session_memory.update_session(thread_id, session, persist=True) # DEPRECATED
        
        return StandardResponse(
            status="success",
            data=ChatData(
                reply=full_response,
                intent=intent,
                createdAt=datetime.now(timezone.utc).isoformat()
            ),
            message="Response generated successfully",
            createdAt=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return StandardResponse(
            status="error",
            data=None,
            message=f"Agent failed: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


# ============================================================
# MINDMAP ENDPOINT
# ============================================================

@app.get(
    "/api/agent/mindmap/{lesson_id}",
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
                        "createdAt": "2025-12-15T12:00:00Z"
                    }
                }
            }
        }
    }
)
async def create_mindmap(
    lesson_id: str,
    credentials: HTTPAuthorizationCredentials = Security(security),
    user_id: str = Depends(get_user_id)
):
    """
    **Generate Mindmap** - Create React Flow compatible mindmap
    
    **Authentication:** Bearer token in Authorization header
    **Path Param:** `lesson_id` (e.g. 2, "bai_2_phan_so")
    """
    try:
        # Use Agent Unified Graph
        thread_id = f"user_{user_id}_lesson_{lesson_id}_mindmap" # Separate thread for isolation or reuse? 
        # Actually, mindmap doesn't depend on history much, but let's keep it consistent.
        
        input_data = {
            "task": "mindmap",
            "lesson_id": lesson_id,
            "user_id": user_id
        }
        
        config = {"configurable": {"thread_id": thread_id}}
        
        result = await agent.ainvoke(input_data, config)
        mindmap_data = result.get("final_output", {})
        
        if "error" in mindmap_data:
             raise Exception(mindmap_data["error"])
        
        return StandardResponse(
            status="success",
            data=MindmapData(
                mindmap=mindmap_data,
                topic=mindmap_data.get("topic", "")
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

@app.get(
    "/api/agent/analyzer/{lesson_id}",
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
                            "analysis": "Học sinh đã nắm vững khái niệm phân số. Tuy nhiên, cần rèn luyện thêm về kỹ năng quy đồng mẫu số...",
                            "level": "Khá",
                            "levelReason": "Trả lời đúng 80% câu hỏi về lý thuyết, nhưng sai ở bài tập vận dụng cao."
                        },
                        "message": "Analysis completed successfully",
                        "createdAt": "2025-12-15T12:00:00Z"
                    }
                }
            }
        }
    }
)
async def analyzer(
    lesson_id: str,
    credentials: HTTPAuthorizationCredentials = Security(security),
    user_id: str = Depends(get_user_id)
):
    """
    **Session Analyzer** - AI analysis of student understanding
    
    **Authentication:** Bearer token in Authorization header
    **Path Param:** `lesson_id` (e.g. 2, "bai_2_phan_so")
    
    **Analysis includes:**
    - Detailed understanding assessment
    - Proficiency level
    - Quiz performance (if available)
    - Specific recommendations
    """
    try:
        # Auto-generate thread_id from user_id
        thread_id = f"user_{user_id}_lesson_{lesson_id}"
        
        # Validate and convert user_id to int
        try:
            db_user_id = int(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid User ID (must be numeric for shared DB)")
            
        # Use Agent Unified Graph
        # Note: analyzer_node inside agent will fetch the history.
        
        input_data = {
            "task": "analyzer",
            "lesson_id": lesson_id,
            "user_id": user_id
        }
        
        config = {"configurable": {"thread_id": thread_id}}
        
        result = await agent.ainvoke(input_data, config)
        analysis_result = result.get("final_output", {})
        
        if "error" in analysis_result:
            raise Exception(analysis_result["error"])
        
        # Build response
        response_data = AnalyzerData(
            analysis=analysis_result.get("analysis", ""),
            level=analysis_result.get("level", ""),
            levelReason=analysis_result.get("level_reason", "")
        )
        
        return StandardResponse(
            status="success",
            data=response_data,
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
                            "threadId": "user_123_session_abc",
                            "messageCount": 10,
                            "lastActivity": "2025-12-15T18:30:00Z"
                        },
                        "message": "Session info retrieved",
                        "createdAt": "2025-12-15T18:30:00Z"
                    }
                }
            }
        }
    }
)
async def get_session_info(
    lesson_id: str = "general",
    credentials: HTTPAuthorizationCredentials = Security(security),
    user_id: str = Depends(get_user_id)
):
    """
    **Get Session Info** - Retrieve current session data
    
    **Authentication:** Bearer token in Authorization header
    **Query Param:** `lesson_id` (default: "general")
    """
    try:
        thread_id = f"user_{user_id}_lesson_{lesson_id}"
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
                        "createdAt": "2025-12-15T18:30:00Z"
                    }
                }
            }
        }
    }
)
async def clear_session(
    lesson_id: str = "general",
    credentials: HTTPAuthorizationCredentials = Security(security),
    user_id: str = Depends(get_user_id)
):
    """
    **Clear Session** - Delete all conversation history for a specific lesson
    
    **Authentication:** Bearer token in Authorization header
    **Query Param:** `lesson_id` (default: "general")
    """
    try:
        thread_id = f"user_{user_id}_lesson_{lesson_id}"
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






if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
