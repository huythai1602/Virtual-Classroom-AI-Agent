"""
Lessons repository - Consolidated from database/lessons_repository.py
"""
from typing import Union
from typing import Union
import json
from .db import get_connection


def get_lesson(lesson_id: Union[str, int]) -> dict:
    """Get lesson by ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        row = None
        
        # 1. Start by treating it as the Public 'lesson_id' (varchar)
        # This is the primary identifier used by Frontend/Agent
        query = """
            SELECT lesson_id, title, subject, grade, transcript, total_chunks, status, metadata
            FROM lessons
            WHERE lesson_id = %s;
        """
        cursor.execute(query, (str(lesson_id),))
        row = cursor.fetchone()
            
        # 2. Fallback: If not found, check if it's an internal Numeric PK
        # Only do this if ignoring the lesson_id didn't work and it looks like an int
        if not row:
            try:
                numeric_id = int(lesson_id)
                query_pk = """
                    SELECT lesson_id, title, subject, grade, transcript, total_chunks, status, metadata
                    FROM lessons
                    WHERE id = %s;
                """
                cursor.execute(query_pk, (numeric_id,))
                row = cursor.fetchone()
            except ValueError:
                pass
        
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
    with get_connection() as conn:
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
        
        return [
            {
                "lesson_id": row[0],
                "title": row[1],
                "subject": row[2],
                "grade": row[3],
                "total_chunks": row[4],
                "status": row[5]
            }
            for row in rows
        ]


def insert_lesson(lesson_data: dict):
    """Insert or update lesson"""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            INSERT INTO lessons (lesson_id, title, subject, grade, transcript, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
            ON CONFLICT (lesson_id) DO UPDATE SET
                title = EXCLUDED.title,
                subject = EXCLUDED.subject,
                grade = EXCLUDED.grade,
                transcript = EXCLUDED.transcript,
                metadata = EXCLUDED.metadata,
                status = 'pending';
        """
        # Ensure metadata is JSON string if it's a dict
        meta = lesson_data.get("metadata", {})
        if isinstance(meta, dict):
            meta = json.dumps(meta)

        cursor.execute(query, (
            lesson_data["lesson_id"],
            lesson_data.get("title"),
            lesson_data.get("subject"),
            lesson_data.get("grade"),
            lesson_data.get("transcript"),
            meta
        ))
        cursor.close()


def update_lesson_status(lesson_id: str, status: str, total_chunks: int = 0):
    """Update lesson status"""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            UPDATE lessons 
            SET status = %s, total_chunks = %s
            WHERE lesson_id = %s;
        """
        cursor.execute(query, (status, total_chunks, lesson_id))
        cursor.close()
