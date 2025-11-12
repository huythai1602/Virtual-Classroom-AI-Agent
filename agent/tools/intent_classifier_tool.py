"""
Intent Classifier Tool - Phân loại câu hỏi thuộc bài học nào
PHASE 3: Fallback cho low confidence cases
"""
import json
from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

# LLM cho classification - dùng GPT-4 cho độ chính xác cao
llm = ChatOpenAI(model="gpt-4", temperature=0)

# Curriculum Map - Mapping bài học với keywords
CURRICULUM_MAP = {
    "Bài 1: Ôn tập các số đến 100000": {
        "lesson_id": "bai_1_on_tap_cac_so",
        "keywords": [
            "đọc số", "viết số", "chữ số", "hàng", "giá trị vị trí",
            "hàng đơn vị", "hàng chục", "hàng trăm", "hàng nghìn", "hàng vạn",
            "số đến 100000", "100000", "100 nghìn"
        ]
    },
    "Bài 2: Ôn tập các phép tính trong phạm vi 100000": {
        "lesson_id": "bai_2_on_tap_cac_phep_tinh",
        "keywords": [
            "cộng", "trừ", "nhân", "chia", "phép tính",
            "tổng", "hiệu", "tích", "thương",
            "tính nhẩm", "đặt tính"
        ]
    },
    "Bài 3: Số chẵn số lẻ": {
        "lesson_id": "bai_3_so_chan_so_le",
        "keywords": [
            "số chẵn", "số lẻ", "chẵn", "lẻ",
            "chia hết cho 2", "dư", "phép chia"
        ]
    },
    "Bài về Phân số": {
        "lesson_id": "bai_phan_so",
        "keywords": [
            "phân số", "tử số", "mẫu số",
            "rút gọn", "so sánh phân số", "quy đồng",
            "phân số bằng nhau"
        ]
    },
    "Bài về Hình học": {
        "lesson_id": "bai_hinh_hoc",
        "keywords": [
            "hình", "chu vi", "diện tích",
            "hình chữ nhật", "hình vuông", "hình tam giác",
            "chiều dài", "chiều rộng", "cạnh"
        ]
    }
}

INTENT_CLASSIFIER_PROMPT = """Bạn là chuyên gia phân tích câu hỏi Toán lớp 4 của Việt Nam.

CHƯƠNG TRÌNH HỌC (CURRICULUM):
{curriculum}

CÂU HỎI CỦA HỌC SINH: {question}

NHIỆM VỤ:
1. Phân tích câu hỏi thuộc chủ đề/bài học nào trong chương trình
2. Xác định lesson_id phù hợp nhất
3. Đánh giá confidence (0.0-1.0)
4. Classification: IN-SCOPE hoặc OUT-OF-SCOPE

QUY TẮC PHÂN LOẠI:
✅ IN-SCOPE nếu:
   - Câu hỏi chứa các khái niệm toán học trong curriculum
   - Liên quan GIÁN TIẾP đến các chủ đề đã học (VD: "chữ số 6 thuộc hàng nào" → Bài 1)
   - Dùng thuật ngữ toán học lớp 4

❌ OUT-OF-SCOPE chỉ khi:
   - Hỏi về môn học KHÁC (Tiếng Anh, Lịch sử, Khoa học...)
   - Hỏi kiến thức NGOÀI chương trình lớp 4 (căn bậc hai, phương trình...)
   - Không liên quan gì đến toán học

VÍ DỤ:
- "Chữ số 6 trong 36547 thuộc hàng nào?" → IN-SCOPE (Bài 1), confidence: 0.95
- "Căn bậc hai là gì?" → OUT-OF-SCOPE, confidence: 0.95
- "What is a fraction?" → OUT-OF-SCOPE (Tiếng Anh), confidence: 1.0

Trả về JSON:
{{
    "topic": "tên bài học cụ thể",
    "lesson_id": "bai_x_..." hoặc null nếu OUT-OF-SCOPE,
    "classification": "IN-SCOPE" hoặc "OUT-OF-SCOPE",
    "confidence": 0.95,
    "reasoning": "giải thích ngắn gọn"
}}

CHỈ trả về JSON, không thêm text:"""


def classify_intent(query: str) -> Dict:
    """
    Phân loại intent của câu hỏi
    
    Args:
        query: Câu hỏi của học sinh
        
    Returns:
        dict với topic, lesson_id, classification, confidence, reasoning
    """
    # Format curriculum
    curriculum_lines = []
    for lesson, info in CURRICULUM_MAP.items():
        keywords_str = ", ".join(info["keywords"][:10])  # Lấy 10 keywords đầu
        curriculum_lines.append(f"- {lesson} (ID: {info['lesson_id']})")
        curriculum_lines.append(f"  Keywords: {keywords_str}...")
    
    curriculum_text = "\n".join(curriculum_lines)
    
    # Create prompt
    prompt = INTENT_CLASSIFIER_PROMPT.format(
        curriculum=curriculum_text,
        question=query
    )
    
    # Call LLM with JSON mode
    llm_json = ChatOpenAI(
        model="gpt-4",
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    messages = [
        SystemMessage(content="Bạn là chuyên gia phân loại câu hỏi toán học Tiểu học."),
        HumanMessage(content=prompt)
    ]
    
    try:
        response = llm_json.invoke(messages)
        result = json.loads(response.content)
        
        # Validate
        required_keys = ["topic", "lesson_id", "classification", "confidence", "reasoning"]
        for key in required_keys:
            if key not in result:
                result[key] = None if key != "confidence" else 0.5
        
        print(f"[INTENT CLASSIFIER] Query: {query[:50]}...")
        print(f"[INTENT CLASSIFIER] Result: {result['classification']} ({result['confidence']}) - {result['topic']}")
        
        return result
        
    except Exception as e:
        print(f"[ERROR] Intent classification failed: {e}")
        # Fallback: assume IN-SCOPE với low confidence
        return {
            "topic": "Unknown",
            "lesson_id": None,
            "classification": "IN-SCOPE",
            "confidence": 0.4,
            "reasoning": f"Classification error: {str(e)}"
        }


def should_use_intent_classifier(confidence: float) -> bool:
    """
    Quyết định có nên dùng intent classifier không
    
    Args:
        confidence: Confidence từ answer
        
    Returns:
        True nếu nên classify
    """
    # Chỉ dùng khi confidence thấp (< 0.7)
    return confidence < 0.7
