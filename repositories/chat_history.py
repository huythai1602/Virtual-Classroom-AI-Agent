from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from repositories.db import get_shared_connection

def get_messages(user_id: int, lesson_id: int, limit: int = 50) -> List[BaseMessage]:
    """
    Retrieve chat history from shared DB
    Returns a list of LangChain BaseMessage objects (HumanMessage, AIMessage)
    """
    messages = []
    
    # Query to fetch messages sorted by time
    query = """
        SELECT role, value 
        FROM lesson_chat_messages 
        WHERE user_id = %s AND lesson_id = %s 
        ORDER BY created_at ASC
    """
    # Note: 'limit' is currently unused to ensure full context for the agent,
    # but could be applied if sessions get too long.
    
    try:
        with get_shared_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, lesson_id))
                rows = cur.fetchall()
                
                for role, content in rows:
                    if role == 'user':
                        messages.append(HumanMessage(content=content))
                    elif role == 'assistant':
                        messages.append(AIMessage(content=content))
                        
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        # Return empty list on error to allow chat to proceed (cold start)
        return []
                    
    return messages

def add_message(user_id: int, lesson_id: int, role: str, content: str):
    """
    Save a message to the shared DB.
    role: 'human' or 'ai' (or 'user'/'assistant')
    """
    # Map LangChain roles to DB Enum ('user', 'assistant')
    db_role = 'user'
    if role == 'ai' or role == 'assistant':
        db_role = 'assistant'
    
    query = """
        INSERT INTO lesson_chat_messages (user_id, lesson_id, role, value, created_at, updated_at)
        VALUES (%s, %s, %s, %s, NOW(), NOW())
    """
    
    try:
        with get_shared_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, lesson_id, db_role, content))
            # Commit is handled by context manager if no exception? 
            # Check db.py. Usually context manager for connection doesn't auto-commit if it's just 'get_connection'.
            # Let's explicitly commit to be safe, or check db.py implementation.
            conn.commit()
    except Exception as e:
        print(f"Error saving chat message: {e}")
        # Log but don't crash the flow?
