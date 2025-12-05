"""Mindmap generation tool
Consolidated from agent/tools/mindmap_tool.py
"""
import json
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


def generate_mindmap_json(topic: str, lesson_id: Union[str, int] = None) -> dict:
    """
    Generate mindmap JSON for React Flow
    
    Args:
        topic: Topic for mindmap
        lesson_id: Optional lesson ID for metadata
        
    Returns:
        dict with nodes and edges
    """
    # Get context
    context = get_context(topic, k=5, lesson_id=lesson_id)
    
    # Get metadata
    metadata = DEFAULT_METADATA.copy()
    if lesson_id:
        lesson = get_lesson(lesson_id)
        if lesson:
            metadata["subject"] = lesson.get("subject", "Toán")
            metadata["grade"] = lesson.get("grade", 4)
            metadata["topic"] = lesson.get("title", topic)
    else:
        metadata["topic"] = topic
    
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
        return json_data
    except json.JSONDecodeError:
        return {
            "error": "Không thể tạo sơ đồ tư duy cho yêu cầu này.",
            "nodes": [],
            "edges": []
        }
