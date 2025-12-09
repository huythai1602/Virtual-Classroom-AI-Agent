# Codebase Review Report

## 1. Architecture Overview
**Status:** ✅ Good structure

The project follows a clean Layered Architecture:
- `core/`: Business logic and core algorithms (LangGraph agent).
- `services/`: Business services (Ingestion, RAG).
- `repositories/`: Data Access Layer (DAL).
- `config/`: Centralized configuration.
- `models/`: Data models (Pydantic).

This separation of concerns is healthy and facilitates testing and maintenance.

## 2. Key Findings & Recommendations

### A. Data Access Layer (Repositories)
**Current:** Using raw SQL with `psycopg2` via context managers.
**Issue:** 
- Boilerplate code is repetitive (open connection, cursor, execute, close).
- Manual string handling for queries makes refactoring harder.
- Lack of type safety for DB results (retrieving by index `row[0]`).

**Recommendation:**
- **Mid-term:** Adopt a lightweight ORM (like **SQLAlchemy** or **TortoiseORM**) or a Query Builder (like **Pypika**).
- **Short-term:** Create a generic `execute_query` wrapper to reduce boilerplate (open/close connection automatically).

### B. Dependency Injection & Global State
**Current:** Global Singletons usage manually (`_retriever = None`, `def get_retriever()`).
**Issue:** 
- Makes unit testing harder because global state persists between tests.
- Hard dependencies in `agent.py` importing global instances.

**Recommendation:**
- Use a lightweight DI container (like `DependencyInjector` or simple class-based injection).
- Pass dependencies into functions rather than importing globals (e.g., pass `retriever` to `retrieve_node`).

### C. Text Processing & Ingestion
**Current:** 
- `IngestionService` contains specific logic for parsing filenames (`parse_filename` with regex).
- Hardcoded rules for Vietnamese text normalization.

**Issue:** 
- Business logic (filename parsing) is coupled with Ingestion logic. If file naming conventions change, the Service code must be modified.

**Recommendation:**
- Extract `MetadataExtractor` as a separate strategy interface.
- Move Vietnamese-specific regex to a configuration or a specialized `VietnameseTokenizer` class (which `TextProcessor` can use).

### D. Testing
**Current:** `tests/` directory exists but seems underutilized or not standardized seen from file listing impact.
**Recommendation:**
- Add **Unit Tests** for `TextProcessor.split_by_tokens` and `RAGRetriever.adaptive_k`.
- Add **Integration Tests** for the full RAG pipeline using a test DB.

### E. Configuration
**Status:** ✅ Excellent
- Using `pydantic_settings` is a best practice.
- Environment variables are well managed.

## 3. Specific Refactoring Opportunities

| Priority | File | Suggestion |
| :--- | :--- | :--- |
| 🔴 High | `repositories/chunks.py` | Add strong typing for return values (use Pydantic models instead of dicts). |
| 🟡 Medium | `services/ingestion/processor.py` | Isolate `parse_filename` into a separate helper/strategy to decouple file naming convention from ingestion logic. |
| 🟡 Medium | `core/agent.py` | Move prompt templates (`SYSTEM_PROMPTS`) entirely to `config/prompts.py` (partially done, but ensure all strings are externalized). |
| 🟢 Low | `core/text_processing.py` | `split_sentences_vn` is a heuristic. Consider using a dedicated NLP library (VnCoreNLP) if accuracy becomes an issue. |

## 4. Conclusion
The codebase is clean, functional, and pragmatic. The recent refactoring to **Parent-Document Retrieval** has significantly modernized the core logic. The main area for "Production-Grade" improvement is shifting from raw SQL to an ORM and improving test coverage.
