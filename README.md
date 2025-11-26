# Hệ thống Agentic RAG - Trợ giảng Toán lớp 4

Hệ thống RAG (Retrieval-Augmented Generation) sử dụng LangGraph, OpenAI LLM, và PostgreSQL + pgvector để trợ giảng Toán lớp 4.

---

## Tính năng chính

- **Chat thông minh**: Trả lời câu hỏi với 2 chế độ (ngắn gọn/chi tiết)
- **Sơ đồ tư duy**: Tạo mindmap JSON cho React Flow
- **Phân tích buổi học**: Đánh giá kết quả học tập + Level assessment
- **Level API**: Backend services có thể query level của user qua GET endpoint
- **Session management**: Quản lý hội thoại theo thread_id
- **Streaming response**: Response real-time giống ChatGPT
- **Tối ưu token**: Giảm 70-83% chi phí với GPT-3.5/GPT-4 hybrid

---

## Cài đặt

### 1. Cài đặt dependencies

```powershell
pip install -r requirements.txt
```

### 2. Cấu hình môi trường

Tạo file `.env` từ template:

```powershell
copy .env.example .env
```

Cấu hình `.env`:

```env
OPENAI_API_KEY=sk-your-api-key-here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=virtual_classroom
POSTGRES_USER=agent_user
POSTGRES_PASSWORD=your-secure-password
```

### 3. Khởi động PostgreSQL + pgvector

```powershell
# Sử dụng Docker (khuyến nghị)
docker run -d `
  --name postgres-virtual-classroom `
  -e POSTGRES_USER=agent_user `
  -e POSTGRES_PASSWORD=your-secure-password `
  -e POSTGRES_DB=virtual_classroom `
  -p 5432:5432 `
  -v postgres_data:/var/lib/postgresql/data `
  pgvector/pgvector:pg16
```

### 4. Tạo Database Schema

```powershell
# Kết nối vào PostgreSQL
docker exec -it postgres-virtual-classroom psql -U agent_user -d virtual_classroom

# Chạy SQL commands:
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE lessons (
    id SERIAL PRIMARY KEY,
    lesson_id VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    subject VARCHAR(50) NOT NULL,
    grade INTEGER NOT NULL,
    transcript TEXT NOT NULL,
    summary TEXT,
    total_chunks INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    lesson_id VARCHAR(50) NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_lesson FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id) ON DELETE CASCADE,
    UNIQUE(lesson_id, chunk_index)
);

CREATE INDEX idx_lessons_lesson_id ON lessons(lesson_id);
CREATE INDEX idx_lessons_subject_grade ON lessons(subject, grade);
CREATE INDEX idx_lessons_status ON lessons(status);
CREATE INDEX idx_chunks_lesson_id ON chunks(lesson_id);
CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 5. Migration: TXT files → PostgreSQL

Đặt file transcript (`.txt`) vào `data/transcripts/`, sau đó chạy:

```powershell
python scripts/migrate_txt_to_postgres.py
```

Script sẽ:
- Đọc tất cả `.txt` files
- Parse metadata từ filename
- Insert vào `lessons` table
- Chunking + Embedding
- Insert vào `chunks` table với vectors

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

Response:
```json
{
  "analysis": "Phân tích chi tiết...",
  "thread_id": "student_001",
  "level": "Intermediate",
  "level_reason": "Em đã hỏi 5 câu hỏi, thể hiện sự chủ động học hỏi"
}
```

### 5. Lấy Level của User (Cho Backend Services)
```http
GET /user/{thread_id}/level
```

Response:
```json
{
  "thread_id": "student_001",
  "level": "Intermediate",
  "level_reason": "Em đã hỏi 5 câu hỏi, thể hiện sự chủ động học hỏi",
  "messages_count": 10,
  "has_conversation": true
}
```

**Lưu ý:** 
- Level chỉ available sau khi gọi `/analyzer`
- Nếu chưa gọi analyzer, level mặc định là "Beginner"
- Levels: `Beginner`, `Intermediate`, `Advanced`

### 6. Quản lý Session
```http
GET /session/{thread_id}
DELETE /session/{thread_id}
```

### 7. Danh sách bài học
```http
GET /lessons
```

---

## Cấu trúc dự án

```
langgraph_agent/
├── app.py                      # FastAPI backend
├── requirements.txt            
├── .env                        # API keys + PostgreSQL config (tự tạo)
├── agent/
│   ├── graph.py               # LangGraph workflow
│   ├── prompts.py             # Prompt templates
│   ├── memory.py              # Session management
│   └── tools/                 # Tools (retriever, answer, explain, mindmap, analyzer, summarizer)
├── database/
│   ├── db_connection.py       # PostgreSQL connection pool
│   ├── lessons_repository.py  # Lessons table operations
│   └── chunks_repository.py   # Chunks + pgvector search
├── scripts/
│   └── migrate_txt_to_postgres.py  # Migration script
└── data/
    └── transcripts/           # Transcript files (.txt)
```

