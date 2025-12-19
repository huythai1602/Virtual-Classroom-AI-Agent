import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.analyzer import analyze_session

def test_analyzer_with_quiz():
    print("Testing Analyzer with Quiz Integration...")
    
    # Mock dependencies
    with patch('tools.analyzer.get_lesson') as mock_get_lesson, \
         patch('tools.analyzer.get_context') as mock_get_context, \
         patch('tools.analyzer.get_llm') as mock_get_llm, \
         patch('repositories.quiz.get_quiz_stats') as mock_get_quiz_stats:
         
        # Setup mocks
        mock_get_lesson.return_value = {"subject": "Toán", "grade": 4, "title": "Phân số"}
        mock_get_context.return_value = "Context content..."
        
        # Mock Quiz Stats
        mock_get_quiz_stats.return_value = {
            "total_questions": 10,
            "correct_count": 8,
            "score_percentage": 80.0,
            "incorrect_details": [
                {
                    "question": "1 + 1 = ?", 
                    "user_answer": "3", 
                    "correct_answer": "2",
                    "options": ["1", "2", "3", "4"]
                }
            ]
        }
        
        # Capture LLM prompt
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance
        mock_llm_instance.invoke.return_value.content = "Analysis Output"
        
        # Run Analysis
        result = analyze_session("User: Hello", lesson_id=1, user_id="user_123")
        
        # Verify
        print("\n--- Result ---")
        print(f"Analysis: {result['analysis']}")
        print(f"Quiz Stats: {result['quiz_stats']}")
        
        # Check if Prompt contained quiz info
        # The invoke call args: [HumanMessage(content='...')]
        call_args = mock_llm_instance.invoke.call_args
        if call_args:
            prompt_sent = call_args[0][0][0].content
            print("\n--- Prompt Verification ---")
            if "QUIZ RESULTS" in prompt_sent and "Score: 8/10" in prompt_sent:
                print("✅ Success: Quiz results injected into prompt.")
            else:
                print("❌ Failure: Quiz results NOT found in prompt.")
                print(f"Prompt snippet: {prompt_sent[:500]}...")
            
            if "1 + 1 = ?" in prompt_sent:
                 print("✅ Success: Incorrect details injected.")
            else:
                 print("❌ Failure: Incorrect details missing.")

if __name__ == "__main__":
    test_analyzer_with_quiz()
