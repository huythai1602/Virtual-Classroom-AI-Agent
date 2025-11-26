# JWT Authentication Guide

## Tổng quan

API đã được nâng cấp để sử dụng **JWT (JSON Web Token) authentication**. Client không cần gửi `thread_id` nữa, backend tự động extract `user_id` từ JWT token.

---

## Cấu hình

### 1. Environment Variables (.env)

```env
JWT_SECRET_KEY=your-shared-secret-key-change-in-production
JWT_ALGORITHM=HS256
```

**Quan trọng:** `JWT_SECRET_KEY` phải **giống nhau** giữa:
- Auth Service (nơi tạo token)
- AI Agent Service (nơi verify token)

---

## JWT Token Format

Token phải chứa `user_id` trong payload:

```json
{
  "sub": "user_123",           // Hoặc
  "user_id": "user_123",       // Hoặc
  "userId": "user_123",        // Backend hỗ trợ cả 3 formats
  "email": "user@example.com",
  "exp": 1735123456
}
```

---

## API Changes

### ❌ Cũ (thread_id trong body)

```javascript
POST /chat
{
  "thread_id": "user_123",
  "user_message": "Cho em hỏi..."
}
```

### ✅ Mới (JWT trong header)

```javascript
POST /chat
Headers: {
  "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
Body: {
  "user_message": "Cho em hỏi..."
}
```

---

## Endpoints đã thay đổi

### 1. Chat Endpoints

#### POST /chat
```javascript
// Request
Headers: { "Authorization": "Bearer <token>" }
Body: {
  "user_message": "Số 12345 có mấy chữ số?",
  "lesson_id": "toan-lop-4-bai-1"  // Optional
}

// Response
{
  "reply": "Số 12345 có 5 chữ số",
  "intent": "normal",
  "user_id": "user_123"  // Changed from thread_id
}
```

#### POST /chat/stream
```javascript
// Request (giống /chat)
Headers: { "Authorization": "Bearer <token>" }
Body: { "user_message": "..." }

// Response (SSE stream)
data: {"chunk": "Số 12345", "done": false}
data: {"chunk": " có 5 chữ số", "done": false}
data: {"chunk": "", "done": true, "user_id": "user_123"}
```

### 2. Analyzer Endpoint

#### POST /analyzer
```javascript
// Request
Headers: { "Authorization": "Bearer <token>" }
Body: {
  "lesson_id": "toan-lop-4-bai-1",  // Optional
  "topic": "phân số"                 // Optional
}

// Response
{
  "analysis": "Học sinh đã hiểu...",
  "user_id": "user_123",  // Changed from thread_id
  "level": "Intermediate",
  "level_reason": "Học sinh trả lời đúng..."
}
```

### 3. Session Management

#### GET /session
```javascript
// Request
Headers: { "Authorization": "Bearer <token>" }

// Response
{
  "user_id": "user_123",
  "messages_count": 10,
  "conversation_history": "Học sinh: ...\nTrợ giảng: ..."
}
```

#### DELETE /session
```javascript
// Request
Headers: { "Authorization": "Bearer <token>" }

// Response
{
  "message": "Đã xóa session của user user_123"
}
```

### 4. User Level

#### GET /user/level
```javascript
// Request
Headers: { "Authorization": "Bearer <token>" }

// Response
{
  "user_id": "user_123",
  "level": "Intermediate",
  "level_reason": "Học sinh đã trả lời...",
  "messages_count": 10,
  "has_conversation": true
}
```

---

## Frontend Integration

### React/Next.js Example

```javascript
// 1. Lưu token sau khi login (từ Auth Service)
const handleLogin = async (email, password) => {
  const response = await fetch('https://auth-service.com/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  });
  const { access_token } = await response.json();
  
  // Lưu vào localStorage hoặc cookie
  localStorage.setItem('access_token', access_token);
};

// 2. Tạo helper function để gọi API
const apiCall = async (endpoint, method = 'GET', body = null) => {
  const token = localStorage.getItem('access_token');
  
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    }
  };
  
  if (body) {
    options.body = JSON.stringify(body);
  }
  
  const response = await fetch(`https://your-api.com${endpoint}`, options);
  
  if (response.status === 401) {
    // Token expired, redirect to login
    window.location.href = '/login';
    return;
  }
  
  return response.json();
};

