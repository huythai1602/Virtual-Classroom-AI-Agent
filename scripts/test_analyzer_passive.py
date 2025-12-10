
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.analyzer import analyze_session
from unittest.mock import MagicMock, patch

def test_passive_learner():
    print("Testing passive learner scenario (empty chat history)...")
    
    # Mock dependencies to avoid actual API calls and DB access
    with patch('tools.analyzer.get_lesson') as mock_get_lesson, \
         patch('tools.analyzer.get_context') as mock_get_context, \
         patch('tools.analyzer.get_llm') as mock_get_llm:
         
        # Setup mocks
        mock_get_lesson.return_value = {"subject": "Toán", "grade": 4, "title": "Phép cộng"}
        mock_get_context.return_value = "Nội dung bài học..."
        
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Analysis: Student watched video passively."
        mock_get_llm.return_value = mock_llm
        
        # Test case: Empty history
        conversation_history = ""
        result = analyze_session(conversation_history, lesson_id=1)
        
        print("\n--- Result ---")
        print(f"Level: {result['level']}")
        print(f"Reason: {result['level_reason']}")
        
        # Verification
        if result['level'] == "Cơ bản" and "Passive Learner" in result['level_reason']:
            print("\nSUCCESS: Passive learner correctly identified.")
        else:
            print(f"\nFAILURE: Expected Level 'Cơ bản', got '{result['level']}'")
            print(f"Reason: {result['level_reason']}")

if __name__ == "__main__":
    test_passive_learner()
