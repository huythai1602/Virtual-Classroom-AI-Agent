"""
Repository for lessons table operations
"""

from database.db_connection import get_db_connection
import json


def insert_lesson(lesson_data: dict) -> str:
    """
    Insert a lesson into lessons table
    
    Args:
        lesson_data: {
            "lesson_id": "toan-lop-4-bai-1",
            "title": "Ôn tập số đến 100000",
            "subject": "Toán",
            "grade": 4,
            "transcript": "Full text...",
            "metadata": {"source_file": "...", "lesson_number": 1}
        }
    
    Returns:
        lesson_id (str)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            INSERT INTO lessons (lesson_id, title, subject, grade, transcript, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lesson_id) 
            DO UPDATE SET 
                title = EXCLUDED.title,
                transcript = EXCLUDED.transcript,
                metadata = EXCLUDED.metadata,
                updated_at = NOW(),
                status = 'pending'
            RETURNING lesson_id;
        """
        
        cursor.execute(query, (
            lesson_data["lesson_id"],
            lesson_data["title"],
            lesson_data["subject"],
            lesson_data["grade"],
            lesson_data["transcript"],
            json.dumps(lesson_data.get("metadata", {})),
            "pending"
        ))
        
        result = cursor.fetchone()
        cursor.close()
        return result[0]


def update_lesson_status(lesson_id: str, status: str, total_chunks: int = 0):
    """Update lesson status after indexing"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            UPDATE lessons 
            SET status = %s, total_chunks = %s, updated_at = NOW()
            WHERE lesson_id = %s;
        """
        
        cursor.execute(query, (status, total_chunks, lesson_id))
        cursor.close()


def get_lesson(lesson_id: str) -> dict:
    """Get lesson by lesson_id or id (supports both string slug and numeric id)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Try to parse as integer first, otherwise use as string
        try:
            numeric_id = int(lesson_id)
            query = """
                SELECT lesson_id, title, subject, grade, transcript, total_chunks, status, metadata
                FROM lessons
                WHERE id = %s;
            """
            cursor.execute(query, (numeric_id,))
        except ValueError:
            # Not a number, use as lesson_id string
            query = """
                SELECT lesson_id, title, subject, grade, transcript, total_chunks, status, metadata
                FROM lessons
                WHERE lesson_id = %s;
            """
            cursor.execute(query, (lesson_id,))
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                "lesson_id": row[0],
                "title": row[1],
                "subject": row[2],
                "grade": row[3],
                "transcript": row[4],
                "total_chunks": row[5],
                "status": row[6],
                "metadata": row[7]
            }
        return None


def get_all_lessons(subject: str = None, grade: int = None) -> list:
    """Get all lessons with optional filters"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = "SELECT lesson_id, title, subject, grade, total_chunks, status FROM lessons"
        params = []
        conditions = []
        
        if subject:
            conditions.append("subject = %s")
            params.append(subject)
        
        if grade:
            conditions.append("grade = %s")
            params.append(grade)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY subject, grade, lesson_id;"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        
        lessons = []
        for row in rows:
            lessons.append({
                "lesson_id": row[0],
                "title": row[1],
                "subject": row[2],
                "grade": row[3],
                "total_chunks": row[4],
                "status": row[5]
            })
        
        return lessons


def delete_lesson(lesson_id: str):
    """Delete lesson and all its chunks (CASCADE)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = "DELETE FROM lessons WHERE lesson_id = %s;"
        cursor.execute(query, (lesson_id,))
        cursor.close()
