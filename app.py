"""  
FastAPI Backend cho hệ thống Agentic RAG
"""
import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    timestamp: str
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {"key": "value"},
                    "message": "Operation completed successfully",
                    "timestamp": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


# Request/Response models
class ChatRequest(BaseModel):
    user_message: str
    id: Optional[int] = None  # Lesson ID (numeric)
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_message": "Cho em hỏi số 12345 có mấy chữ số?",
                    "id": 1
                },
                {
                    "user_message": "Giải thích cho em hiểu về phân số với nhé cô",
                    "id": 2
                }
            ]
        }
    }


class ChatData(BaseModel):
    reply: str
    intent: str
    user_id: str


class ChatResponse(APIResponse):
    data: Optional[ChatData] = None


class AnalyzerRequest(BaseModel):
    id: Optional[int] = None  # Lesson ID (numeric)
    topic: Optional[str] = ""
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "topic": "phân số"
                }
            ]
        }
    }


class AnalyzerData(BaseModel):
    analysis: str
    user_id: str
    level: str
    level_reason: str


class AnalyzerResponse(APIResponse):
    data: Optional[AnalyzerData] = None
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {
                        "analysis": "Học sinh đã hiểu khái niệm cơ bản...",
                        "user_id": "user_123",
                        "level": "Intermediate",
                        "level_reason": "Học sinh trả lời đúng 80% câu hỏi"
                    },
                    "message": "Analysis completed",
                    "timestamp": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


class MindmapRequest(BaseModel):
    id: int  # Lesson ID (numeric, required)
    topic: Optional[str] = ""
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "topic": "số tự nhiên"
                }
            ]
        }
    }


class MindmapData(BaseModel):
    mindmap_data: Dict[str, Any]
    id: int
    title: str


class MindmapResponse(APIResponse):
    data: Optional[MindmapData] = None
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {
                        "mindmap_data": {
                            "nodes": [],
                            "edges": []
                        },
                        "id": 1,
                        "title": "Ôn tập các số đến 100000"
                    },
                    "message": "Mindmap generated successfully",
                    "timestamp": "2025-11-26T10:30:00Z"
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
                    "timestamp": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


class LessonInfo(BaseModel):
    id: int
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
                                "id": 1,
                                "title": "Ôn tập các số đến 100000"
                            },
                            {
                                "id": 2,
                                "title": "Phân số"
                            }
                        ]
                    },
                    "message": "Lessons retrieved successfully",
                    "timestamp": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


class UserLevelData(BaseModel):
    user_id: str
    level: str
    level_reason: str
    messages_count: int
    has_conversation: bool


