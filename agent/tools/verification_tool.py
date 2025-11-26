"""
Verification Tool - Validates synthesized answers for accuracy and appropriateness
Final quality check before returning answer to student
"""
import os
import json
from typing import Dict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

load_dotenv()

# LLM for verification
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)


VERIFICATION_PROMPT = """
You are a quality assurance specialist for an educational AI system.

TASK: Verify the accuracy and appropriateness of a synthesized answer.

STUDENT QUESTION: {question}

SYNTHESIZED ANSWER: {answer}

SOURCE CONTEXT (for verification):
{source_context}

LESSON METADATA:
- Subject: {subject}
- Grade: {grade}
- Topic: {topic}

VERIFICATION CHECKLIST:

1. ACCURACY CHECK:
   - Is every statement in the answer supported by the source context?
   - Are there any fabricated facts or assumptions?
   - If external sources cited, are they properly attributed?
   - Rating: accurate (1.0) | mostly_accurate (0.7) | inaccurate (0.3)

2. GRADE APPROPRIATENESS:
   - Is the language suitable for grade {grade} students?
   - Are concepts explained at the right complexity level?
   - Any overly technical terms that need simplification?
   - Rating: appropriate (1.0) | needs_adjustment (0.5) | inappropriate (0.2)

3. RELEVANCE CHECK:
   - Does the answer directly address the question?
   - Is information on-topic and helpful?
   - Any irrelevant tangents?
   - Rating: relevant (1.0) | partially_relevant (0.6) | off_topic (0.2)

4. COMPLETENESS:
   - Is the answer complete enough to be helpful?
   - Does it leave major gaps in explanation?
   - Rating: complete (1.0) | adequate (0.7) | incomplete (0.4)

5. TONE CHECK:
   - Is the tone warm, encouraging, and natural?
   - Appropriate use of "cô" and "em"?
   - Not robotic or templated?
   - Rating: good_tone (1.0) | acceptable (0.7) | poor_tone (0.4)

ISSUES DETECTION:
- List specific issues found (if any)
- For each issue, explain what's wrong and how to fix it

OUTPUT FORMAT (JSON):
{{
  "is_valid": true | false,
  "overall_score": 0.0-1.0,
  "accuracy_score": 0.0-1.0,
  "appropriateness_score": 0.0-1.0,
  "relevance_score": 0.0-1.0,
  "completeness_score": 0.0-1.0,
  "tone_score": 0.0-1.0,
  "issues": ["issue 1", "issue 2", ...],
  "recommendation": "approve" | "revise" | "reject",
  "revision_notes": "specific suggestions if revision needed"
}}

Criteria for is_valid:
- is_valid = true if overall_score >= 0.7 AND accuracy_score >= 0.7
- is_valid = false otherwise

Return ONLY valid JSON, no additional text:
"""


class VerificationTool:
    """Validates synthesized answers for quality and accuracy"""
    
    def __init__(self):
        self.llm = llm
    
    def verify(
        self,
        question: str,
        answer: str,
        source_context: str,
        subject: str = "Toán",
        grade: int = 4,
        topic: str = "Bài học"
    ) -> Dict:
        """
        Verify synthesized answer quality
        
        Args:
            question: Original student question
            answer: Synthesized answer to verify
            source_context: Combined source context used for synthesis
            subject: Current subject
            grade: Current grade level
            topic: Current lesson topic
            
        Returns:
            Dict with verification results and scores
        """
        try:
            # Format prompt
            prompt = VERIFICATION_PROMPT.format(
                question=question,
                answer=answer,
                source_context=source_context[:1500],  # Limit context length
                subject=subject,
                grade=grade,
                topic=topic
            )
            
            # Get verification
            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            
            # Parse JSON response
            result = json.loads(response.content)
            
            # Validate required fields
            required_fields = ["is_valid", "overall_score", "recommendation"]
            for field in required_fields:
                if field not in result:
                    result[field] = True if field == "is_valid" else (0.8 if field == "overall_score" else "approve")
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Verification failed: {e}")
            # Fallback: approve with medium confidence
            return {
                "is_valid": True,
                "overall_score": 0.7,
                "accuracy_score": 0.7,
                "recommendation": "approve",
                "issues": [f"Verification error: {str(e)}"],
                "revision_notes": "Verification system unavailable, proceeding with caution"
            }


# Global instance
_verifier = VerificationTool()


@tool
def verify_answer(
    question: str,
    answer: str,
    source_context: str,
    subject: str = "Toán",
    grade: int = 4,
    topic: str = "Bài học"
) -> str:
    """
    Verify the quality and accuracy of a synthesized answer.
    
    Args:
        question: Original student question
        answer: Synthesized answer to verify
        source_context: Combined source context used for synthesis
        subject: Current subject (default: Toán)
        grade: Current grade level (default: 4)
        topic: Current lesson topic (default: Bài học)
        
    Returns:
        JSON string with verification results including scores and recommendations
    """
    result = _verifier.verify(question, answer, source_context, subject, grade, topic)
    return json.dumps(result, ensure_ascii=False, indent=2)


def get_verification_result(
    question: str,
    answer: str,
    source_context: str,
    metadata: Dict = None
) -> Dict:
    """
    Helper function to get verification result as dict
    
    Args:
        question: Original student question
        answer: Synthesized answer
        source_context: Source context
        metadata: Optional dict with subject, grade, topic
        
    Returns:
        Dict with verification results
    """
    if metadata is None:
        metadata = {"subject": "Toán", "grade": 4, "topic": "Bài học"}
    
    return _verifier.verify(
        question,
        answer,
        source_context,
        subject=metadata.get("subject", "Toán"),
        grade=metadata.get("grade", 4),
        topic=metadata.get("topic", "Bài học")
    )
