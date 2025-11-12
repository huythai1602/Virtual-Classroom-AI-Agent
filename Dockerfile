# Sử dụng Python 3.9 slim image cho kích thước nhỏ hơn
FROM python:3.9-slim

# Thiết lập biến môi trường
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy requirements trước để tận dụng Docker layer caching
COPY requirements.txt /app/

# Cài đặt dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code
COPY . /app/

# Tạo thư mục cho ChromaDB nếu chưa có
RUN mkdir -p /app/chroma_db /app/data/transcripts

# Expose port cho FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/')" || exit 1

# Command để chạy ứng dụng
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
