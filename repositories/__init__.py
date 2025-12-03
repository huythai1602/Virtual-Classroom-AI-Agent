"""Repositories module - Data access layer"""
from .db import get_connection
from .chunks import search_similar_chunks, get_chunks_by_lesson, get_all_chunks
from .lessons import get_lesson, get_all_lessons
from .sessions import (
    get_session,
    create_or_update_session,
    delete_session,
    get_user_sessions,
    cleanup_old_sessions
)

__all__ = [
    "get_connection",
    "search_similar_chunks",
    "get_chunks_by_lesson",
    "get_all_chunks",
    "get_lesson",
    "get_all_lessons",
    "get_session",
    "create_or_update_session",
    "delete_session",
    "get_user_sessions",
    "cleanup_old_sessions"
]
