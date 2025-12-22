
from typing import Dict, Any, List, Optional
from services.rabbitmq import rabbitmq_service

def get_quiz_data(lesson_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch Quiz Data via RPC
    Pattern: GET_QUIZ_DATA
    """
    payload = {"lessonId": lesson_id}
    response = rabbitmq_service.rpc_call("GET_QUIZ_DATA", payload)
    
    if response and response.get("success"):
        return response
    return None

def get_lesson_transcript(lesson_id: int) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch Lesson Transcript via RPC
    Pattern: GET_LESSON_TRANSCRIPT
    """
    payload = {"lessonId": lesson_id}
    response = rabbitmq_service.rpc_call("GET_LESSON_TRANSCRIPT", payload)
    
    if response and response.get("success"):
        return response.get("transcript", [])
    return []

def get_chat_history_via_rpc(user_id: int, lesson_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch Chat History via RPC
    Pattern: GET_CHAT_HISTORY
    """
    payload = {
        "userId": user_id,
        "lessonId": lesson_id,
        "limit": limit
    }
    response = rabbitmq_service.rpc_call("GET_CHAT_HISTORY", payload)
    
    if response and response.get("success"):
        return response.get("messages", [])
    return []

def get_quiz_attempts(user_id: int, lesson_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch Quiz Attempts via RPC
    Pattern: GET_QUIZ_ATTEMPTS
    """
    payload = {
        "userId": user_id,
        "lessonId": lesson_id
    }
    response = rabbitmq_service.rpc_call("GET_QUIZ_ATTEMPTS", payload)
    
    if response and response.get("success"):
        return response.get("data", None) # Expecting 'data' or specific fields
    return None

def get_analysis_history(user_id: int, lesson_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch Analysis History via RPC
    Pattern: GET_ANALYSIS_HISTORY
    """
    payload = {
        "userId": user_id,
        "lessonId": lesson_id,
        "limit": limit
    }
    response = rabbitmq_service.rpc_call("GET_ANALYSIS_HISTORY", payload)
    
    if response and response.get("success"):
        return response.get("history", [])
    return []
