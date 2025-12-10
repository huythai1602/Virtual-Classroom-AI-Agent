
3.3. XÂY DỰNG PIPELINE TRUY XUẤT VÀ TỐI ƯU HÓA TÌM KIẾM (RETRIEVAL PIPELINE)
Sau khi dữ liệu đã được vector hóa và lưu trữ, thách thức tiếp theo là làm thế nào để truy xuất chính xác những đoạn thông tin (chunks) liên quan nhất đến câu hỏi của người dùng. Một cơ chế tìm kiếm Vector thuần túy (Dense Retrieval) thường gặp khó khăn với các từ khóa chuyên ngành chính xác hoặc tên riêng (ví dụ: "Tấm Cám", "Hàng chục nghìn").
Để giải quyết vấn đề này, nhóm em đã xây dựng một Pipeline truy xuất đa tầng (Multi-stage Retrieval Pipeline) kết hợp giữa tìm kiếm từ khóa và tìm kiếm ngữ nghĩa, kèm theo cơ chế lọc và sắp xếp lại (Re-ranking).

3.3.1. Chiến lược Tìm kiếm Lai (Hybrid Search Strategy)
Thay vì chỉ dựa vào Cosine Similarity của vector, hệ thống sử dụng chiến lược Hybrid Search kết hợp sức mạnh của hai thuật toán:
- Sparse Retrieval (BM25): Tìm kiếm dựa trên tần suất từ khóa (Keyword Matching). Thuật toán này rất giỏi trong việc bắt chính xác các thuật ngữ toán học cụ thể (ví dụ: "số tròn chục", "liền trước").
- Dense Retrieval (Vector Search): Tìm kiếm dựa trên ý nghĩa ngữ nghĩa (Semantic Matching). Thuật toán này giúp hiểu được ngữ cảnh câu hỏi ngay cả khi không khớp từ khóa chính xác (ví dụ: "số đứng ngay trước" -> "số liền trước").

Cơ chế kết hợp (Ensemble) sử dụng thuật toán Reciprocal Rank Fusion (RRF) hoặc Weighted Sum để tổng hợp điểm số từ hai nguồn:

```python
    def hybrid_search(
        self,
        query: str,
        lesson_id: Optional[Union[str, int]] = None,
        k: int = 20
    ) -> List[Dict]:
        """Hybrid: 70% vector + 30% BM25"""
        alpha = settings.HYBRID_ALPHA
        
        vector_results = self.vector_search(query, lesson_id, k=k)
        bm25_results = self.bm25_search(query, lesson_id, k=k//2)
        
        # Combine scores logic...
        # ...
        
        for r in vector_results:
             # Weighted Sum
             combined[chunk_id]["hybrid_score"] = alpha * r.get("norm_vector", 0)
        
        for r in bm25_results:
             # ... + (1-alpha) * BM25
             combined[chunk_id]["hybrid_score"] += (1 - alpha) * r.get("norm_bm25", 0)
            
        return sorted(combined.values(), key=lambda x: x["hybrid_score"], reverse=True)[:k]
```
Trong đó, tham số alpha được thực nghiệm và tinh chỉnh (thường đặt alpha = 0.7 để ưu tiên ngữ nghĩa nhưng vẫn giữ trọng số cho từ khóa).

3.3.2. Cơ chế Lọc Metadata (Metadata Filtering)
Trước khi thực hiện tìm kiếm vector, hệ thống áp dụng bộ lọc Metadata (Pre-filtering) để thu hẹp không gian tìm kiếm, giúp tăng tốc độ và độ chính xác.
Dựa vào Metadata đã trích xuất ở giai đoạn xử lý dữ liệu (Mục 2.2.1), hệ thống có thể thực hiện các truy vấn có cấu trúc.
Ví dụ: Nếu Agent xác định câu hỏi đang nói về "Bài 1", bộ lọc sẽ được áp dụng:

```python
    def vector_search(self, query: str, lesson_id: Optional[Union[str, int]] = None, k: int = 20):
        # ...
        results = search_similar_chunks(
            query_embedding=query_embedding,
            lesson_id=lesson_id,  # <--- Metadata Filter: Only search within this lesson
            k=k
        )
        return results
```
Điều này đảm bảo rằng câu trả lời của Agent không bị nhiễu bởi kiến thức của các bài học khác (ví dụ: không lấy kiến thức "Phân số" của Bài 5 để trả lời cho Bài 1 về "Số tự nhiên").