---

## Đặc điểm kỹ thuật

- **LangGraph**: Stateful workflow với nodes/edges
- **GPT-4**: Giải thích chi tiết, mindmap
- **GPT-3.5-turbo**: Trả lời ngắn, phân tích (tối ưu chi phí)
- **PostgreSQL + pgvector**: Vector database với cosine similarity search
- **FastAPI**: REST API + Streaming
- **MemorySaver**: Conversation history

---

## Lưu ý

- Chỉ sử dụng thông tin từ transcript
- Giọng điệu thân thiện, phù hợp học sinh lớp 4
- Temperature = 0 cho tính nhất quán
- Mỗi `thread_id` = 1 cuộc hội thoại riêng

---

## 🐳 Triển khai với Docker

### Yêu cầu
- Docker Desktop (Windows/Mac) hoặc Docker Engine (Linux)
- Docker Compose v3.8+

### Cách 1: Sử dụng Docker Compose (Khuyến nghị)

#### Bước 1: Cấu hình môi trường
```powershell
# Copy file .env.example thành .env
copy .env.example .env

# Mở .env và điền các biến cần thiết
notepad .env
```

Cấu hình tối thiểu trong `.env`:
```env
OPENAI_API_KEY=sk-your-api-key-here
POSTGRES_USER=agent_user
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=virtual_classroom
```

#### Bước 2: Build và chạy
```powershell
# Build và chạy tất cả services (PostgreSQL + API + Ngrok)
docker-compose up --build

# Hoặc chạy ở chế độ background (detached)
docker-compose up -d --build
```

#### Bước 2.5: Khởi tạo Database Schema (chỉ lần đầu)
```powershell
# Kết nối vào PostgreSQL container
docker exec -it langgraph_postgres psql -U agent_user -d virtual_classroom

# Chạy lệnh SQL (copy từ phần "Tạo Database Schema" ở trên)
# CREATE EXTENSION vector; CREATE TABLE lessons (...); etc.
```

#### Bước 2.6: Migration Data (nếu có transcript files)
```powershell
# Copy transcript files vào data/transcripts/
# Sau đó chạy migration từ container
docker exec -it langgraph_agent_api python scripts/migrate_txt_to_postgres.py
```

#### Bước 3: Kiểm tra
- API: http://localhost:8000
- Health check: http://localhost:8000/
- API docs: http://localhost:8000/docs

#### Bước 4 (Tùy chọn): Expose ra public URL với Ngrok
```powershell
# 1. Lấy Ngrok authtoken từ: https://dashboard.ngrok.com/get-started/your-authtoken
# 2. Thêm vào .env:
#    NGROK_AUTHTOKEN=your_token_here

# 3. Restart docker-compose
docker-compose down
docker-compose up -d

# 4. Kiểm tra Ngrok URL
# Mở browser: http://localhost:4040
# Hoặc xem logs:
docker-compose logs ngrok
```

**Lấy Public URL:**
- Mở http://localhost:4040 để xem Ngrok dashboard
- Copy URL dạng: `https://xxxx-xx-xx-xxx-xxx.ngrok-free.app`
- Dùng URL này để test từ bất kỳ đâu (mobile, Postman, webhook...)

#### Dừng services
```powershell
# Dừng và xóa containers
docker-compose down

# Dừng và xóa cả volumes (postgres_data)
docker-compose down -v
```

### Cách 2: Sử dụng Docker thuần

#### Build image
```powershell
docker build -t langgraph-agent:latest .
```

#### Chạy PostgreSQL
```powershell
docker run -d `
  --name postgres-virtual-classroom `
  -e POSTGRES_USER=agent_user `
  -e POSTGRES_PASSWORD=your-password `
  -e POSTGRES_DB=virtual_classroom `
  -p 5432:5432 `
  pgvector/pgvector:pg16
```

#### Chạy API container
```powershell
docker run -d `
  --name langgraph-agent `
  -p 8000:8000 `
  -e OPENAI_API_KEY=sk-your-api-key-here `
  -e POSTGRES_HOST=host.docker.internal `
  -e POSTGRES_PORT=5432 `
  -e POSTGRES_DB=virtual_classroom `
  -e POSTGRES_USER=agent_user `
  -e POSTGRES_PASSWORD=your-password `
  -v ${PWD}/data:/app/data `
  langgraph-agent:latest
```

