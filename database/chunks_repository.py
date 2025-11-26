"""
Repository for chunks table operations with pgvector similarity search
"""

from database.db_connection import get_db_connection
from pgvector.psycopg2 import register_vector


def insert_chunks_batch(lesson_id: str, chunks_data: list):
    """
    Batch insert chunks with embeddings
    
    Args:
        lesson_id: Lesson identifier
        chunks_data: [
            {"chunk_index": 0, "text": "...", "embedding": [0.1, -0.2, ...]},
            {"chunk_index": 1, "text": "...", "embedding": [0.3, 0.4, ...]},
            ...
        ]
    """
    with get_db_connection() as conn:
        # Register vector type for pgvector
        register_vector(conn)
        
        cursor = conn.cursor()
        
        # Delete old chunks if re-indexing
        cursor.execute("DELETE FROM chunks WHERE lesson_id = %s;", (lesson_id,))
        
        # Batch insert
        query = """
            INSERT INTO chunks (lesson_id, chunk_index, text, embedding)
            VALUES (%s, %s, %s, %s);
        """
        
        for chunk in chunks_data:
            cursor.execute(query, (
                lesson_id,
                chunk["chunk_index"],
                chunk["text"],
                chunk["embedding"]  # pgvector auto-converts list to vector type
            ))
        
        cursor.close()
        print(f"✅ Inserted {len(chunks_data)} chunks for lesson: {lesson_id}")


def search_similar_chunks(query_embedding: list, lesson_id: str = None, k: int = 7) -> list:
    """
    Vector similarity search using pgvector cosine distance
    
    Args:
        query_embedding: Query vector [0.1, -0.2, ...] (1536 dimensions)
        lesson_id: Optional filter by specific lesson (supports numeric id or string slug)
        k: Number of results to return
    
    Returns:
        List of similar chunks:
        [
            {
                "chunk_id": 123,
                "lesson_id": "toan-lop-4-bai-1",
                "text": "Chữ số 6 ở hàng...",
                "similarity": 0.89,
                "chunk_index": 5
            },
            ...
        ]
    """
    with get_db_connection() as conn:
        register_vector(conn)
        cursor = conn.cursor()
        
        # Cosine similarity: 1 - (embedding <=> query_embedding)
        # <=> is pgvector's cosine distance operator
        
        if lesson_id:
            # Support both numeric id and string lesson_id
            try:
                numeric_id = int(lesson_id)
                query = """
                    SELECT 
                        c.id,
                        c.lesson_id,
                        c.chunk_index,
                        c.text,
                        1 - (c.embedding <=> %s::vector) AS similarity
                    FROM chunks c
                    JOIN lessons l ON c.lesson_id = l.lesson_id
                    WHERE l.id = %s
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s;
                """
                cursor.execute(query, (query_embedding, numeric_id, query_embedding, k))
            except ValueError:
                # Use as string lesson_id
                query = """
                    SELECT 
                        id,
                        lesson_id,
                        chunk_index,
                        text,
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
                    id,
                    lesson_id,
                    chunk_index,
                    text,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """
            cursor.execute(query, (query_embedding, query_embedding, k))
        
        rows = cursor.fetchall()
        cursor.close()
        
        results = []
        for row in rows:
            results.append({
                "chunk_id": row[0],
                "lesson_id": row[1],
                "chunk_index": row[2],
                "text": row[3],
                "similarity": float(row[4])
            })
        
        return results


def get_chunks_by_lesson(lesson_id: str) -> list:
    """Get all chunks for a specific lesson"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT id, chunk_index, text
            FROM chunks
            WHERE lesson_id = %s
            ORDER BY chunk_index;
        """
        
        cursor.execute(query, (lesson_id,))
        rows = cursor.fetchall()
        cursor.close()
        
        chunks = []
        for row in rows:
            chunks.append({
                "chunk_id": row[0],
                "chunk_index": row[1],
                "text": row[2]
            })
        
        return chunks


def delete_chunks_by_lesson(lesson_id: str):
    """Delete all chunks for a specific lesson"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = "DELETE FROM chunks WHERE lesson_id = %s;"
        cursor.execute(query, (lesson_id,))
        cursor.close()


def get_chunks_count() -> int:
    """Get total number of chunks in database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM chunks;")
        count = cursor.fetchone()[0]
        cursor.close()
        
        return count
