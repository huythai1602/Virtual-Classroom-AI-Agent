"""
Quản lý memory và checkpointer cho LangGraph
"""
from langgraph.checkpoint.memory import MemorySaver
from typing import Dict, Any

# Khởi tạo MemorySaver cho việc lưu trữ state
memory_saver = MemorySaver()

class SessionMemory:
    """Quản lý memory cho từng session/thread"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def get_session(self, thread_id: str) -> Dict[str, Any]:
        """Lấy thông tin session theo thread_id"""
        if thread_id not in self.sessions:
            self.sessions[thread_id] = {
                "messages": [],
                "context": "",
                "metadata": {}
            }
        return self.sessions[thread_id]
    
    def update_session(self, thread_id: str, data: Dict[str, Any]):
        """Cập nhật thông tin session"""
        if thread_id not in self.sessions:
            self.sessions[thread_id] = {}
        self.sessions[thread_id].update(data)
    
    def clear_session(self, thread_id: str):
        """Xóa session"""
        if thread_id in self.sessions:
            del self.sessions[thread_id]
    
    def get_conversation_history(self, thread_id: str) -> str:
        """Lấy lịch sử hội thoại dưới dạng text"""
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

# Global session memory instance
session_memory = SessionMemory()