3.3.3. Kỹ thuật Re-ranking (Sắp xếp lại kết quả)
Vector Search thường trả về Top-K (ví dụ K=20) tài liệu có độ tương đồng cao nhất. Tuy nhiên, độ tương đồng vector không phải lúc nào cũng đồng nghĩa với sự phù hợp về mặt logic (Relevance).
Để chọn ra những đoạn văn bản chất lượng nhất đưa vào Context Window của LLM, nhóm sử dụng một mô hình Cross-Encoder Re-ranker (ví dụ: bge-reranker-v2-m3 hoặc Cohere Rerank).

Quy trình:
1. Retrieval: Lấy Top-20 tài liệu từ Vector DB.
2. Re-ranking: Đưa cặp (Query, Document) vào mô hình Cross-Encoder để chấm điểm lại mức độ phù hợp ngữ nghĩa chi tiết.
3. Selection: Chọn ra Top-5 tài liệu có điểm số cao nhất sau khi Re-rank.

```python
    def rerank(self, query: str, candidates: List[Dict], k: int = 5) -> List[Dict]:
        """Cross-encoder reranking"""
        # ...
        self.reranker = CrossEncoder(settings.RERANK_MODEL)
        
        # Prepare pairs [Query, Content]
        pairs = [[query, chunk["text"]] for chunk in candidates]
        
        # Predict relevance scores
        rerank_scores = self.reranker.predict(pairs, ...)
            
        # Sort by new rerank score
        results = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:k]
        return results
```
Kỹ thuật này giúp loại bỏ các kết quả "dương tính giả" (False Positives) - những đoạn văn có vector gần giống nhưng nội dung không trả lời được câu hỏi.

3.3.4. Quản lý Cửa sổ Ngữ cảnh (Context Window Management)
Sau khi có được các đoạn văn bản (chunks) tốt nhất, thách thức cuối cùng là ghép chúng lại thành một ngữ cảnh (Context) hoàn chỉnh để gửi cho LLM. Nhóm áp dụng các kỹ thuật sau:
- Context Concatenation (Ghép nối): Các chunk được ghép lại theo thứ tự điểm số Re-rank giảm dần hoặc thứ tự xuất hiện trong bài giảng gốc (để giữ mạch logic).
- Token Budgeting (Ngân sách Token): Hệ thống tính toán tổng số token của Prompt. Nếu vượt quá giới hạn (ví dụ 4096 tokens), các chunk có điểm thấp nhất sẽ bị loại bỏ dần cho đến khi vừa đủ.
- Source Tracking (Theo dõi nguồn): Mỗi đoạn văn bản khi đưa vào prompt đều được đánh dấu nguồn gốc (Citation) để Agent có thể trích dẫn trong câu trả lời.

Format: [Trích từ: Toán lớp 4 - Bài 1] Nội dung...

```python
        # 4. Format with token budget
        for r in reranked_parents:
            content = r["text"]
            tokens = self.processor.count_tokens(content)
            
            # Token Budgeting
            if total_tokens + tokens > settings.MAX_CONTEXT_TOKENS:
                break
            
            total_tokens += tokens
            
            # Source Tracking
            formatted_chunks.append({
                "content": content,
                "source": r["source"] 
            })
            
        # Format as string for LLM
        context_parts = []
        for i, chunk in enumerate(formatted_chunks, 1):
            context_parts.append(f"[Nguồn {i}: {chunk['source']}]\n{chunk['content']}")
```

Ngoài việc quản lý nội dung bài học, nhóm còn áp dụng chiến lược **Tóm tắt Hội thoại (Conversation Summarization)** để xử lý lịch sử chat ngày càng dài. Khi số lượng tin nhắn vượt quá ngưỡng (ví dụ: 10 tin), hệ thống sẽ tự động kích hoạt một LLM phụ để tóm tắt các hội thoại cũ thành một đoạn văn ngắn, giải phóng không gian Context Window cho các xử lý suy luận phức tạp hơn.

