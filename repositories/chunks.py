"""
Chunks repository - Consolidated from database/chunks_repository.py
"""
from typing import Union
from pgvector.psycopg2 import register_vector
from .db import get_connection


def search_similar_chunks(query_embedding: list, lesson_id: Union[str, int] = None, k: int = 7) -> list:
    """
    Vector similarity search using pgvector
    
    Returns:
        [{"chunk_id": 123, "lesson_id": "...", "text": "...", "similarity": 0.89, "chunk_index": 5}]
    """
    with get_connection() as conn:
        register_vector(conn)
        cursor = conn.cursor()
        
        if lesson_id:
            try:
                numeric_id = int(lesson_id)
                query = """
                    SELECT 
                        c.id, c.lesson_id, c.chunk_index, c.text, c.parent_content,
                        1 - (c.embedding <=> %s::vector) AS similarity
                    FROM chunks c
                    JOIN lessons l ON c.lesson_id = l.lesson_id
                    WHERE l.id = %s
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s;
                """
                cursor.execute(query, (query_embedding, numeric_id, query_embedding, k))
            except ValueError:
                query = """
                    SELECT 
                        id, lesson_id, chunk_index, text, parent_content,
                        1 - (embedding <=> %s::vector) AS similarity
                    FROM chunks
                    WHERE lesson_id = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                """
                cursor.execute(query, (query_embedding, lesson_id, query_embedding, k))
        else:
            query = """
                SELECT 
                    id, lesson_id, chunk_index, text, parent_content,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """
            cursor.execute(query, (query_embedding, query_embedding, k))
        
        rows = cursor.fetchall()
        cursor.close()
        
        return [
            {
                "chunk_id": row[0],
                "lesson_id": row[1],
                "chunk_index": row[2],
                "text": row[3],
                "parent_content": row[4] if len(row) > 4 else None,
                "similarity": float(row[5])
            }
            for row in rows
        ]


def get_chunks_by_lesson(lesson_id: Union[str, int]) -> list:
    """Get all chunks for a lesson (supports both lesson_id string and lessons.id integer)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # If integer, join with lessons table to get lesson_id
        if isinstance(lesson_id, int):
            query = """
                SELECT c.id, c.lesson_id, c.chunk_index, c.text
                FROM chunks c
                JOIN lessons l ON c.lesson_id = l.lesson_id
                WHERE l.id = %s
                ORDER BY c.chunk_index;
            """
        else:
            query = """
                SELECT id, lesson_id, chunk_index, text
                FROM chunks
                WHERE lesson_id = %s
                ORDER BY chunk_index;
            """
        
        cursor.execute(query, (lesson_id,))
        rows = cursor.fetchall()
        cursor.close()
        
        return [
            {
                "id": row[0],
                "lesson_id": row[1],
                "chunk_index": row[2],
                "text": row[3]
            }
            for row in rows
        ]


def get_all_chunks(limit: int = 10000) -> list:
    """Get all chunks (for BM25 indexing)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT id, lesson_id, chunk_index, text
            FROM chunks
            ORDER BY lesson_id, chunk_index
            LIMIT %s;
        """
        
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        cursor.close()
        
        return [
            {
                "id": row[0],
                "lesson_id": row[1],
                "chunk_index": row[2],
                "text": row[3]
            }
            for row in rows
        ]


def insert_chunks_batch(lesson_id: str, chunks_data: list):
    """Batch insert chunks with embeddings"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get lesson PK
        # Note: lesson_id here is the string ID (e.g. 'toan-lop-4...'), table uses 'lesson_id' column
        # But wait, chunks table links to lessons(id)? 
        # Let's check get_chunks_by_lesson ... JOIN lessons l ON c.lesson_id = l.lesson_id ...
        # If chunks.lesson_id is a FK to lessons.lesson_id (string), then we don't need PK lookup.
        # However, checking search_similar_chunks: JOIN lessons l... WHERE l.id = %s
        # It seems the schema might use string ID as FK? or PK?
        # Let's look at `repositories/lessons.py` query again: WHERE id = %s vs WHERE lesson_id = %s
        # Schema likely has `id` (serial) and `lesson_id` (string unique).
        # Let's assume chunks.lesson_id refers to lessons.lesson_id (string) OR lessons.id (int).
        
        # Safer bet: Look at `chunks` table schema via existing queries.
        # "JOIN lessons l ON c.lesson_id = l.lesson_id" implies chunks.lesson_id matches lessons.lesson_id (string).
        # WAIIIIT.
        # "WHERE l.id = %s" (numeric).
        # If c.lesson_idLinked to l.lesson_id, then both are strings.
        
        # Let's try to just use the string lesson_id.
        
        query = """
            INSERT INTO chunks (lesson_id, chunk_index, text, embedding, parent_content)
            VALUES (%s, %s, %s, %s, %s)
        """
        # BUT: previous usage in migrate script: "insert_chunks_batch(lesson_id, chunks_data)"
        # where lesson_id is string.
        # The schema probably requires the string since the join uses string.
        
        # Actually, let's look at `search_similar_chunks`:
        # JOIN lessons l ON c.lesson_id = l.lesson_id
        # This implies c.lesson_id is the string ID same as l.lesson_id.
        
        # Clean current chunks for this lesson
        cursor.execute("DELETE FROM chunks WHERE lesson_id = %s", (lesson_id,))
        
        values = [
            (lesson_id, c["chunk_index"], c["text"], c["embedding"], c.get("parent_content", None)) 
            for c in chunks_data
        ]
        
        cursor.executemany(query, values)
        cursor.close()
