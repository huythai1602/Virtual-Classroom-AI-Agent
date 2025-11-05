# Hệ thống Agentic RAG - Trợ giảng Toán lớp 4

Hệ thống RAG (Retrieval-Augmented Generation) sử dụng LangGraph, OpenAI LLM, và ChromaDB để trợ giảng Toán lớp 4.

---

## Tính năng chính

- **Chat thông minh**: Trả lời câu hỏi với 2 chế độ (ngắn gọn/chi tiết)
- **Sơ đồ tư duy**: Tạo mindmap JSON cho React Flow
- **Phân tích buổi học**: Đánh giá kết quả học tập của học sinh
- **Session management**: Quản lý hội thoại theo thread_id
- **Streaming response**: Response real-time giống ChatGPT
- **Tối ưu token**: Giảm 70-83% chi phí với GPT-3.5/GPT-4 hybrid

---

## Cài đặt

### 1. Cài đặt dependencies

```powershell
pip install -r requirements.txt
```

### 2. Cấu hình API key

Tạo file `.env` từ template:

```powershell
copy .env.example .env
```

Thêm OpenAI API key vào `.env`:

```env
OPENAI_API_KEY=sk-your-api-key-here
```

### 3. Chuẩn bị dữ liệu

Đặt file transcript bài giảng (`.txt` hoặc `.pdf`) vào `data/transcripts/`

### 4. Build Vector Store

```powershell
python vector_store/build_chroma.py
```

---

## Chạy server

```powershell
python app.py
```

Server chạy tại: `http://localhost:8000`

---

## API Endpoints

### 1. Chat (Regular)
```http
POST /chat
Content-Type: application/json

{
  "thread_id": "student_001",
  "user_message": "Phân số là gì?",
  "lesson_id": "bai_2_phan_so"
}
```

### 2. Chat (Streaming)
```http
POST /chat/stream
Content-Type: application/json

{
  "thread_id": "student_001",
  "user_message": "Phân số là gì?",
  "lesson_id": "bai_2_phan_so"
}
```

Response: Server-Sent Events
```
data: {"chunk": "Ồ, câu hỏi hay!", "done": false}
data: {"chunk": "", "done": true}
```

### 3. Tạo Mindmap
```http
POST /mindmap
Content-Type: application/json

{
  "lesson_id": "bai_2_phan_so",
  "topic": "phân số"
}
```

### 4. Phân tích buổi học
```http
POST /analyzer
Content-Type: application/json

{
  "thread_id": "student_001",
  "lesson_id": "bai_2_phan_so",
  "topic": "phân số"
}
```

### 5. Quản lý Session
```http
GET /session/{thread_id}
DELETE /session/{thread_id}
```

### 6. Danh sách bài học
```http
GET /lessons
```

---

## Cấu trúc dự án

```
langgraph_agent/
├── app.py                      # FastAPI backend
├── requirements.txt            
├── .env                        # API keys (tự tạo)
├── agent/
│   ├── graph.py               # LangGraph workflow
│   ├── prompts.py             # Prompt templates
│   ├── memory.py              # Session management
│   └── tools/                 # Tools (retriever, answer, explain, mindmap, analyzer, summarizer)
├── data/
│   └── transcripts/           # Transcript files (.txt, .pdf)
├── vector_store/
│   └── build_chroma.py        # Build vector DB
└── chroma_db/                 # Vector store (auto-generated)
```

---

## Đặc điểm kỹ thuật

- **LangGraph**: Stateful workflow với nodes/edges
- **GPT-4**: Giải thích chi tiết, mindmap
- **GPT-3.5-turbo**: Trả lời ngắn, phân tích (tối ưu chi phí)
- **ChromaDB**: Vector database
- **FastAPI**: REST API + Streaming
- **MemorySaver**: Conversation history

---

## Lưu ý

- Chỉ sử dụng thông tin từ transcript
- Giọng điệu thân thiện, phù hợp học sinh lớp 4
- Temperature = 0 cho tính nhất quán
- Mỗi `thread_id` = 1 cuộc hội thoại riêng
