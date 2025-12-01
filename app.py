"""  
FastAPI Backend cho hệ thống Agentic RAG
"""
import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Header, Security, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import os
from pathlib import Path
import asyncio
from langchain_core.messages import HumanMessage
from jose import JWTError, jwt

from agent.graph import compiled_graph
from agent.memory import session_memory
from agent.tools.analyzer_tool import analyze_with_data
from agent.tools.mindmap_tool import generate_mindmap_with_context
from agent.tools.retriever_tool import get_context
from agent.tools.summarizer_tool import summarize_old_messages

# Load environment variables
load_dotenv()

# Kiểm tra API key
if not os.getenv("OPENAI_API_KEY"):
    print("CẢNH BÁO: OPENAI_API_KEY chưa được thiết lập!")

# JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Khởi tạo FastAPI app
app = FastAPI(
    title="Agentic RAG - Trợ giảng Toán lớp 4",
    description="Hệ thống RAG với LangGraph cho việc trợ giảng Toán lớp 4",
    version="1.0.0",
    swagger_ui_parameters={
        "persistAuthorization": True  # Lưu token khi refresh page
    }
)

# CORS middleware - Allow all origins without credentials for simplicity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when using allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Add CORS headers middleware for preflight
@app.middleware("http")
async def add_cors_headers(request, call_next):
    # Handle OPTIONS preflight
    if request.method == "OPTIONS":
        print(f"🔍 OPTIONS request: {request.url.path}")
        print(f"   Origin: {request.headers.get('origin', 'N/A')}")
        print(f"   Access-Control-Request-Headers: {request.headers.get('access-control-request-headers', 'N/A')}")
        
        response = Response(status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "3600"
        return response
    
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Expose-Headers"] = "*"
    return response


# Security scheme for Swagger UI
security = HTTPBearer()


# JWT Authentication Helper
async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Decode JWT token và trả về user_id
    
    Args:
        credentials: HTTPAuthorizationCredentials from Security(HTTPBearer())
        
    Returns:
        user_id: ID của user từ JWT payload
        
    Raises:
        HTTPException 401: Nếu token invalid hoặc missing
    """
    try:
        # Get token from credentials
        token = credentials.credentials
        
        # Decode JWT
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # Extract user_id (support multiple payload formats)
        user_id = payload.get("sub") or payload.get("user_id") or payload.get("userId")
        
        if not user_id:
            raise HTTPException(
                status_code=401, 
                detail="Token payload missing user identifier (sub/user_id/userId)"
            )
        
        return str(user_id)
        
    except JWTError as e:
        raise HTTPException(
            status_code=401, 
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=401, 
            detail=f"Authentication error: {str(e)}"
        )


# Standard API Response wrapper
class APIResponse(BaseModel):
    status: str  # "success" | "error"
    data: Optional[Any] = None
    message: str
    createdAt: str = Field(..., alias="createdAt")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {"key": "value"},
                    "message": "Operation completed successfully",
                    "createdAt": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


# Request/Response models
class ChatRequest(BaseModel):
    userMessage: str = Field(..., alias="userMessage")
    lessonId: Optional[int] = Field(None, alias="lessonId")  # Lesson ID (numeric)
    
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "examples": [
                {
                    "userMessage": "Cho em hỏi số 12345 có mấy chữ số?",
                    "lessonId": 1
                },
                {
                    "userMessage": "Giải thích cho em hiểu về phân số với nhé cô",
                    "lessonId": 2
                }
            ]
        }
    }


class ChatData(BaseModel):
    reply: str
    intent: str


class ChatResponse(APIResponse):
    data: Optional[ChatData] = None


class AnalyzerRequest(BaseModel):
    lessonId: Optional[int] = Field(None, serialization_alias="lessonId")  # Lesson ID (numeric)
    topic: Optional[str] = ""
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "lessonId": 1,
                    "topic": "phân số"
                }
            ]
        }
    }


class AnalyzerData(BaseModel):
    analysis: str
    level: str
    levelReason: str = Field(..., serialization_alias="levelReason")


class AnalyzerResponse(APIResponse):
    data: Optional[AnalyzerData] = None
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {
                        "analysis": "Học sinh đã hiểu khái niệm cơ bản...",
                        "level": "Intermediate",
                        "levelReason": "Học sinh trả lời đúng 80% câu hỏi"
                    },
                    "message": "Analysis completed",
                    "createdAt": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


class MindmapRequest(BaseModel):
    lessonId: int = Field(..., serialization_alias="lessonId")  # Lesson ID (numeric, required)
    topic: Optional[str] = ""
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "lessonId": 1,
                    "topic": "số tự nhiên"
                }
            ]
        }
    }


class MindmapData(BaseModel):
    mindmapData: Dict[str, Any] = Field(..., serialization_alias="mindmapData")
    lessonId: int = Field(..., serialization_alias="lessonId")
    title: str


class MindmapResponse(APIResponse):
    data: Optional[MindmapData] = None
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {
                        "mindmapData": {
                            "nodes": [],
                            "edges": []
                        },
                        "lessonId": 1,
                        "title": "Ôn tập các số đến 100000"
                    },
                    "message": "Mindmap generated successfully",
                    "createdAt": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


class HealthResponse(APIResponse):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": None,
                    "message": "Agentic RAG API đang hoạt động",
                    "createdAt": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


class LessonInfo(BaseModel):
    lessonId: int = Field(..., serialization_alias="lessonId")
    title: str


class LessonsData(BaseModel):
    lessons: List[LessonInfo]


class LessonsResponse(APIResponse):
    data: Optional[LessonsData] = None
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {
                        "lessons": [
                            {
                                "lessonId": 1,
                                "title": "Ôn tập các số đến 100000"
                            },
                            {
                                "lessonId": 2,
                                "title": "Phân số"
                            }
                        ]
                    },
                    "message": "Lessons retrieved successfully",
                    "createdAt": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


class UserLevelData(BaseModel):
    userId: str = Field(..., serialization_alias="userId")
    level: str
    levelReason: str = Field(..., serialization_alias="levelReason")
    messagesCount: int = Field(..., serialization_alias="messagesCount")
    hasConversation: bool = Field(..., serialization_alias="hasConversation")


class UserLevelResponse(APIResponse):
    data: Optional[UserLevelData] = None
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {
                        "userId": "user_123",
                        "level": "Intermediate",
                        "levelReason": "Đã hoàn thành 10 bài tập",
                        "messagesCount": 15,
                        "hasConversation": True
                    },
                    "message": "User level retrieved",
                    "createdAt": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


@app.get("/api/health", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return HealthResponse(
        status="success",
        data=None,
        message="Agentic RAG API đang hoạt động",
        createdAt=datetime.now(timezone.utc).isoformat()
    )


@app.get("/api/lessons", response_model=LessonsResponse)
async def get_lessons():
    """
    Lấy danh sách các bài giảng có sẵn từ database
    
    Returns:
        LessonsResponse với danh sách bài giảng (id và title)
    """
    try:
        from database.db_connection import get_db_connection
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title 
                FROM lessons 
                WHERE status = 'indexed'
                ORDER BY id;
            """)
            rows = cursor.fetchall()
            cursor.close()
        
        lessons = [LessonInfo(lessonId=row[0], title=row[1]) for row in rows]
        
        return LessonsResponse(
            status="success",
            data=LessonsData(lessons=lessons),
            message="Lessons retrieved successfully",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    
    except Exception as e:
        return LessonsResponse(
            status="error",
            data=None,
            message=f"Lỗi khi lấy danh sách bài giảng: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


@app.post(
    "/api/agent/chat",
    response_model=ChatResponse,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        "short_answer": {
                            "summary": "Câu trả lời ngắn (Normal Intent)",
                            "description": "Response cho câu hỏi đơn giản không cần giải thích sâu",
                            "value": {
                                "status": "success",
                                "data": {
                                    "reply": "Số 12345 có 5 chữ số. Đây là số tự nhiên gồm: 1 chục nghìn, 2 nghìn, 3 trăm, 4 chục và 5 đơn vị.",
                                    "intent": "normal"
                                },
                                "message": "Chat processed successfully",
                                "createdAt": "2025-11-26T10:30:00.123Z"
                            }
                        },
                        "deep_explanation": {
                            "summary": "Giải thích sâu (Deep Intent) - Streaming",
                            "description": "Response cho câu hỏi cần giải thích chi tiết (sẽ được stream qua SSE)",
                            "value": {
                                "status": "success",
                                "data": {
                                    "reply": "### Giải thích chi tiết về Phân số\n\n**1. Khái niệm cơ bản**\nPhân số là một cách biểu diễn các phần của một tổng thể. Ví dụ: nếu chia một cái bánh thành 4 phần bằng nhau và lấy 3 phần, ta có phân số 3/4.\n\n**2. Thành phần của phân số**\n- Tử số: Số phần ta lấy (số ở trên)\n- Mẫu số: Tổng số phần bằng nhau (số ở dưới)\n- Gạch ngang: Dấu chia\n\n**3. Ví dụ minh họa**\nCho 1 hình tròn chia thành 8 phần bằng nhau:\n- Nếu tô màu 3 phần → 3/8\n- Nếu tô màu 5 phần → 5/8\n\n**4. Lưu ý quan trọng**\n- Mẫu số không bao giờ bằng 0\n- Tử số có thể bằng 0 (nghĩa là không lấy phần nào)\n- Khi tử số = mẫu số → phân số = 1 (lấy hết)\n\n**5. Bài tập thực hành**\nHãy biểu diễn phân số sau bằng hình vẽ: 2/5",
                                    "intent": "deep"
                                },
                                "message": "Deep explanation provided",
                                "createdAt": "2025-11-26T10:35:15.456Z"
                            }
                        }
                    }
                },
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "description": "Server-Sent Events stream for deep explanations"
                    }
                }
            }
        }
    }
)
async def chat_endpoint(
    request: ChatRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Unified chat endpoint - Tự động quyết định streaming hay non-streaming dựa vào intent
    Requires JWT token in Authorization header
    
    Args:
        request: ChatRequest chứa user_message và id (lesson id)
        user_id: User ID extracted from JWT token (auto-injected)
        
    Returns:
        - ChatResponse (JSON) nếu intent = normal (câu trả lời ngắn)
        - StreamingResponse (SSE) nếu intent = deep/explain (câu trả lời dài)
    """
    try:
        # Use user_id as thread_id
        thread_id = user_id
        
        # Lấy session hiện tại
        session = session_memory.get_session(thread_id)
        
        # Lưu user message vào session
        session["messages"].append({
            "role": "user",
            "content": request.userMessage
        })
        
        # Tạo input state (convert lessonId to string for compatibility)
        input_state = {
            "messages": [HumanMessage(content=request.userMessage)],
            "lesson_id": str(request.lessonId) if request.lessonId else ""
        }
        
        # Config để load history
        config = {"configurable": {"thread_id": thread_id}}
        
        # Tối ưu: Summarize messages nếu cần
        try:
            current_state = compiled_graph.get_state(config)
            if current_state and current_state.values.get("messages"):
                all_messages = current_state.values["messages"] + [HumanMessage(content=request.user_message)]
                if len(all_messages) > 6:
                    summarized = summarize_old_messages(all_messages, keep_recent=4)
                    input_state["messages"] = summarized
        except:
            pass
        
        # STEP 1: Invoke graph để lấy intent
        result = compiled_graph.invoke(input_state, config)
        intent = result.get("intent", "normal")
        
        # STEP 2: Quyết định streaming hay non-streaming dựa vào intent
        if intent in ["deep", "explain"]:
            # STREAMING: Câu trả lời dài, cần suy nghĩ chuyên sâu
            async def generate_stream():
                try:
                    full_response = ""
                    
                    # Re-invoke với astream để lấy chunks
                    async for event in compiled_graph.astream(input_state, config):
                        if "messages" in event:
                            for msg in event["messages"]:
                                if hasattr(msg, 'content') and msg.content:
                                    chunk = msg.content
                                    full_response = chunk
                                    yield f"data: {json.dumps({'chunk': chunk, 'done': False, 'intent': intent})}\n\n"
                    
                    # Lưu response vào session
                    session["messages"].append({
                        "role": "assistant",
                        "content": full_response
                    })
                    session_memory.update_session(thread_id, session)
                    
                    # Send final event
                    yield f"data: {json.dumps({'chunk': '', 'done': True, 'user_id': user_id, 'intent': intent})}\n\n"
                    
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            return StreamingResponse(generate_stream(), media_type="text/event-stream")
        
        else:
            # NON-STREAMING: Câu trả lời ngắn, trả về ngay
            messages = result.get("messages", [])
            if messages:
                last_message = messages[-1]
                reply = last_message.content if hasattr(last_message, 'content') else str(last_message)
            else:
                reply = "Xin lỗi, em không thể trả lời câu hỏi này."
            
            # Lưu response vào session
            session["messages"].append({
                "role": "assistant",
                "content": reply
            })
            session_memory.update_session(thread_id, session)
            
            return ChatResponse(
                status="success",
                data=ChatData(
                    reply=reply,
                    intent=intent
                ),
                message="Chat processed successfully",
                createdAt=datetime.now(timezone.utc).isoformat()
            )
    
    except Exception as e:
        return ChatResponse(
            status="error",
            data=None,
            message=f"Lỗi khi xử lý chat: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


@app.post("/api/agent/analyzer", response_model=AnalyzerResponse)
async def analyzer_endpoint(
    request: AnalyzerRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Endpoint phân tích buổi học
    Requires JWT token in Authorization header
    
    Args:
        request: AnalyzerRequest chứa id (lesson id) và topic (optional)
        user_id: User ID extracted from JWT token (auto-injected)
        
    Returns:
        AnalyzerResponse với kết quả phân tích
    """
    try:
        # Use user_id as thread_id
        thread_id = user_id
        
        # Lấy conversation history từ session
        conversation_history = session_memory.get_conversation_history(thread_id)
        
        if not conversation_history:
            raise HTTPException(
                status_code=404,
                detail=f"Không tìm thấy lịch sử hội thoại cho user_id: {user_id}"
            )
        
        # Lấy transcript (Tối ưu: k=10→5 để giảm tokens cho analyzer)
        topic = request.topic if request.topic else "Toán lớp 4"
        lesson_id = str(request.lessonId) if request.lessonId else None
        transcript = get_context(topic, k=5, lesson_id=lesson_id)
        
        # Phân tích (bao gồm đánh giá level)
        result = analyze_with_data(conversation_history, transcript)
        
        # Lưu level vào session
        session = session_memory.get_session(thread_id)
        session["latest_level"] = result["level"]
        session["level_reason"] = result["level_reason"]
        session_memory.update_session(thread_id, session)
        
        return AnalyzerResponse(
            status="success",
            data=AnalyzerData(
                analysis=result["analysis"],
                level=result["level"],
                levelReason=result["level_reason"]
            ),
            message="Analysis completed successfully",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    
    except HTTPException as he:
        return AnalyzerResponse(
            status="error",
            data=None,
            message=he.detail,
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return AnalyzerResponse(
            status="error",
            data=None,
            message=f"Lỗi khi phân tích: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


@app.post("/api/lessons/mindmap", response_model=MindmapResponse)
async def mindmap_endpoint(request: MindmapRequest):
    """
    Endpoint tạo sơ đồ tư duy cho bài học
    
    Args:
        request: MindmapRequest chứa id (lesson id) và topic (optional)
        
    Returns:
        MindmapResponse với mindmap JSON cho React Flow
    """
    try:
        # Get lesson info
        from database.lessons_repository import get_lesson
        lesson = get_lesson(str(request.lessonId))
        if not lesson:
            raise HTTPException(
                status_code=404,
                detail=f"Không tìm thấy bài học với id: {request.lessonId}"
            )
        
        # Lấy context từ bài học (Tối ưu: k=10→7 để giảm tokens)
        topic = request.topic if request.topic else "toàn bộ bài học"
        context = get_context(topic, k=7, lesson_id=str(request.lessonId))
        
        # Tạo mindmap
        mindmap_json_str = generate_mindmap_with_context(topic, context)
        
        # Parse JSON
        try:
            mindmap_data = json.loads(mindmap_json_str)
        except json.JSONDecodeError:
            # Fallback nếu không parse được
            mindmap_data = {
                "error": "Không thể tạo sơ đồ tư duy cho bài học này."
            }
        
        return MindmapResponse(
            status="success",
            data=MindmapData(
                mindmapData=mindmap_data,
                lessonId=request.lessonId,
                title=lesson["title"]
            ),
            message="Mindmap generated successfully",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    
    except Exception as e:
        return MindmapResponse(
            status="error",
            data=None,
            message=f"Lỗi khi tạo mindmap: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


@app.delete("/api/session")
async def clear_session(user_id: str = Depends(get_current_user)):
    """
    Xóa session của user hiện tại
    Requires JWT token in Authorization header
    
    Args:
        user_id: User ID extracted from JWT token (auto-injected)
    """
    try:
        session_memory.clear_session(user_id)
        return APIResponse(
            status="success",
            data=None,
            message=f"Đã xóa session của user {user_id}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return APIResponse(
            status="error",
            data=None,
            message=f"Lỗi khi xóa session: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


@app.get("/api/session")
async def get_session_info(user_id: str = Depends(get_current_user)):
    """
    Lấy thông tin session của user hiện tại
    Requires JWT token in Authorization header
    
    Args:
        user_id: User ID extracted from JWT token (auto-injected)
    """
    try:
        session = session_memory.get_session(user_id)
        return APIResponse(
            status="success",
            data={
                "userId": user_id,
                "messagesCount": len(session.get("messages", [])),
                "conversationHistory": session_memory.get_conversation_history(user_id)
            },
            message="Session retrieved successfully",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return APIResponse(
            status="error",
            data=None,
            message=f"Lỗi khi lấy session: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


@app.get("/api/user/level", response_model=UserLevelResponse)
async def get_user_level(user_id: str = Depends(get_current_user)):
    """
    Lấy level của user hiện tại
    Requires JWT token in Authorization header
    
    Args:
        user_id: User ID extracted from JWT token (auto-injected)
        
    Returns:
        UserLevelResponse với level, lý do, và thống kê conversation
    """
    try:
        session = session_memory.get_session(user_id)
        messages = session.get("messages", [])
        
        # Kiểm tra có conversation chưa
        if not messages:
            return UserLevelResponse(
                status="success",
                data=UserLevelData(
                    userId=user_id,
                    level="Beginner",
                    levelReason="Chưa có cuộc hội thoại nào",
                    messagesCount=0,
                    hasConversation=False
                ),
                message="User level retrieved",
                createdAt=datetime.now(timezone.utc).isoformat()
            )
        
        # Lấy level đã được lưu (từ analyzer)
        latest_level = session.get("latest_level")
        level_reason = session.get("level_reason")
        
        # Nếu chưa có level (chưa gọi analyzer), trả về Beginner
        if not latest_level:
            return UserLevelResponse(
                status="success",
                data=UserLevelData(
                    userId=user_id,
                    level="Beginner",
                    levelReason="Chưa được đánh giá. Vui lòng gọi /analyzer trước.",
                    messagesCount=len(messages),
                    hasConversation=True
                ),
                message="User level retrieved",
                createdAt=datetime.now(timezone.utc).isoformat()
            )
        
        return UserLevelResponse(
            status="success",
            data=UserLevelData(
                userId=user_id,
                level=latest_level,
                levelReason=level_reason or "",
                messagesCount=len(messages),
                hasConversation=True
            ),
            message="User level retrieved successfully",
            createdAt=datetime.now(timezone.utc).isoformat()
        )
    
    except Exception as e:
        return UserLevelResponse(
            status="error",
            data=None,
            message=f"Lỗi khi lấy level: {str(e)}",
            createdAt=datetime.now(timezone.utc).isoformat()
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
