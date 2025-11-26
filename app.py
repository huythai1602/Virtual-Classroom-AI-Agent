"""  
FastAPI Backend cho hệ thống Agentic RAG
"""
import json
from fastapi import FastAPI, HTTPException, Depends, Header
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
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# JWT Authentication Helper
async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """
    Decode JWT token và trả về user_id
    
    Args:
        authorization: Header Authorization: Bearer <token>
        
    Returns:
        user_id: ID của user từ JWT payload
        
    Raises:
        HTTPException 401: Nếu token invalid hoặc missing
    """
    if not authorization:
        raise HTTPException(
            status_code=401, 
            detail="Missing Authorization header. Please provide: Authorization: Bearer <token>"
        )
    
    try:
        # Extract token from "Bearer <token>"
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=401, 
                detail="Invalid Authorization header format. Use: Bearer <token>"
            )
        
        token = parts[1]
        
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


# Request/Response models
class ChatRequest(BaseModel):
    user_message: str
    lesson_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = None
    user_id: str  # Changed from thread_id


class AnalyzerRequest(BaseModel):
    lesson_id: Optional[str] = None
    topic: Optional[str] = ""


class AnalyzerResponse(BaseModel):
    analysis: str
    user_id: str  # Changed from thread_id
    level: str  # Beginner/Intermediate/Advanced
    level_reason: str  # Lý do đánh giá level


class MindmapRequest(BaseModel):
    lesson_id: str
    topic: Optional[str] = ""  # Topic để tạo mindmap, mặc định lấy toàn bộ bài


class MindmapResponse(BaseModel):
    mindmap_data: Dict[str, Any]
    lesson_id: str


class HealthResponse(BaseModel):
    status: str
    message: str


class LessonInfo(BaseModel):
    lesson_id: str
    lesson_name: str


class LessonsResponse(BaseModel):
    lessons: List[LessonInfo]


class UserLevelResponse(BaseModel):
    user_id: str  # Changed from thread_id
    level: str  # Beginner/Intermediate/Advanced
    level_reason: str
    messages_count: int
    has_conversation: bool


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Agentic RAG API đang hoạt động"
    }


@app.get("/lessons", response_model=LessonsResponse)
async def get_lessons():
    """
    Lấy danh sách các bài giảng có sẵn
    
    Returns:
        LessonsResponse với danh sách bài giảng
    """
    try:
        transcripts_dir = Path("data/transcripts")
        lessons = []
        
        if transcripts_dir.exists():
            for file_path in transcripts_dir.glob("*"):
                if file_path.suffix in [".txt", ".pdf"]:
                    lessons.append(LessonInfo(
                        lesson_id=file_path.stem,
                        lesson_name=file_path.name
                    ))
        
        return LessonsResponse(lessons=lessons)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi lấy danh sách bài giảng: {str(e)}"
        )


@app.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Unified chat endpoint - Tự động quyết định streaming hay non-streaming dựa vào intent
    Requires JWT token in Authorization header
    
    Args:
        request: ChatRequest chứa user_message và lesson_id
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
        
        # Tạo input state
        input_state = {
            "messages": [HumanMessage(content=request.user_message)],
            "lesson_id": request.lesson_id or ""
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
                reply=reply,
                intent=intent,
                user_id=user_id
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi xử lý chat: {str(e)}"
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
        request: AnalyzerRequest chứa lesson_id và topic (optional)
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
        transcript = get_context(topic, k=5, lesson_id=request.lesson_id)
        
        # Phân tích (bao gồm đánh giá level)
        result = analyze_with_data(conversation_history, transcript)
        
        # Lưu level vào session
        session = session_memory.get_session(thread_id)
        session["latest_level"] = result["level"]
        session["level_reason"] = result["level_reason"]
        session_memory.update_session(thread_id, session)
        
        return AnalyzerResponse(
            analysis=result["analysis"],
            user_id=user_id,
            level=result["level"],
            level_reason=result["level_reason"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi phân tích: {str(e)}"
        )


@app.post("/mindmap", response_model=MindmapResponse)
async def mindmap_endpoint(request: MindmapRequest):
    """
    Endpoint tạo sơ đồ tư duy cho bài học
    
    Args:
        request: MindmapRequest chứa lesson_id và topic (optional)
        
    Returns:
        MindmapResponse với mindmap JSON cho React Flow
    """
    try:
        # Lấy context từ bài học (Tối ưu: k=10→7 để giảm tokens)
        topic = request.topic if request.topic else "toàn bộ bài học"
        context = get_context(topic, k=7, lesson_id=request.lesson_id)
        
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
            mindmap_data=mindmap_data,
            lesson_id=request.lesson_id
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi tạo mindmap: {str(e)}"
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
        return {"message": f"Đã xóa session của user {user_id}"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi xóa session: {str(e)}"
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
        return {
            "user_id": user_id,
            "messages_count": len(session.get("messages", [])),
            "conversation_history": session_memory.get_conversation_history(user_id)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi lấy session: {str(e)}"
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
                user_id=user_id,
                level="Beginner",
                level_reason="Chưa có cuộc hội thoại nào",
                messages_count=0,
                has_conversation=False
            )
        
        # Lấy level đã được lưu (từ analyzer)
        latest_level = session.get("latest_level")
        level_reason = session.get("level_reason")
        
        # Nếu chưa có level (chưa gọi analyzer), trả về Beginner
        if not latest_level:
            return UserLevelResponse(
                user_id=user_id,
                level="Beginner",
                level_reason="Chưa được đánh giá. Vui lòng gọi /analyzer trước.",
                messages_count=len(messages),
                has_conversation=True
            )
        
        return UserLevelResponse(
            user_id=user_id,
            level=latest_level,
            level_reason=level_reason or "",
            messages_count=len(messages),
            has_conversation=True
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi lấy level: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
