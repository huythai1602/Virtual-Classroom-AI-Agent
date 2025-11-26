# Agentic RAG API - Testing Guide

## 📋 Postman Collection Import

### Step 1: Import Collection
1. Open Postman
2. Click **Import** button (top left)
3. Select file: `Agentic_RAG_API.postman_collection.json`
4. Click **Import**

### Step 2: Verify Base URL
All requests use: `http://localhost:8000`

---

## 🗄️ Database Lessons

Current lessons in PostgreSQL:

| ID | Title | Subject | Grade |
|----|-------|---------|-------|
| **1** | Ôn tập các số đến 100000 | Toán | 4 |
| **2** | Ôn tập các phép tính trong phạm vi 100 000 | Toán | 4 |
| **3** | Số chẵn số lẻ | Toán | 4 |

---

## 🧪 Test Cases

### 1. Health Check ✅
**GET** `/`
- Verify API is running

### 2. Get All Lessons ✅
**GET** `/lessons`
- Returns all 3 lessons from PostgreSQL

### 3. Chat - Normal Answer (Lesson 1) ✅
**POST** `/chat`
```json
{
  "thread_id": "student_001",
  "user_message": "Chỗ số 6 trong số 36745 thuộc hàng nào?",
  "lesson_id": "1"
}
```
- **Topic**: Place value (hàng trong số)
- **Expected**: Short answer about "hàng nghìn"

### 4. Chat - Deep Explain (Lesson 1 - FIXED) 🔧
**POST** `/chat`
```json
{
  "thread_id": "student_001",
  "user_message": "Cô ơi, giải thích chi tiết cách xác định hàng trong một số cho em với ạ.",
  "lesson_id": "1"
}
```
- **IMPORTANT**: Use `lesson_id: "1"` (NOT "2")
- **Reason**: Place value questions belong to Lesson 1
- **Expected**: Detailed 4-step explanation with examples

### 5. Chat - Lesson 2 (Addition) ✅
**POST** `/chat`
```json
{
  "thread_id": "student_002",
  "user_message": "Cô ơi, cho em hỏi cách cộng hai số có năm chữ số?",
  "lesson_id": "2"
}
```
- **Topic**: Addition operations
- **Expected**: Explanation about adding 5-digit numbers

### 6. Chat - Lesson 3 (Even/Odd) ✅
**POST** `/chat`
```json
{
  "thread_id": "student_003",
  "user_message": "Số 248 là số chẵn hay số lẻ ạ?",
  "lesson_id": "3"
}
```
- **Topic**: Even/odd numbers
- **Expected**: Identify 248 as even number

### 7. Chat - Out of Scope (History) ❌
**POST** `/chat`
```json
{
  "thread_id": "student_001",
  "user_message": "Cô ơi, cho em hỏi về lịch sử Việt Nam?",
  "lesson_id": "1"
}
```
- **Expected**: Politely decline and redirect to math topic
- **Example**: "Ối, câu này chưa nằm trong bài học Toán hôm nay em ạ!"

### 8. Chat - Without lesson_id 🔍
**POST** `/chat`
```json
{
  "thread_id": "student_004",
  "user_message": "Số chẵn là gì?"
}
```
- **Expected**: Search across all lessons, should find answer in Lesson 3

### 9. Analyze Session 📊
**POST** `/analyzer`
```json
{
  "thread_id": "student_001",
  "lesson_id": "1",
  "topic": "Ôn tập các số đến 100000"
}
```
- **Expected**: Learning analysis + level assessment (Beginner/Intermediate/Advanced)

### 10. Generate Mindmap 🗺️
**POST** `/mindmap`
```json
{
  "lesson_id": "3",
  "topic": "Số chẵn số lẻ"
}
```
- **Expected**: React Flow JSON for mindmap visualization

### 11. Get Session Info ℹ️
**GET** `/session/student_001`
- Returns conversation history for thread

### 12. Clear Session 🗑️
**DELETE** `/session/student_001`
- Clears all messages for thread

---

## 🔑 Key Points

### ✅ Correct Usage
```json
{
  "lesson_id": "1"  // Use numeric string ID from database
}
```

### ❌ Wrong Usage (Old way)
```json
{
  "lesson_id": "Toán lớp 4 Bài 1 Ôn tập các số đến 100000..."  // DON'T use lesson title
}
```

### 📍 Lesson-Question Mapping

| Question Type | Correct lesson_id |
|--------------|-------------------|
| Xác định hàng trong số | "1" |
| Giá trị các chữ số | "1" |
| Cộng, trừ, nhân, chia | "2" |
| Số chẵn, số lẻ | "3" |

---

## 🚀 Quick Test Sequence

1. **Health Check** → Verify API is up
2. **Get Lessons** → See all available lessons
3. **Test Case 4** → Most important: Deep explain with CORRECT lesson_id
4. **Test Case 7** → Verify out-of-scope detection
5. **Clear Session** → Clean up after testing

---

## 🐛 Common Issues

### Issue 1: Wrong lesson_id
**Problem**: "Cô không tìm thấy đủ thông tin..."
**Solution**: Match question topic to correct lesson ID

### Issue 2: Out-of-scope false positive
**Problem**: Valid question marked as out-of-scope
**Cause**: RAG retrieval found low similarity
**Solution**: Check if using correct lesson_id

### Issue 3: Generic/robotic answers
**Cause**: Prompt needs more natural language instructions
**Status**: Fixed with "Write NATURALLY" constraints

---

## 📊 Expected Response Times

- Normal Answer: ~2-4 seconds
- Deep Explain: ~4-6 seconds
- Mindmap: ~5-8 seconds
- Analyzer: ~6-10 seconds

---

## 🔍 Debugging

Check Docker logs:
```bash
docker logs langgraph_agent_api --tail 50
```

Check PostgreSQL connection:
```bash
docker exec -it langgraph_postgres psql -U agent_user -d virtual_classroom -c "SELECT COUNT(*) FROM chunks;"
```

Verify vector index:
```bash
docker exec -it langgraph_postgres psql -U agent_user -d virtual_classroom -c "\d chunks"
```

---

## 📝 Notes

- All responses are in Vietnamese
- System uses GPT-4o for synthesis, GPT-3.5-turbo for routing
- PostgreSQL pgvector with IVFFlat index (lists=100)
- Smart retrieval with query expansion
- Confidence scoring for answer quality