```python
# tools/summarizer.py
def summarize_conversation(messages: List, keep_recent: int = 4) -> List:
    """Summarize old messages, keep recent ones"""
    if len(messages) <= keep_recent:
        return messages
    
    # ... logic to separate old and recent messages
    
    prompt = SUMMARIZE_PROMPT.format(conversation=conversation_text)
    summary = llm.invoke([HumanMessage(content=prompt)])
    
    return [SystemMessage(content=f"Tóm tắt: {summary.content}")] + recent_messages
```

3.3.5. Tổng kết Pipeline Truy xuất
Việc xây dựng một Pipeline truy xuất đa tầng (Hybrid Search + Re-ranking) là bước đệm quan trọng giúp chuyển hóa dữ liệu thô thành tri thức tinh lọc. Điều này đảm bảo rằng ở bước tiếp theo (Kiến trúc Agent), "bộ não" AI sẽ luôn được cung cấp những thông tin đầu vào chất lượng nhất, giải quyết triệt để vấn đề "Rác vào - Rác ra" (Garbage In, Garbage Out) thường gặp trong các hệ thống RAG cơ bản.

----------------------------------------------------------------------------------------------------
3.4. THIẾT KẾ VÀ HIỆN THỰC HÓA KIẾN TRÚC AGENT HƯỚNG ĐỒ THỊ.
Trong kiến trúc LangGraph, "State" (Trạng thái) đóng vai trò như bộ nhớ chia sẻ (Shared Memory) xuyên suốt vòng đời của một phiên xử lý. Không giống như các biến cục bộ trong lập trình tuần tự, State trong Agent là một cấu trúc dữ liệu bền vững, được truyền qua các Node để các thành phần khác nhau có thể đọc, ghi và cập nhật ngữ cảnh.
Nhóm nghiên cứu đã thiết kế AgentState dựa trên cấu trúc TypedDict của Python, bao gồm các trường thông tin cốt lõi sau:

| Trường (Field) | Kiểu dữ liệu | Mô tả & Vai trò |
| :--- | :--- | :--- |
| messages | list[BaseMessage] | Bộ nhớ ngắn hạn (Short-term Memory): Lưu trữ toàn bộ lịch sử hội thoại giữa User và Agent. Sử dụng cơ chế operator.add để liên tục nối thêm tin nhắn mới vào danh sách, giúp duy trì mạch chuyện liền mạch. |
| user_query | str | Câu hỏi gốc của người dùng ở lượt hiện tại. |
| intent | str | Kết quả phân loại ý định: Chứa nhãn (label) sau khi qua bộ phân loại (ví dụ: normal, deep, greeting, off_topic). Giá trị này quyết định hướng đi của đồ thị. |
| metadata | dict | Ngữ cảnh bài học: Lưu trữ các thông tin meta như grade (Lớp 4), subject (Toán), lesson_id (Bài 1). Thông tin này được dùng để lọc dữ liệu trong quá trình truy xuất (Retrieval). |
| context | str | Dữ liệu thô: Tổng hợp nội dung các đoạn văn bản (chunks) liên quan nhất đã được Retrieval Pipeline tìm thấy từ Vector DB. |
| answer | str | Câu trả lời cuối cùng được sinh ra bởi LLM trước khi gửi trả người dùng. |
| steps | list[str] | Trace log: Ghi lại danh sách các bước (Nodes) mà Agent đã đi qua (ví dụ: ['intent', 'retrieve', 'explain']). Trường này phục vụ cho việc debug và tối ưu hóa luồng đi. |

Hiện thực hóa bằng mã nguồn (Python):
```python
class AgentState(MessagesState):
    """Agent state with context and metadata"""
    context: str = ""
    intent: str = ""  # normal or deep
    current_query: str = ""
    lesson_id: Optional[Union[str, int]] = None
    metadata: dict = {}
    conversation_history: str = ""  # Recent conversation for context
    thread_id: str = ""
```

Để đảm bảo tính liên tục của trải nghiệm người dùng, trạng thái này không chỉ tồn tại trong bộ nhớ RAM mà được **bền vững hóa (Persisted)** vào cơ sở dữ liệu PostgreSQL thông qua cơ chế `Checkpointer`. Điều này cho phép người dùng có thể tải lại trang hoặc quay lại phiên học sau nhiều ngày mà vẫn giữ nguyên ngữ cảnh.

