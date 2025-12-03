"""
Sessions repository - PostgreSQL persistent conversation storage
"""
from repositories.db import get_connection
from typing import Dict, Any, Optional, List
import json
from datetime import datetime


def get_session(thread_id: str) -> Optional[Dict[str, Any]]:
    """Get session from database"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT thread_id, user_id, messages, context, metadata, 
                   created_at, updated_at, last_activity
            FROM sessions
            WHERE thread_id = %s;
        """
        cursor.execute(query, (thread_id,))
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                "thread_id": row[0],
                "user_id": row[1],
                "messages": row[2] if isinstance(row[2], list) else json.loads(row[2] or "[]"),
                "context": row[3],
                "metadata": row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}"),
                "created_at": row[5].isoformat() if row[5] else None,
                "updated_at": row[6].isoformat() if row[6] else None,
                "last_activity": row[7].isoformat() if row[7] else None
            }
        return None


def create_or_update_session(
    thread_id: str,
    user_id: str,
    messages: List[Dict],
    context: str = "",
    metadata: Dict = None
) -> bool:
    """Create or update session in database"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if metadata is None:
            metadata = {}
        
        query = """
            INSERT INTO sessions (thread_id, user_id, messages, context, metadata, last_activity)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (thread_id) 
            DO UPDATE SET
                messages = EXCLUDED.messages,
                context = EXCLUDED.context,
                metadata = EXCLUDED.metadata,
                last_activity = CURRENT_TIMESTAMP;
        """
        
        try:
            cursor.execute(query, (
                thread_id,
                user_id,
                json.dumps(messages),
                context,
                json.dumps(metadata)
            ))
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"❌ Error saving session: {e}")
            cursor.close()
            return False


def delete_session(thread_id: str) -> bool:
    """Delete session from database"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = "DELETE FROM sessions WHERE thread_id = %s;"
        cursor.execute(query, (thread_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()
        return deleted


def get_user_sessions(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get all sessions for a user (most recent first)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT thread_id, messages, last_activity
            FROM sessions
            WHERE user_id = %s
            ORDER BY last_activity DESC
            LIMIT %s;
        """
        cursor.execute(query, (user_id, limit))
        rows = cursor.fetchall()
        cursor.close()
        
        sessions = []
        for row in rows:
            messages = row[1] if isinstance(row[1], list) else json.loads(row[1] or "[]")
            sessions.append({
                "thread_id": row[0],
                "message_count": len(messages),
                "last_activity": row[2].isoformat() if row[2] else None
            })
        
        return sessions


def cleanup_old_sessions(days: int = 30) -> int:
    """Delete sessions older than specified days"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            DELETE FROM sessions
            WHERE last_activity < CURRENT_TIMESTAMP - INTERVAL '%s days';
        """
        cursor.execute(query, (days,))
        conn.commit()
        deleted = cursor.rowcount
        cursor.close()
        return deleted
