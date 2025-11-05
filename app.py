"""
FastAPI Backend cho hệ thống Agentic RAG
"""
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import os
from pathlib import Path
import asyncio
from langchain_core.messages import HumanMessage

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


# Request/Response models
class ChatRequest(BaseModel):
    thread_id: str
    user_message: str
    lesson_id: Optional[str] = None  # Thêm lesson_id


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = None
    thread_id: str


class AnalyzerRequest(BaseModel):
    thread_id: str
    lesson_id: Optional[str] = None  # Thêm lesson_id
    topic: Optional[str] = ""


class AnalyzerResponse(BaseModel):
    analysis: str
    thread_id: str


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


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint xử lý chat với học sinh
    
    Args:
        request: ChatRequest chứa thread_id và user_message
        
    Returns:
        ChatResponse với câu trả lời từ agent
    """
    try:
        # Lấy session hiện tại để lưu vào SessionMemory (cho analyzer)
        session = session_memory.get_session(request.thread_id)
        
        # Lưu user message vào session
        session["messages"].append({
            "role": "user",
            "content": request.user_message
        })
        
        # Tạo input state với message mới
        # LangGraph sẽ tự động merge với messages cũ từ checkpoint
        input_state = {
            "messages": [HumanMessage(content=request.user_message)],
            "lesson_id": request.lesson_id or ""
        }
        
        # Config để load history
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # Tối ưu: Lấy state hiện tại để summarize messages nếu cần
        try:
            current_state = compiled_graph.get_state(config)
            if current_state and current_state.values.get("messages"):
                all_messages = current_state.values["messages"] + [HumanMessage(content=request.user_message)]
                
                # Summarize nếu có >6 messages (giữ 4 messages gần nhất + summary)
                if len(all_messages) > 6:
                    summarized = summarize_old_messages(all_messages, keep_recent=4)
                    input_state["messages"] = summarized
        except:
            # Nếu không lấy được state, tiếp tục với message mới
            pass
        
        # Invoke graph - LangGraph tự load history từ MemorySaver
        result = compiled_graph.invoke(input_state, config)
        
        # Lấy câu trả lời cuối cùng
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
        
        # Lấy intent nếu có
        intent = result.get("intent", "normal")
        
        # Update session
        session_memory.update_session(request.thread_id, session)
        
        return ChatResponse(
            reply=reply,
            intent=intent,
            thread_id=request.thread_id
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi xử lý chat: {str(e)}"
        )


@app.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    Streaming version của chat endpoint để giảm latency cảm nhận
    
    Returns:
        Server-Sent Events stream với chunks của response
    """
    async def generate():
        try:
            # Get/create session
            session = session_memory.get_session(request.thread_id)
            
            # Save user message
            session["messages"].append({
                "role": "user",
                "content": request.user_message
            })
            
            # Prepare state
            input_state = {
                "messages": [HumanMessage(content=request.user_message)],
                "lesson_id": request.lesson_id or ""
            }
            
            config = {"configurable": {"thread_id": request.thread_id}}
            
            # Summarize if needed
            try:
                current_state = compiled_graph.get_state(config)
                if current_state and current_state.values.get("messages"):
                    all_messages = current_state.values["messages"] + [HumanMessage(content=request.user_message)]
                    if len(all_messages) > 6:
                        summarized = summarize_old_messages(all_messages, keep_recent=4)
                        input_state["messages"] = summarized
            except:
                pass
            
            # Stream graph execution
            full_response = ""
            async for event in compiled_graph.astream(input_state, config):
                # Tìm AI message trong event
                if "messages" in event:
                    for msg in event["messages"]:
                        if hasattr(msg, 'content') and msg.content:
                            chunk = msg.content
                            full_response = chunk
                            yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
            
            # Save assistant message
            session["messages"].append({
                "role": "assistant",
                "content": full_response
            })
            session_memory.update_session(request.thread_id, session)
            
            # Send final event
            yield f"data: {json.dumps({'chunk': '', 'done': True, 'thread_id': request.thread_id})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/analyzer", response_model=AnalyzerResponse)
async def analyzer_endpoint(request: AnalyzerRequest):
    """
    Endpoint phân tích buổi học
    
    Args:
        request: AnalyzerRequest chứa thread_id và topic (optional)
        
    Returns:
        AnalyzerResponse với kết quả phân tích
    """
    try:
        # Lấy conversation history từ session
        conversation_history = session_memory.get_conversation_history(request.thread_id)
        
        if not conversation_history:
            raise HTTPException(
                status_code=404,
                detail=f"Không tìm thấy lịch sử hội thoại cho thread_id: {request.thread_id}"
            )
        
        # Lấy transcript (Tối ưu: k=10→5 để giảm tokens cho analyzer)
        topic = request.topic if request.topic else "Toán lớp 4"
        transcript = get_context(topic, k=5, lesson_id=request.lesson_id)
        
        # Phân tích
        analysis = analyze_with_data(conversation_history, transcript)
        
        return AnalyzerResponse(
            analysis=analysis,
            thread_id=request.thread_id
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


@app.delete("/session/{thread_id}")
async def clear_session(thread_id: str):
    """
    Xóa session/thread
    
    Args:
        thread_id: ID của thread cần xóa
    """
    try:
        session_memory.clear_session(thread_id)
        return {"message": f"Đã xóa session {thread_id}"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi xóa session: {str(e)}"
        )


@app.get("/session/{thread_id}")
async def get_session(thread_id: str):
    """
    Lấy thông tin session
    
    Args:
        thread_id: ID của thread
    """
    try:
        session = session_memory.get_session(thread_id)
        return {
            "thread_id": thread_id,
            "messages_count": len(session.get("messages", [])),
            "conversation_history": session_memory.get_conversation_history(thread_id)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi lấy session: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