// 3. Sử dụng trong components
const ChatComponent = () => {
  const sendMessage = async (message) => {
    const response = await apiCall('/chat', 'POST', {
      user_message: message,
      lesson_id: 'toan-lop-4-bai-1'
    });
    
    console.log(response.reply);
  };
  
  return (
    <div>
      <button onClick={() => sendMessage('Cho em hỏi...')}>
        Send
      </button>
    </div>
  );
};
```

### Axios Example

```javascript
import axios from 'axios';

// Create axios instance với interceptor
const api = axios.create({
  baseURL: 'https://your-api.com'
});

// Auto-inject token vào mọi request
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 (token expired)
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Sử dụng
const sendMessage = async (message) => {
  const response = await api.post('/chat', {
    user_message: message
  });
  return response.data;
};
```

---

## Error Handling

### 401 Unauthorized

```json
{
  "detail": "Missing Authorization header. Please provide: Authorization: Bearer <token>"
}
```

**Nguyên nhân:** Không có header Authorization

**Giải pháp:** Thêm `Authorization: Bearer <token>` vào headers

---

```json
{
  "detail": "Invalid Authorization header format. Use: Bearer <token>"
}
```

**Nguyên nhân:** Sai format header (phải là `Bearer <token>`)

**Giải pháp:** Đảm bảo format đúng: `Authorization: Bearer eyJhbGc...`

---

```json
{
  "detail": "Invalid token: Signature verification failed"
}
```

**Nguyên nhân:** Token không hợp lệ hoặc `JWT_SECRET_KEY` khác nhau giữa Auth Service và AI Service

**Giải pháp:** 
1. Kiểm tra `JWT_SECRET_KEY` trong .env của cả 2 services
2. Đảm bảo token chưa expired
3. Đảm bảo token được tạo bằng cùng secret key

---

```json
{
  "detail": "Token payload missing user identifier (sub/user_id/userId)"
}
```

**Nguyên nhân:** Token payload không có `sub`, `user_id`, hoặc `userId`

**Giải pháp:** Auth Service phải include ít nhất 1 trong 3 fields này khi tạo token

---

## Testing với Postman

### 1. Tạo JWT token (mock)

Vào https://jwt.io/ và tạo token với:

**Header:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Payload:**
```json
{
  "sub": "test_user_123",
  "email": "test@example.com",
  "exp": 9999999999
}
```

**Secret:** Dùng giá trị trong `JWT_SECRET_KEY` của .env

### 2. Test trong Postman

1. Tạo request mới: `POST http://localhost:8000/chat`
2. Tab **Headers**, thêm:
   - Key: `Authorization`
   - Value: `Bearer <token_từ_jwt.io>`
3. Tab **Body** (raw JSON):
   ```json
   {
     "user_message": "Cho em hỏi số 12345 có mấy chữ số?"
   }
   ```
4. Send request

---

## Security Best Practices

### 1. Secret Key Management
- ❌ **KHÔNG** commit `JWT_SECRET_KEY` vào Git
- ✅ Dùng environment variables
- ✅ Secret key phải dài ít nhất 32 characters
- ✅ Dùng random generator: `openssl rand -hex 32`

### 2. Token Expiration
- Token nên có thời hạn (exp claim)
- Recommend: 1-24 hours tùy use case
- Implement refresh token mechanism

### 3. HTTPS Only
- Trong production, **BẮT BUỘC** dùng HTTPS
- Token qua HTTP plain text = dễ bị đánh cắp

### 4. Token Storage
- ✅ HttpOnly cookie (best for web)
- ⚠️ localStorage (dễ bị XSS)
- ❌ sessionStorage
- ✅ Mobile: Secure storage (Keychain/Keystore)

---

## Rollback (nếu cần)

Nếu muốn quay lại cách cũ (thread_id trong body):

1. Checkout commit trước JWT update
2. Hoặc comment `Depends(get_current_user)` và cho client gửi thread_id

---

## Support

Nếu gặp vấn đề:
1. Check logs: `docker logs langgraph_agent_api`
2. Verify token tại https://jwt.io/
3. Test với Postman trước khi integrate frontend
