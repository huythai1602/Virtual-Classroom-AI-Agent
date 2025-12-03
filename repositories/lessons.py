"""
Lessons repository - Consolidated from database/lessons_repository.py
"""
from typing import Union
from .db import get_connection


def get_lesson(lesson_id: Union[str, int]) -> dict:
    """Get lesson by ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        try:
            numeric_id = int(lesson_id)
            query = """
                SELECT lesson_id, title, subject, grade, transcript, total_chunks, status, metadata
                FROM lessons
                WHERE id = %s;
            """
            cursor.execute(query, (numeric_id,))
        except ValueError:
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
