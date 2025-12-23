"""Session analyzer tool
Consolidated from agent/tools/analyzer_tool.py
"""
from typing import Union
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config.prompts import SYSTEM_PROMPTS, format_prompt, DEFAULT_METADATA
from services.rag import get_context
from repositories.lessons import get_lesson
from services.rabbitmq import rabbitmq_service
from repositories.remote_data import get_quiz_data, get_quiz_attempts, get_analysis_history
from datetime import datetime, timezone

# Lazy init
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    return _llm



def analyze_session(
    conversation_history: str,
    lesson_id: Union[str, int],
    user_id: str = None
) -> dict:
    """
    Analyze learning session
    
    Args:
        conversation_history: Full conversation text
        lesson_id: Lesson ID
        
    Returns:
        dict with analysis and level assessment
    """
    # Get metadata
    metadata = DEFAULT_METADATA.copy()
    if lesson_id:
        lesson = get_lesson(lesson_id)
        if lesson:
            metadata["subject"] = lesson.get("subject", "Toán")
            metadata["grade"] = lesson.get("grade", 4)
            metadata["topic"] = lesson.get("title", "Bài học")
    
    # Get transcript
    transcript = get_context(metadata["topic"], k=10, lesson_id=lesson_id)
    
    # Get quiz content (Questions)
    quiz_data = get_quiz_data(lesson_id)
    
    # Get user quiz attempts (Results)
    # This provides the actual score and incorrect answers
    quiz_attempts = get_quiz_attempts(user_id, lesson_id) if user_id else None
    
    # Get previous analysis history
    history_logs = get_analysis_history(user_id, lesson_id) if user_id else []

    quiz_context = ""
    if quiz_attempts:
        # If we have real attempts, use them
        quiz_context += f"""
QUIZ RESULTS (Latest Attempt):
- Score: {quiz_attempts.get('score_percentage', 0):.1f}% ({quiz_attempts.get('correct_count', 0)}/{quiz_attempts.get('total_questions', 0)})
- Incorrect Answers:
"""
        for inc in quiz_attempts.get('incorrect_details', []):
            quiz_context += f"  * Question: {inc['question']}\n    Student Answer: {inc['user_answer']}\n    Correct Answer: {inc['correct_answer']}\n"
    elif quiz_data and "questions" in quiz_data:
        # Fallback to just questions if no attempt found
        quiz_context += "\nQUIZ CONTENT (What the student was tested on):\n"
        for q in quiz_data["questions"]:
            quiz_context += f"- {q.get('questionText')}\n"

    # Add History Context
    history_context = ""
    if history_logs:
        history_context = "\nPREVIOUS ANALYSIS HISTORY (Progress Tracking):\n"
        for log in history_logs:
            history_context += f"- {log.get('created_at')}: Level {log.get('level')} - {log.get('analysis_summary')}\n"


    # Format prompt
    prompt = format_prompt(
        SYSTEM_PROMPTS["analyzer"],
        conversation_history=conversation_history,
        subject=metadata["subject"],
        grade=metadata["grade"],
        topic=metadata["topic"]
    )
    
    # Inject contexts into prompt
    if quiz_context:
        prompt += f"\n\n{quiz_context}"
    if history_context:
        prompt += f"\n\n{history_context}"
    
    # Generate analysis
    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    analysis = response.content
    
    # Simple level assessment based on message count
    messages_count = conversation_history.count("\n") // 2
    
    # If the history is empty/short but analyzer is called, we assume 90% video completion (Passive Learner)
    # The Prompt will handle the textual feedback, but we need to force the "Level" tag.
    if messages_count >= 10:
        level = "Tốt"
        level_reason = "Học sinh tương tác tích cực với nhiều câu hỏi"
    elif messages_count >= 5:
        level = "Trung bình"
        level_reason = "Học sinh có tham gia nhưng chưa nhiều"
    elif messages_count < 5:
        # Passive Learners (Watched video but didn't chat)
        # User request: "Understanding is good, just needs practice"
        level = "Khá" 
        level_reason = "Đã hoàn thành 90% bài giảng và nắm vững lý thuyết cơ bản"
    else: 
        # Fallback
        level = "Cần cải thiện"
        level_reason = "Học sinh chưa tương tác đủ để đánh giá"
    
    # SAVE ANALYSIS LOG via RabbitMQ Event
    if user_id:
        try:
            log_payload = {
                "userId": user_id,
                "lessonId": lesson_id,
                "analysis": analysis,
                "level": level,
                "levelReason": level_reason,
                "createdAt": datetime.now(timezone.utc).isoformat()
            }
            rabbitmq_service.publish_event("SAVE_ANALYSIS_LOG", log_payload)
            print(f"📝 Analysis Log saved for user {user_id}")
        except Exception as e:
            print(f"❌ Failed to save analysis log: {e}")

    return {
        "analysis": analysis,
        "level": level,
        "level_reason": level_reason,
        "quiz_stats": quiz_attempts # Pass full attempts for UI
    }
