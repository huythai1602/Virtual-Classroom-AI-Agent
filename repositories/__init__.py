"""Repositories module - Data access layer"""
from .db import get_connection
from .chunks import search_similar_chunks, get_chunks_by_lesson, get_all_chunks
from .lessons import get_lesson, get_all_lessons

__all__ = [
    "get_connection",
    "search_similar_chunks",
    "get_chunks_by_lesson",
    "get_all_chunks",
    "get_lesson",
    "get_all_lessons"
]
