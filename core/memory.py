"""
Session memory management with PostgreSQL persistence
"""
from langgraph.checkpoint.memory import MemorySaver
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage

# Global memory saver for LangGraph
memory_saver = MemorySaver()


class SessionMemory:
    """Manage session data with PostgreSQL persistence"""
    
    def __init__(self):
        # In-memory cache for performance
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 minutes cache
    
    def get_session(self, thread_id: str, user_id: str = None) -> Dict[str, Any]:
        """Get session from cache or database"""
        from repositories.sessions import get_session as db_get_session
        
        # Check cache first
        if thread_id in self._cache:
            return self._cache[thread_id]
        
        # Load from database
        session = db_get_session(thread_id)
        if session:
            # Convert stored messages back to LangChain format
            messages = []
            for msg in session.get("messages", []):
                if isinstance(msg, dict):
                    if msg.get("type") == "human":
                        messages.append(HumanMessage(content=msg.get("content", "")))
                    elif msg.get("type") == "ai":
                        messages.append(AIMessage(content=msg.get("content", "")))
                else:
                    messages.append(msg)
            
            session["messages"] = messages
            self._cache[thread_id] = session
            return session
        
        # Create new session
        new_session = {
            "thread_id": thread_id,
            "user_id": user_id or thread_id.split("_")[1] if "_" in thread_id else "unknown",
            "messages": [],
            "context": "",
            "metadata": {}
        }
        self._cache[thread_id] = new_session
        return new_session
    
    def update_session(self, thread_id: str, data: Dict[str, Any], persist: bool = True):
        """Update session in cache and optionally persist to database"""
        from repositories.sessions import create_or_update_session
        
        # Update cache
        if thread_id not in self._cache:
            self._cache[thread_id] = {}
        self._cache[thread_id].update(data)
        
        # Persist to database
        if persist:
            session = self._cache[thread_id]
            
            # Convert LangChain messages to serializable format
            messages = []
            for msg in session.get("messages", []):
                if hasattr(msg, 'type'):
                    messages.append({
                        "type": msg.type,
                        "content": msg.content
                    })
                else:
                    messages.append(msg)
            
            create_or_update_session(
                thread_id=thread_id,
                user_id=session.get("user_id", "unknown"),
                messages=messages,
                context=session.get("context", ""),
                metadata=session.get("metadata", {})
            )
    
    def clear_session(self, thread_id: str):
        """Clear session from cache and database"""
        from repositories.sessions import delete_session
        
        # Remove from cache
        if thread_id in self._cache:
            del self._cache[thread_id]
        
        # Remove from database
        delete_session(thread_id)
    
    def get_conversation_history(self, thread_id: str) -> str:
        """Get conversation history as text"""
        session = self.get_session(thread_id)
        messages = session.get("messages", [])
        
        history = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                history.append(f"Học sinh: {content}")
            elif role == "assistant":
                history.append(f"Trợ giảng: {content}")
        
        return "\n".join(history)
    
    def get_conversation_window(self, thread_id: str, n: int = 3) -> str:
        """Get last N conversation exchanges for context"""
        session = self.get_session(thread_id)
        messages = session.get("messages", [])
        
        # Get last n*2 messages (n exchanges = n user + n assistant)
        recent_messages = messages[-(n*2):] if len(messages) > n*2 else messages
        
        if not recent_messages:
            return ""
        
        history = []
        for msg in recent_messages:
            if hasattr(msg, 'type'):
                # LangChain message objects
                if msg.type == "human":
                    history.append(f"User: {msg.content}")
                elif msg.type == "ai":
                    history.append(f"Assistant: {msg.content}")
            else:
                # Dict format
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role == "user":
                    history.append(f"User: {content}")
                elif role == "assistant":
                    history.append(f"Assistant: {content}")
        
        return "\n".join(history)


# Global instance
session_memory = SessionMemory()