#### Xem logs
```powershell
docker logs -f langgraph-agent
```

#### Dừng và xóa container
```powershell
docker stop langgraph-agent
docker rm langgraph-agent
```

### Các lệnh Docker hữu ích

```powershell
# Xem containers đang chạy
docker ps

# Xem logs
docker-compose logs -f web

# Chạy migration script trong container
docker-compose exec web python scripts/migrate_txt_to_postgres.py

# Rebuild khi có thay đổi code
docker-compose up --build

# Xem resource usage
docker stats
```

### Cấu trúc Volumes

Docker Compose tự động mount các thư mục sau:
- `postgres_data` → PostgreSQL data persistence
- `./data` → `/app/data` (Transcripts)
- `.` → `/app` (Source code - chỉ cho development)

### Troubleshooting

#### Lỗi: "Cannot connect to the Docker daemon"
```powershell
# Đảm bảo Docker Desktop đang chạy
# Khởi động Docker Desktop và thử lại
```

#### Lỗi: "Port 8000 is already allocated"
```powershell
# Dừng process đang dùng port 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Hoặc thay đổi port trong docker-compose.yml
ports:
  - "8001:8000"  # Thay 8000 thành 8001
```

#### Lỗi: "OPENAI_API_KEY not set"
```powershell
# Kiểm tra file .env có tồn tại không
dir .env

# Đảm bảo file .env có nội dung:
# OPENAI_API_KEY=sk-...
```

#### Rebuild từ đầu (clean build)
```powershell
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

### Production Deployment

Để deploy production, khuyến nghị:

1. **Bỏ mount source code** trong `docker-compose.yml`:
```yaml
volumes:
  # - .:/app  # Comment dòng này
  - ./data:/app/data
```

2. **Sử dụng .env file riêng cho production**:
```powershell
docker-compose --env-file .env.production up -d
```

3. **Setup PostgreSQL backups**:
```powershell
# Backup
docker exec langgraph_postgres pg_dump -U agent_user virtual_classroom > backup.sql

# Restore
docker exec -i langgraph_postgres psql -U agent_user virtual_classroom < backup.sql
```

5. **Enable monitoring** (Prometheus/Grafana)

6. **Setup log aggregation** (ELK stack)

### Docker Image Size Optimization

Image hiện tại sử dụng `python:3.9-slim` (khoảng ~450MB sau build).

Để giảm size hơn nữa:
- Sử dụng multi-stage build
- Dùng Alpine Linux base image
- Loại bỏ build dependencies sau khi cài đặt

---

## 🎯 Cải tiến Độ Chính Xác (v2.0)

### Các kỹ thuật đã áp dụng:

#### 1. Chain-of-Thought Prompting
- Yêu cầu LLM giải thích từng bước tư duy
- Tăng độ chính xác lên ~30% cho bài toán logic
- Áp dụng trong chế độ "Deep" (giải thích chi tiết)

#### 2. Few-Shot Examples
- Cung cấp 2-3 ví dụ mẫu trong prompt
- Giúp LLM hiểu rõ format và style câu trả lời mong đợi
- Giảm thiểu câu trả lời sai format

#### 3. Temperature = 0
- Loại bỏ tính ngẫu nhiên trong response
- Đảm bảo câu trả lời nhất quán, có thể reproduce
- Áp dụng cho TẤT CẢ LLM calls

#### 4. Self-Critique Mechanism
- LLM tự kiểm tra câu trả lời trước khi trả về
- Phát hiện hallucination và thông tin không chính xác
- Chỉ áp dụng cho "Deep mode" để tiết kiệm cost
- Validation với confidence score và auto-correction

#### 5. Abstain When Uncertain
- Hướng dẫn LLM từ chối trả lời khi không có đủ thông tin
- Tránh bịa đặt thông tin (hallucination)
- Response mẫu: "Em ơi, phần này cô chưa có đủ thông tin..."

#### 6. RAG với Trích Dẫn Nguồn
- Retriever trả về metadata (source, lesson_id)
- Format context kèm nguồn: `[Nguồn 1: bai_2_phan_so.txt]`
- LLM được yêu cầu dựa vào nguồn cụ thể
- Tăng tính minh bạch và truy vết được thông tin

### So sánh với Gemini

Google Gemini có "Grounding with Google Search" giúp tăng độ chính xác:
- Tìm kiếm web real-time
- Trích dẫn nguồn tin cậy
- Điểm accuracy: 8.5/10 (vs ChatGPT 8.3/10)

Hệ thống này bắt chước cách tiếp cận đó bằng:
- RAG với PostgreSQL + pgvector (thay vì Google Search)
- Metadata tracking và citation
- Validation layer để tự kiểm tra
