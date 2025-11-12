"""
Validator tool - Tự kiểm tra câu trả lời để giảm hallucination
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

# LLM cho validation (dùng GPT-4 để chính xác hơn)
validator_llm = ChatOpenAI(model="gpt-4", temperature=0)

VALIDATION_PROMPT = """Bạn là chuyên gia kiểm tra độ chính xác của câu trả lời giáo dục.

NGUYÊN TẮC KIỂM TRA:
1. Câu trả lời phải DỰA HOÀN TOÀN vào thông tin từ bài học
2. KHÔNG được bịa đặt hoặc thêm thông tin không có trong bài
3. KHÔNG được suy đoán nếu không chắc chắn
4. Nếu thông tin không đủ, phải thừa nhận rõ ràng

BÀI HỌC (NGUỒN CHÂN LÝ):
{context}

CÂU HỎI:
{question}

CÂU TRẢ LỜI CẦN KIỂM TRA:
{answer}

HÃY PHÂN TÍCH:
1. Câu trả lời có dựa trên bài học không?
2. Có thông tin nào bị bịa đặt/suy đoán không?
3. Có thông tin nào thiếu chính xác không?
4. Câu trả lời có phù hợp với lớp 4 không?

Trả về JSON với format:
{{
  "is_valid": true/false,
  "confidence": 0-100,
  "issues": ["vấn đề 1", "vấn đề 2", ...],
  "suggestions": "gợi ý sửa câu trả lời (nếu có)",
  "corrected_answer": "câu trả lời đã sửa (nếu cần)"
}}

Chỉ trả về JSON, không thêm text:"""


def validate_answer(question: str, answer: str, context: str) -> dict:
    """
    Tự động kiểm tra câu trả lời để phát hiện hallucination
    
    Args:
        question: Câu hỏi gốc
        answer: Câu trả lời cần kiểm tra
        context: Ngữ cảnh từ bài học
        
    Returns:
        dict với is_valid, confidence, issues, suggestions, corrected_answer
    """
    try:
        prompt = VALIDATION_PROMPT.format(
            context=context,
            question=question,
            answer=answer
        )
        
        messages = [
            SystemMessage(content="Bạn là chuyên gia validation, luôn trả về JSON hợp lệ."),
            HumanMessage(content=prompt)
        ]
        
        # Gọi LLM với JSON mode
        llm_json = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
        
        response = llm_json.invoke(messages)
        
        # Parse JSON
        import json
        result = json.loads(response.content)
        
        # Đảm bảo có đủ fields
        if "is_valid" not in result:
            result["is_valid"] = True
        if "confidence" not in result:
            result["confidence"] = 70
        if "issues" not in result:
            result["issues"] = []
        if "suggestions" not in result:
            result["suggestions"] = ""
        if "corrected_answer" not in result:
            result["corrected_answer"] = answer
            
        return result
        
    except Exception as e:
        print(f"Lỗi validation: {e}")
        # Fallback: chấp nhận câu trả lời
        return {
            "is_valid": True,
            "confidence": 50,
            "issues": [f"Không thể validate: {str(e)}"],
            "suggestions": "",
            "corrected_answer": answer
        }


def should_use_validation(intent: str = "normal") -> bool:
    """
    Quyết định có nên dùng validation không (để tiết kiệm cost)
    
    Args:
        intent: normal hoặc deep
        
    Returns:
        bool: True nếu nên validate
    """
    # Chỉ validate cho deep mode (yêu cầu độ chính xác cao)
    # Normal mode đã được optimize với prompt tốt
    return intent == "deep"
