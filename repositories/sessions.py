"""
Sessions repository - PostgreSQL persistent conversation storage
"""
from repositories.db import get_connection, get_shared_connection
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
            
            # Sync to shared database if configured
            # Extract last message
            if messages:
                last_msg = messages[-1]
                # Only sync detailed messages (skip system or simple acks if needed, but syncing all is safer)
                msg_content = last_msg.get("content", "")
                msg_role = last_msg.get("role", "user")
                
                # Simple Logic: Only sync if content exists
                if msg_content:
                    # Get Lesson ID from metadata if available
                    lesson_id = metadata.get("lesson_id") if metadata else None
                    if not lesson_id:
                        # Try to find in context string if we parsed it? Unlikely reliable.
                        # For now send None or Default.
                        pass
                        
                    sync_message_to_shared_db(
                        thread_id=thread_id,
                        role=msg_role,
                        content=msg_content,
                        user_id=user_id, # String ID, will be mapped in sync func
                        lesson_id=lesson_id
                    )

            return True
        except Exception as e:
            print(f"❌ Error saving session: {e}")
            cursor.close()
            return False


def sync_message_to_shared_db(thread_id: str, role: str, content: str, user_id: str, lesson_id: Any = None):
    """
    Adapter function to sync messages to shared Supabase table.
    Table: lesson_chat_messages(id, created_at, updated_at, user_id, value, lesson_id, role)
    """
    # 1. Map Role (LangGraph -> Supabase Enum/String)
    # Supabase roles: likely 'user' and 'bot' or 'assistant'
    db_role = role
    if role == "assistant":
        db_role = "bot" # Assumption based on common schemas, or keep 'assistant' if enum allows
    
    # 2. Map User ID (String -> Int)
    # This is the tricky part. For now, we use a fixed ID for the Agent/Shared user if not provided.
    # If the user_id string looks like an integer, use it. Otherwise default.
    db_user_id = 0 # Default/System user
    try:
        if user_id and str(user_id).isdigit():
            db_user_id = int(user_id)
        # Else: keep 0
    except:
        pass
        
    # 3. Lesson ID
    db_lesson_id = None
    if lesson_id:
        try:
            db_lesson_id = int(lesson_id)
        except:
            pass

    try:
        with get_shared_connection() as conn:
            if conn is None:
                # Shared DB not configured or failed
                return

            with conn.cursor() as cur:
                query = """
                    INSERT INTO lesson_chat_messages (created_at, updated_at, user_id, value, lesson_id, role)
                    VALUES (CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s, %s, %s);
                """
                cur.execute(query, (db_user_id, content, db_lesson_id, db_role))
            # Commit handled by context manager
    except Exception as e:
        print(f"⚠️ Failed to sync to shared DB: {e}") 
        # Non-blocking error, we don't return False here as local save succeeded


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