```python
# core/memory.py
class SessionMemory:
    """Manage session data with PostgreSQL persistence"""
    def update_session(self, thread_id: str, data: Dict[str, Any], persist: bool = True):
        # Update cache ...
        # Persist to database
        if persist:
            create_or_update_session(
                thread_id=thread_id,
                messages=messages,
                # ...
            )
```

3.4.3. Thiết kế Chi tiết Các Nút Xử lý (Nodes Implementation)
Hệ thống được mô đun hóa thành 5 Node chức năng chuyên biệt. Mỗi Node là một hàm độc lập, nhận vào State hiện tại, thực hiện xử lý logic và trả về bản cập nhật cho State.

A. Intent Node (Bộ phân loại ý định)
Đây là "cửa ngõ" đầu tiên của hệ thống. Thay vì lãng phí tài nguyên để truy xuất dữ liệu cho mọi câu hỏi, Node này sử dụng một mô hình LLM nhỏ, tốc độ cao (như Gemini Flash) để phân tích ngữ nghĩa và xác định người dùng thực sự muốn gì.
Input: user_query và messages (lịch sử chat gần nhất).
Kỹ thuật: Few-shot Prompting (Cung cấp ví dụ mẫu trong prompt).
Logic phân loại:
- deep: Các câu hỏi yêu cầu giải thích cơ chế, nguyên lý hoặc hướng dẫn giải bài tập (VD: "Tại sao...", "Làm thế nào...", "Giảng lại cho con...").
- normal: Các câu hỏi tra cứu định nghĩa, công thức hoặc sự thật hiển nhiên (VD: "Phân số là gì?", "1 km bằng bao nhiêu m?").
- greeting: Các câu chào hỏi xã giao không cần truy xuất kiến thức.

B. Metadata Node (Bộ làm giàu ngữ cảnh)
Chức năng: Xác định chính xác ngữ cảnh bài học mà người dùng đang tham gia.
Logic: Node này truy vấn cơ sở dữ liệu quan hệ (PostgreSQL) dựa trên lesson_id hiện tại của phiên học để lấy thông tin như: Tên bài học, Mục tiêu cần đạt, Các từ khóa trọng tâm.
Tác dụng: Giúp Agent "hiểu" ngầm ngữ cảnh. Ví dụ: Khi đang học bài "Phân số", nếu học sinh hỏi "Số ở trên gọi là gì?", Agent sẽ tự động hiểu là "Tử số" nhờ có metadata của bài học, thay vì trả lời chung chung.

C. Retrieve Node (Bộ truy xuất kiến thức)
Đây là điểm kết nối với Pipeline Truy xuất (đã trình bày ở Mục 3.2). Node này thực hiện chuỗi hành động:
- Query Rewriting: Viết lại câu hỏi dựa trên lịch sử chat (ví dụ: "Nó là gì?" -> "Phân số là gì?").
- Hybrid Search: Gọi Vector DB để tìm kiếm các chunk văn bản phù hợp nhất, sử dụng bộ lọc metadata để giới hạn phạm vi tìm kiếm trong bài học hiện tại.
- Context Update: Cập nhật nội dung tìm được vào trường context của State.

D. Generation Nodes (Các bộ não tạo sinh)
Để tối ưu hóa trải nghiệm người dùng, nhóm không sử dụng một prompt chung cho tất cả trường hợp mà tách thành hai nhánh xử lý riêng biệt:
Answer Node (Chế độ Trả lời nhanh):
- Kích hoạt khi: intent == 'normal'.
- Nhiệm vụ: Đóng vai trò như một từ điển sống.
- Chiến lược: Trả lời ngắn gọn, trực tiếp vào vấn đề, trích dẫn chính xác định nghĩa từ tài liệu. Không lan man giải thích dông dài.

