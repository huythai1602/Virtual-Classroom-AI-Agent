"""
Chunks repository - Consolidated from database/chunks_repository.py
"""
from pgvector.psycopg2 import register_vector
from .db import get_connection


def search_similar_chunks(query_embedding: list, lesson_id: str = None, k: int = 7) -> list:
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
                        c.id, c.lesson_id, c.chunk_index, c.text,
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
                        id, lesson_id, chunk_index, text,
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
                    id, lesson_id, chunk_index, text,
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
                "similarity": float(row[4])
            }
            for row in rows
        ]


def get_chunks_by_lesson(lesson_id: str) -> list:
    """Get all chunks for a lesson"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
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
