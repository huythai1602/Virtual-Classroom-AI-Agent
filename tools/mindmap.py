"""Mindmap generation tool
Consolidated from agent/tools/mindmap_tool.py
"""
import json
import re
from typing import Union
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config.settings import settings
from config.prompts import SYSTEM_PROMPTS, format_prompt, DEFAULT_METADATA
from services.rag import get_context
from repositories.lessons import get_lesson

# Lazy init
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
    return _llm


def generate_mindmap_json(lesson_id: Union[str, int]) -> dict:
    """
    Generate mindmap JSON for React Flow
    
    Args:
        lesson_id: Lesson ID for metadata
        
    Returns:
        dict with nodes, edges, and topic
    """
    
    # Get metadata
    metadata = DEFAULT_METADATA.copy()
    if lesson_id:
        lesson = get_lesson(lesson_id)
        if lesson:
            metadata["subject"] = lesson.get("subject", "Toán")
            metadata["grade"] = lesson.get("grade", 4)
            full_title = lesson.get("title", "Bài học")
            
            # Clean title logic
            # Remove "Toán lớp 4", "Bài X", "Trang Y", extensions, etc.
            # Example: "Toán lớp 4 Bài 1 Ôn tập... - Trang 6..." -> "Ôn tập..."
            
            # 1. Remove "Toán lớp 4" prefix (case insensitive)
            clean_title = re.sub(r'Toán\s+lớp\s+\d+\s*', '', full_title, flags=re.IGNORECASE)
            
            # 2. Remove "Bài X" or "Bài X :" prefix
            clean_title = re.sub(r'Bài\s+\d+(\s*:)?\s*', '', clean_title, flags=re.IGNORECASE)
            
            # 3. Remove suffix starting with " - " (often page numbers, source)
            # Find the first occurrence of " - " and take everything before it
            if " - " in clean_title:
                clean_title = clean_title.split(" - ")[0]
                
            clean_title = clean_title.strip()
            if not clean_title:
                clean_title = full_title # Fallback
                
            metadata["topic"] = clean_title
            
    # Get context with CLEAN topic
    context = get_context(metadata["topic"], k=5, lesson_id=lesson_id)

    # Format prompt
    prompt = format_prompt(
        SYSTEM_PROMPTS["mindmap"],
        context=context,
        topic=metadata["topic"]
    )
    
    # Generate
    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # Parse JSON
    try:
        json_data = json.loads(response.content)
        if "nodes" not in json_data:
            json_data["nodes"] = []
        if "edges" not in json_data:
            json_data["edges"] = []
            
        json_data["topic"] = metadata["topic"]
        return json_data
    except json.JSONDecodeError:
        return {
            "error": "Không thể tạo sơ đồ tư duy cho yêu cầu này.",
            "nodes": [],
            "edges": [],
            "topic": metadata.get("topic", "")
        }