Explain Node (Chế độ Giảng giải sâu):
- Kích hoạt khi: intent == 'deep'.
- Nhiệm vụ: Đóng vai trò là một giáo viên sư phạm.
- Chiến lược: Sử dụng kỹ thuật Chain-of-Thought (CoT) để kích hoạt khả năng suy luận từng bước. Prompt yêu cầu mô hình không được đưa ra đáp án ngay mà phải:
  - Bước 1: Phân tích khó khăn của học sinh.
  - Bước 2: Tìm ví dụ ẩn dụ (Analogy) gần gũi với đời sống (bánh kẹo, hoa quả).
  - Bước 3: Hướng dẫn giải quyết vấn đề từng bước một.

3.4.4. Cơ chế Điều hướng và Luồng Điều khiển (Routing Logic)
Sự linh hoạt và thông minh của Agent nằm ở các Conditional Edges (Cạnh điều kiện). Thay vì luồng đi cứng nhắc, hệ thống sử dụng một hàm Router (Bộ định tuyến) để quyết định bước tiếp theo dựa trên trạng thái hiện tại.

Thuật toán Router (Mã giả):
```python
def route_intent(state: AgentState) -> Literal["answer", "explain"]:
    """Route by intent"""
    return "explain" if state.get("intent") == "deep" else "answer"
```

Trong LangGraph, logic này được cấu hình như sau:
```python
    # Conditional routing by intent
    workflow.add_conditional_edges(
        "retrieve",
        route_intent,
        {"answer": "answer", "explain": "explain"}
    )
```
Cơ chế này đảm bảo tài nguyên tính toán được phân bổ hợp lý: những câu hỏi đơn giản được xử lý nhanh gọn, trong khi những vấn đề phức tạp nhận được sự "đầu tư" suy luận sâu sắc hơn.

3.4.5. Kỹ thuật Prompt Engineering Chuyên sâu
Để Agent thực sự mang "linh hồn" của một giáo viên Toán tiểu học chứ không phải một cỗ máy vô cảm, nhóm đã áp dụng kỹ thuật Persona Prompting kết hợp với In-Context Learning cực kỳ chi tiết.

Cấu trúc System Prompt cho Explain Node:
```text
{teacher_role}

**TASK**: Provide a **DETAILED**, **STEP-BY-STEP** explanation suitable for a Grade {grade} student.

**LESSON INFO**:
- Subject: {subject} | Grade: {grade} | Topic: {topic}
--------------
**LESSON CONTEXT**:
{context}
--------------

**STUDENT QUESTION**: "{question}"

{accuracy_constraints}

**PLANNING INSTRUCTION (Internal Thought)**:
Before generating the response, think about:
1. **Barrier Analysis**: What specific concept is confusing the student?
2. **Analogy/Example**: What real-world example (e.g., candy, money, toys) fits this concept?
3. **Structure**: How to break this down into simple steps (Step 1, Step 2...)?

**RESPONSE GUIDELINES**:
- Start with encouragement.
- Use bullet points or numbered steps for clarity.
- Use the analogy thought of in the planning phase.
- End with a "Check for Understanding" question (e.g., "Con thấy chỗ này dễ hiểu hơn chưa?").

**OUTPUT**: (Vietnamese, "Cô - Con" style)
```

3.4.6. Tích hợp Công cụ Mở rộng (Tool Calling Strategy)
Ngoài khả năng hội thoại, Agent còn được trang bị "tay chân" để thực hiện các hành động cụ thể thông qua cơ chế Tool Calling. Các công cụ này được định nghĩa dưới dạng Function Schema và được LLM tự động gọi khi cần thiết.

3.4.6.1. Mindmap Generator Tool (Công cụ vẽ sơ đồ tư duy)
Để hỗ trợ phương pháp học tập trực quan (Visual Learning), nhóm phát triển công cụ tự động tạo sơ đồ tư duy từ nội dung bài học.

#### Cơ chế hoạt động:
1.  **Trigger**: Người dùng nhấn nút "Tạo sơ đồ tư duy" trên giao diện bài học.
2.  **Auto Extraction**: Hệ thống tự động xác định chủ đề bài học (Lesson Title) từ ID bài học.
3.  **Topic Cleaning**: Sử dụng Regex để làm sạch tiêu đề (ví dụ "Toán lớp 4 Bài 1..." -> "Bài 1...").
4.  **Retrieval**: Truy xuất 5 chunks quan trọng nhất về chủ đề đã làm sạch từ Vector DB.
5.  **Generation**: LLM (GPT-4o JSON Mode) tạo cấu trúc cây (nodes/edges) dựa trên ngữ cảnh được cung cấp.

