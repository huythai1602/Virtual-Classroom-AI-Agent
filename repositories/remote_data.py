"""
Remote Data Repository - RPC calls to Course Service WITH CACHING
"""
from typing import Dict, Any, List, Optional
from services.rabbitmq import rabbitmq_service
from .cache import get_cached, set_cached


def get_quiz_data(lesson_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch Quiz Data via RPC with caching
    Pattern: GET_QUIZ_DATA
    """
    payload = {"lessonId": lesson_id}
    
    # Check cache first
    cached = get_cached("GET_QUIZ_DATA", payload)
    if cached:
        return cached
    
    # Make RPC call
    response = rabbitmq_service.rpc_call("GET_QUIZ_DATA", payload)
    
    if response and response.get("success"):
        set_cached("GET_QUIZ_DATA", payload, response)
        return response
    return None


def get_lesson_transcript(lesson_id: int) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch Lesson Transcript via RPC with caching
    Pattern: GET_LESSON_TRANSCRIPT
    """
    payload = {"lessonId": lesson_id}
    
    # Check cache first
    cached = get_cached("GET_LESSON_TRANSCRIPT", payload)
    if cached:
        return cached.get("transcript", [])
    
    response = rabbitmq_service.rpc_call("GET_LESSON_TRANSCRIPT", payload)
    
    if response and response.get("success"):
        set_cached("GET_LESSON_TRANSCRIPT", payload, response)
        return response.get("transcript", [])
    return []


def get_chat_history_via_rpc(user_id: int, lesson_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch Chat History via RPC
    Pattern: GET_CHAT_HISTORY
    NOTE: Chat history is NOT cached as it changes frequently
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
    Fetch Quiz Attempts via RPC with caching
    Pattern: GET_QUIZ_ATTEMPTS
    """
    payload = {
        "userId": user_id,
        "lessonId": lesson_id
    }
    
    # Check cache first
    cached = get_cached("GET_QUIZ_ATTEMPTS", payload)
    if cached:
        return cached.get("data", None)
    
    response = rabbitmq_service.rpc_call("GET_QUIZ_ATTEMPTS", payload)
    
    if response and response.get("success"):
        set_cached("GET_QUIZ_ATTEMPTS", payload, response)
        return response.get("data", None)
    return None


def get_analysis_history(user_id: int, lesson_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch Analysis History via RPC with caching
    Pattern: GET_ANALYSIS_HISTORY
    """
    payload = {
        "userId": user_id,
        "lessonId": lesson_id,
        "limit": limit
    }
    
    # Check cache first
    cached = get_cached("GET_ANALYSIS_HISTORY", payload)
    if cached:
        return cached.get("history", [])
    
    response = rabbitmq_service.rpc_call("GET_ANALYSIS_HISTORY", payload)
    
    if response and response.get("success"):
        set_cached("GET_ANALYSIS_HISTORY", payload, response)
        return response.get("history", [])
    return []
