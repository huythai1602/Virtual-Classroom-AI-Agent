# 🚀 Quick Start Guide - PostgreSQL Migration

## ✅ Đã hoàn thành
- ✅ Migrate từ ChromaDB → PostgreSQL + pgvector
- ✅ Vector similarity search với cosine distance
- ✅ Database schema: `lessons` + `chunks` tables
- ✅ Migration script: `scripts/migrate_txt_to_postgres.py`
- ✅ Docker Compose với PostgreSQL service

---

## 📝 Các bước để chạy hệ thống

### Bước 1: Setup PostgreSQL

```powershell
# Start PostgreSQL container
docker-compose up postgres -d

# Verify PostgreSQL is running
docker ps | Select-String postgres
```

### Bước 2: Initialize Database

```powershell
# Run init script
docker exec -i langgraph_postgres psql -U agent_user -d virtual_classroom < scripts/init_db.sql

# Or manually:
docker exec -it langgraph_postgres psql -U agent_user -d virtual_classroom
# Then paste SQL from scripts/init_db.sql
```

### Bước 3: Migrate Transcript Files

```powershell
# Cấu hình .env với PostgreSQL credentials
copy .env.example .env
notepad .env  # Điền OPENAI_API_KEY và POSTGRES_* variables

# Install dependencies
pip install -r requirements.txt

# Run migration
python scripts/migrate_txt_to_postgres.py
```

**Expected output:**
```
🚀 Starting TXT Files → PostgreSQL Migration
📂 Found 4 transcript files
📄 [1/4] Processing: Toán lớp 4 Bài 1...
   ✅ Lesson inserted: toan-lop-4-bai-1
   🧠 Creating embeddings...
   ✅ Inserted 87 chunks
   🎉 SUCCESS: 87 chunks indexed
...
✨ Migration completed!
```

### Bước 4: Start API Server

```powershell
# Option 1: Run locally
python app.py

# Option 2: Run with Docker Compose (all services)
docker-compose up --build
```

### Bước 5: Test API

```powershell
# Test chat endpoint
curl -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"thread_id": "test_001", "user_message": "Chữ số 6 ở hàng nào trong số 36547?"}'
```

---

## 🗄️ Database Structure

### Lessons Table
```sql
SELECT lesson_id, title, subject, grade, total_chunks, status 
FROM lessons;
```

### Chunks Table
```sql
SELECT lesson_id, chunk_index, LEFT(text, 50) AS preview, 
       1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM chunks 
WHERE lesson_id = 'toan-lop-4-bai-1'
LIMIT 5;
```

---

## 🔧 Troubleshooting

### Lỗi: "pgvector extension not found"
```sql
-- Connect to PostgreSQL
docker exec -it langgraph_postgres psql -U agent_user -d virtual_classroom

-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;
```

### Lỗi: "Connection refused to PostgreSQL"
```powershell
# Check PostgreSQL is running
docker ps | Select-String postgres

# Check logs
docker logs langgraph_postgres

# Restart
docker-compose restart postgres
```

### Lỗi: "Embedding API timeout"
```
Giải pháp: 
1. Giảm số lượng transcript files trong data/transcripts/
2. Tăng timeout trong OpenAI client
3. Chạy migration từng file một
```

---

## 📊 Performance Notes

- **Vector search latency**: ~20-50ms (với 1000 chunks)
- **Embedding cost**: ~$0.0001 per 1000 tokens
- **IVFFlat index**: Cần tune `lists` parameter dựa trên số lượng chunks
  - 1,000 chunks → lists = 50
  - 10,000 chunks → lists = 100
  - 100,000 chunks → lists = 1000

---

## 🎯 Next Steps

1. ✅ Test retrieval accuracy với các câu hỏi mẫu
2. ✅ Benchmark latency: ChromaDB vs pgvector
3. ⚠️ Setup monitoring cho PostgreSQL queries
4. ⚠️ Implement backup strategy cho PostgreSQL
5. ⚠️ Optimize IVFFlat index parameters

---

## 📚 References

- pgvector docs: https://github.com/pgvector/pgvector
- PostgreSQL docs: https://www.postgresql.org/docs/
- OpenAI Embeddings: https://platform.openai.com/docs/guides/embeddings