class UserLevelResponse(APIResponse):
    data: Optional[UserLevelData] = None
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {
                        "user_id": "user_123",
                        "level": "Intermediate",
                        "level_reason": "Đã hoàn thành 10 bài tập",
                        "messages_count": 15,
                        "has_conversation": True
                    },
                    "message": "User level retrieved",
                    "timestamp": "2025-11-26T10:30:00Z"
                }
            ]
        }
    }


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return HealthResponse(
        status="success",
        data=None,
        message="Agentic RAG API đang hoạt động",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get("/lessons", response_model=LessonsResponse)
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
        
        lessons = [LessonInfo(id=row[0], title=row[1]) for row in rows]
        
        return LessonsResponse(
            status="success",
            data=LessonsData(lessons=lessons),
            message="Lessons retrieved successfully",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    except Exception as e:
        return LessonsResponse(
            status="error",
            data=None,
            message=f"Lỗi khi lấy danh sách bài giảng: {str(e)}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )


@app.post(
    "/chat",
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
                                    "intent": "normal",
                                    "user_id": "user_123"
                                },
                                "message": "Chat processed successfully",
                                "timestamp": "2025-11-26T10:30:00.123Z"
                            }
                        },
                        "deep_explanation": {
                            "summary": "Giải thích sâu (Deep Intent) - Streaming",
                            "description": "Response cho câu hỏi cần giải thích chi tiết (sẽ được stream qua SSE)",
                            "value": {
                                "status": "success",
                                "data": {
                                    "reply": "### Giải thích chi tiết về Phân số\n\n**1. Khái niệm cơ bản**\nPhân số là một cách biểu diễn các phần của một tổng thể. Ví dụ: nếu chia một cái bánh thành 4 phần bằng nhau và lấy 3 phần, ta có phân số 3/4.\n\n**2. Thành phần của phân số**\n- Tử số: Số phần ta lấy (số ở trên)\n- Mẫu số: Tổng số phần bằng nhau (số ở dưới)\n- Gạch ngang: Dấu chia\n\n**3. Ví dụ minh họa**\nCho 1 hình tròn chia thành 8 phần bằng nhau:\n- Nếu tô màu 3 phần → 3/8\n- Nếu tô màu 5 phần → 5/8\n\n**4. Lưu ý quan trọng**\n- Mẫu số không bao giờ bằng 0\n- Tử số có thể bằng 0 (nghĩa là không lấy phần nào)\n- Khi tử số = mẫu số → phân số = 1 (lấy hết)\n\n**5. Bài tập thực hành**\nHãy biểu diễn phân số sau bằng hình vẽ: 2/5",
                                    "intent": "deep",
                                    "user_id": "user_456"
                                },
                                "message": "Deep explanation provided",
                                "timestamp": "2025-11-26T10:35:15.456Z"
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
            "content": request.user_message
        })
        
        # Tạo input state (convert id to string for compatibility)
        input_state = {
            "messages": [HumanMessage(content=request.user_message)],
            "lesson_id": str(request.id) if request.id else ""
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
                    intent=intent,
                    user_id=user_id
                ),
                message="Chat processed successfully",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
    
    except Exception as e:
        return ChatResponse(
            status="error",
            data=None,
            message=f"Lỗi khi xử lý chat: {str(e)}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )


@app.post("/analyzer", response_model=AnalyzerResponse)
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
        lesson_id = str(request.id) if request.id else None
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
                user_id=user_id,
                level=result["level"],
                level_reason=result["level_reason"]
            ),
            message="Analysis completed successfully",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    except HTTPException as he:
        return AnalyzerResponse(
            status="error",
            data=None,
            message=he.detail,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return AnalyzerResponse(
            status="error",
            data=None,
            message=f"Lỗi khi phân tích: {str(e)}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )


@app.post("/mindmap", response_model=MindmapResponse)
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
        lesson = get_lesson(str(request.id))
        if not lesson:
            raise HTTPException(
                status_code=404,
                detail=f"Không tìm thấy bài học với id: {request.id}"
            )
        
        # Lấy context từ bài học (Tối ưu: k=10→7 để giảm tokens)
        topic = request.topic if request.topic else "toàn bộ bài học"
        context = get_context(topic, k=7, lesson_id=str(request.id))
        
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
                mindmap_data=mindmap_data,
                id=request.id,
                title=lesson["title"]
            ),
            message="Mindmap generated successfully",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    except Exception as e:
        return MindmapResponse(
            status="error",
            data=None,
            message=f"Lỗi khi tạo mindmap: {str(e)}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )


@app.delete("/session")
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
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return APIResponse(
            status="error",
            data=None,
            message=f"Lỗi khi xóa session: {str(e)}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )


@app.get("/session")
async def get_session(user_id: str = Depends(get_current_user)):
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
                "user_id": user_id,
                "messages_count": len(session.get("messages", [])),
                "conversation_history": session_memory.get_conversation_history(user_id)
            },
            message="Session retrieved successfully",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        return APIResponse(
            status="error",
            data=None,
            message=f"Lỗi khi lấy session: {str(e)}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )


@app.get("/user/level", response_model=UserLevelResponse)
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
                    user_id=user_id,
                    level="Beginner",
                    level_reason="Chưa có cuộc hội thoại nào",
                    messages_count=0,
                    has_conversation=False
                ),
                message="User level retrieved",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        # Lấy level đã được lưu (từ analyzer)
        latest_level = session.get("latest_level")
        level_reason = session.get("level_reason")
        
        # Nếu chưa có level (chưa gọi analyzer), trả về Beginner
        if not latest_level:
            return UserLevelResponse(
                status="success",
                data=UserLevelData(
                    user_id=user_id,
                    level="Beginner",
                    level_reason="Chưa được đánh giá. Vui lòng gọi /analyzer trước.",
                    messages_count=len(messages),
                    has_conversation=True
                ),
                message="User level retrieved",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        return UserLevelResponse(
            status="success",
            data=UserLevelData(
                user_id=user_id,
                level=latest_level,
                level_reason=level_reason or "",
                messages_count=len(messages),
                has_conversation=True
            ),
            message="User level retrieved successfully",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    except Exception as e:
        return UserLevelResponse(
            status="error",
            data=None,
            message=f"Lỗi khi lấy level: {str(e)}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