#### Evidence (Code):
```python
# tools/mindmap.py
def generate_mindmap_json(lesson_id: Union[str, int]) -> dict:
    # ... logic lấy metadata ...
    full_title = lesson.get("title", "Bài học")
    
    # Auto-clean topic from title
    clean_title = re.sub(r'Toán\s+lớp\s+\d+\s*', '', full_title, flags=re.IGNORECASE)
    # ... more cleaning logic ...
    
    # Generate mindmap for CLEAN topic
    metadata["topic"] = clean_title
    context = get_context(metadata["topic"], k=5, lesson_id=lesson_id)
    # ...
```
    # 2. Format prompt with context
    prompt = format_prompt(
        SYSTEM_PROMPTS["mindmap"],
        context=context
    )
    
    # 3. Request LLM to generate strict JSON
    llm = ChatOpenAI(model="gpt-4o", model_kwargs={"response_format": {"type": "json_object"}})
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # 4. Parse returning JSON
    return json.loads(response.content)
```

**System Prompt (Mindmap)**:
```text
TASK: Generate React Flow mindmap JSON.

LESSON CONTEXT:
{context}

TOPIC: {topic}

Return ONLY valid JSON with nodes and edges. Root at top, main branches below.
```

3.4.6.2. Learning Analyzer Tool (Công cụ phân tích học tập)
    Công cụ này đóng vai trò như một "Giáo viên chủ nhiệm" ảo, hoạt động ngầm để theo dõi sự tiến bộ của học sinh.

#### Cơ chế hoạt động:
1.  **Thu thập dữ liệu**: Tải toàn bộ lịch sử hội thoại của phiên học hiện tại.
2.  **Contextualize**: Xác định ngữ cảnh bài học dựa trên `lesson_id` (nếu có).
3.  **Đánh giá (LLM)**: LLM đóng vai "Assessor" phân tích log chat để xác định mức độ hiểu bài, các lỗ hổng kiến thức.
4.  **Xếp loại**: Dựa trên số lượng tương tác và chất lượng câu hỏi (ví dụ: >10 tin nhắn là Tích cực).

#### Evidence (Code):
```python
# tools/analyzer.py
def analyze_session(conversation_history: str, lesson_id: Union[str, int]) -> dict:
    # ... get metadata ...
    
    # Analyze with context
    prompt = format_prompt(
        SYSTEM_PROMPTS["analyzer"],
        conversation_history=conversation_history,
        metadata=metadata
    )
    # ... return analysis + level
```
    analysis = llm.invoke([HumanMessage(content=prompt)]).content
    
    # 3. Rule-based Level Assessment
    messages_count = conversation_history.count("\n") // 2
    if messages_count >= 10:
        level = "Tốt"
    elif messages_count >= 5:
        level = "Trung bình"
    else:
        level = "Cần cải thiện"
        
    return {
        "analysis": analysis,
        "level": level
    }
```

**System Prompt (Analyzer)**:
```text
You are an Objective Educational Assessor.
TASK: Evaluate the learning session.

CHAT HISTORY:
{conversation_history}

OUTPUT FORMAT (Vietnamese):
1. Kiến thức đã học: ...
2. Điểm mạnh: ...
3. Cần cải thiện: ...
4. Lời khuyên: ...
```

3.4.7. Tổng kết Kiến trúc Hệ thống
Kiến trúc Agent hướng đồ thị (Graph-based Architecture) với nền tảng LangGraph, kết hợp cùng chiến lược Prompt Engineering chuyên sâu và cơ chế Tool Calling linh hoạt, đã tạo nên một hệ thống trợ lý ảo giáo dục vượt trội. Hệ thống không chỉ có khả năng trả lời chính xác nhờ RAG, mà còn sở hữu "trí tuệ sư phạm": biết phân loại nhu cầu, biết điều chỉnh phương pháp giải thích, và biết sử dụng công cụ hỗ trợ trực quan. Đây là bước tiến quan trọng, chuyển dịch từ mô hình Chatbot hỏi-đáp thụ động sang mô hình AI Companion (Người đồng hành) chủ động trong giáo dục.
