"""
Level Assessment Tool - Đánh giá trình độ học sinh
"""


def assess_student_level_from_conversation(conversation_history: str, messages_count: int) -> dict:
    """
    Đánh giá level học sinh dựa trên conversation history (rule-based)
    Không gọi LLM - tiết kiệm token
    
    Args:
        conversation_history: Lịch sử hội thoại (text)
        messages_count: Số lượng messages trong conversation
        
    Returns:
        dict: {"level": "Beginner/Intermediate/Advanced", "reason": "..."}
    """
    # Đếm số câu hỏi của học sinh (ước lượng)
    user_questions = conversation_history.count("Học sinh:")
    
    # Kiểm tra từ khóa chủ động học sâu
    deep_keywords = ["giải thích", "chi tiết", "tại sao", "như thế nào", "ví dụ", "làm sao"]
    deep_count = sum(1 for keyword in deep_keywords if keyword in conversation_history.lower())
    
    # Đánh giá theo rules
    if user_questions < 3:
        level = "Beginner"
        reason = f"Học sinh mới hỏi {user_questions} câu, chưa thể hiện sự tích cực học hỏi"
    elif user_questions >= 7 or deep_count >= 3:
        level = "Advanced"
        reason = f"Học sinh đã hỏi {user_questions} câu, trong đó có {deep_count} câu hỏi sâu, thể hiện sự chủ động và ham học hỏi cao"
    else:
        level = "Intermediate"
        reason = f"Học sinh đã hỏi {user_questions} câu, thể hiện sự tích cực học hỏi ở mức trung bình"
    
    return {
        "level": level,
        "reason": reason
    }
