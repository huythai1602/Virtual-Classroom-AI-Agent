
# 3.4. THIẾT KẾ API VÀ HIỆN THỰC HÓA TRIỂN KHAI (SYSTEM IMPLEMENTATION & DEPLOYMENT)

Để chuyển đổi các mô hình AI từ môi trường thử nghiệm sang một sản phẩm thực tế có khả năng phục vụ người dùng cuối, nhóm đã xây dựng một kiến trúc hệ thống phân tán, tách biệt giữa tầng xử lý (Compute Layer) và tầng dữ liệu (Data Layer).

Phần này trình bày chi tiết về thiết kế chuẩn hóa API và quy trình triển khai bằng công nghệ Container hóa (Local Docker).

## 3.4.1. Kiến trúc Đóng gói và Thiết kế API (API Design)

Hệ thống Backend (Agent Service) được phát triển bằng **FastAPI**, tuân thủ mô hình **Clean Architecture** để đảm bảo tính độc lập của logic nghiệp vụ.

### A. Cấu trúc Dự án và Phân tầng (Project Structure)
Mã nguồn không được viết gộp mà chia thành các module chuyên biệt:

*   **`app/core/`**: Chứa logic "bộ não" của Agent (LangGraph nodes, State schema). Đây là tầng quan trọng nhất, không phụ thuộc vào Database hay Web Framework.
*   **`app/services/`**: Tầng dịch vụ hạ tầng (Infrastructure Services), bao gồm logic RAG và Ingestion.
*   **`app/api/`**: Tầng giao tiếp (Presentation Layer), định nghĩa các Router và xử lý HTTP Request/Response trong `app.py`.
*   **`app/models/`**: Định nghĩa các DTO (Data Transfer Object) bằng Pydantic để validate dữ liệu chặt chẽ (ví dụ: `ChatRequest`, `MindmapRequest`).

### B. Đặc tả Chi tiết các Endpoint (API Specification)

Dưới đây là thiết kế chi tiết (Input/Output) đã được hiện thực hóa, đảm bảo tính nhất quán khi tích hợp với Frontend.

#### 1. Endpoint Hội thoại Thông minh (`POST /api/agent/chat`)
Đây là điểm tiếp nhận chính, xử lý luồng RAG và hội thoại.

**Request Body (`ChatRequest`):**
```json
{
  "userMessage": "Làm sao để quy đồng mẫu số?",
  "lessonId": 2
}
```
*(Lưu ý: `user_id` được xác thực qua JWT Header, `thread_id` được sinh tự động)*

**Logic xử lý:**
1.  **Context Loading**: Tải lịch sử chat từ PostgreSQL dựa trên `thread_id`.
2.  **Graph Execution**: Kích hoạt LangGraph. Agent tự động định tuyến (Route) sang node giải thích (Explain Node) do phát hiện câu hỏi "Làm sao".
3.  **Response Generation**: Trả về kết quả kèm metadata phân loại ý định.

**Response Body (`ChatData`):**
```json
{
  "reply": "Để quy đồng mẫu số, con hãy làm theo 3 bước sau...",
  "intent": "deep",
  "threadId": "user_123_session"
}
```

#### 2. Endpoint Tạo Sơ đồ Tư duy (`POST /api/lessons/mindmap`)
**Cơ chế**: Endpoint này không vẽ hình ảnh mà trả về cấu trúc dữ liệu đồ thị để Frontend (React Flow) tự render.

**Request Body (`MindmapRequest`):**
```json
{
  "lessonId": 2
}
```
*(Hệ thống tự động trích xuất Topic từ tiêu đề bài học)*

**Response Structure (Graph JSON):**
```json
{
  "mindmap": {
    "nodes": [
      {"id": "1", "data": {"label": "Phân số"}, "position": {"x": 0, "y": 0}},
      {"id": "2", "data": {"label": "Tử số"}, "position": {"x": 100, "y": 100}}
    ],
    "edges": [
      {"source": "1", "target": "2"}
    ],
    "topic": "Phân số"
  }
}
```

## 3.4.2. Hạ tầng Triển khai (Deployment Infrastructure)

Nhóm áp dụng công nghệ Container hóa để đảm bảo tính nhất quán giữa môi trường phát triển và vận hành (Dev/Prod Parity).

### A. Tầng Ứng dụng (Compute Layer) - Docker Container
App Server chạy trong môi trường Docker cô lập, đảm bảo không xung đột thư viện.

**Quy trình Build & Run:**
1.  **Base Image**: Sử dụng `python:3.9-slim` tối ưu dung lượng.
2.  **Multistage Build**: Cài đặt dependencies và copy mã nguồn.
3.  **Command**: `uvicorn app:app --host 0.0.0.0` để khởi chạy ASGI Server.

**Minh chứng (`Dockerfile`):**
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD sh -c "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"
```

### B. Tầng Dữ liệu (Data Layer) - PostgreSQL & PgVector
Hệ thống sử dụng **PostgreSQL 16** đi kèm extension **pgvector** để lưu trữ cả dữ liệu quan hệ (bài học, user) và dữ liệu vector (embeddings).

**Minh chứng (`docker-compose.yml`):**
```yaml
services:
  postgres:
    image: pgvector/pgvector:postgres-16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=langgraph_db
      
  web:
    build: .
    depends_on:
      - postgres
```

### 3.4.3. Quy trình Vận hành
Hệ thống được thiết kế để dễ dàng mở rộng lên Cloud (như Railway/AWS) khi cần thiết nhờ kiến trúc Docker tiêu chuẩn.
- **Log Management**: Theo dõi qua `docker logs -f` hoặc driver logging tập trung.
- **State Persistence**: Sử dụng `SessionMemory` (Postgres-backed) để đảm bảo trạng thái hội thoại không bị mất khi container khởi động lại.
