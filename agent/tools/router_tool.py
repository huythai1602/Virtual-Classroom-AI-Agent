"""
Router Tool - Intelligent routing between internal RAG and external search
Decides whether to use lesson transcripts or external sources based on query analysis
"""
import os
from typing import Dict, Literal
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
import json

load_dotenv()

# LLM for routing decisions
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)


ROUTER_PROMPT = """
You are an intelligent query router for an educational AI assistant.

TASK: Analyze the student's question and determine the best information source.

STUDENT QUESTION: {question}

LESSON METADATA:
- Subject: {subject}
- Grade: {grade}
- Current Topic: {topic}

INTERNAL RAG PREVIEW (Top 3 chunks):
{rag_preview}

ROUTING DECISION FRAMEWORK:

1. SUBJECT RELEVANCE CHECK (Most Important):
   - Is the question about {subject} for grade {grade}?
   - Does it relate to the lesson topic: {topic}?
   - If NO (completely different subject) → Route "out_of_scope"
   - If YES → Continue to step 2

2. ANALYZE QUESTION TYPE:
   a) PRACTICAL APPLICATION: "Số 6 trong 36451 thuộc hàng nào?"
      - Question asks to APPLY theory to specific example
      - Transcript contains GENERAL theory/method
      - Does NOT need exact example in transcript
      
   b) DEEP WHY/HOW: "Tại sao phải xác định từ phải sang trái?"
      - Question asks for underlying reasons/mechanisms
      - Transcript may not explain the "why" behind rules
      - Needs deeper conceptual knowledge
      
   c) OUT-OF-SCOPE: "Cho em hỏi về lịch sử Việt Nam"
      - Completely different subject from current lesson
      - Should politely decline

3. EVALUATE RAG CONTENT:
   - Does RAG contain THEORY/METHOD that can answer the question?
   - For application questions: Theory presence = sufficient
   - For deep questions: Check if "why/reason" is explained

4. ROUTING RULES:

   Route to "out_of_scope" if:
   - Question about different subject (not {subject})
   - Completely unrelated to {topic}
   - Example: asking about history in math class
   → System will politely decline WITHOUT external search
   
   Route to "internal" if:
   - Question about {subject} AND related to {topic}
   - RAG contains relevant theory/method
   - Can answer by APPLYING theory (even if exact example not in transcript)
   - Practical application questions where theory exists
   
   Route to "hybrid" if:
   - Question about {subject} AND related to {topic}
   - But asks for deep WHY/HOW beyond transcript
   - RAG has theory but missing deeper explanation
   - Needs external knowledge to supplement lesson content
   
   CRITICAL: 
   - "out_of_scope" = Different subject → Decline politely
   - "internal" = Same subject + Theory exists → Apply theory
   - "hybrid" = Same subject + Need deeper explanation → Search + Synthesize

OUTPUT FORMAT (JSON):
{{
  "route": "out_of_scope" | "internal" | "hybrid",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation of routing decision"
}}

Route options:
- "out_of_scope": Different subject, will decline politely
- "internal": Same subject, apply theory from transcript
- "hybrid": Same subject, need external knowledge for deep understanding

Return ONLY valid JSON, no additional text:
"""


class RouterTool:
    """Intelligent routing between internal and external search"""
    
    def __init__(self):
        self.llm = llm
    
    def route_query(
        self,
        question: str,
        rag_preview: str,
        subject: str = "Toán",
        grade: int = 4,
        topic: str = "Bài học"
    ) -> Dict:
        """
        Route query to appropriate information source
        
        Args:
            question: Student's question
            rag_preview: Preview of top RAG results with similarity scores
            subject: Current subject
            grade: Current grade level
            topic: Current lesson topic
            
        Returns:
            Dict with route, confidence, and reasoning
        """
        try:
            # Format prompt
            prompt = ROUTER_PROMPT.format(
                question=question,
                subject=subject,
                grade=grade,
                topic=topic,
                rag_preview=rag_preview
            )
            
            # Get routing decision
            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            
            # Parse JSON response
            result = json.loads(response.content)
            
            # Validate fields
            if "route" not in result or result["route"] not in ["internal", "external", "hybrid"]:
                result["route"] = "internal"  # Default fallback
            if "confidence" not in result:
                result["confidence"] = 0.7
            if "reasoning" not in result:
                result["reasoning"] = "Default routing"
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Routing failed: {e}")
            # Fallback: default to internal with low confidence
            return {
                "route": "internal",
                "confidence": 0.5,
                "reasoning": "Routing error, defaulting to internal RAG"
            }


# Global instance
_router = RouterTool()


@tool
def route_question(
    question: str,
    rag_preview: str,
    subject: str = "Toán",
    grade: int = 4,
    topic: str = "Bài học"
) -> str:
    """
    Intelligently route a question to the best information source.
    
    Args:
        question: Student's question
        rag_preview: Preview of internal RAG results with similarity scores
        subject: Current subject (default: Toán)
        grade: Current grade level (default: 4)
        topic: Current lesson topic (default: Bài học)
        
    Returns:
        JSON string with routing decision: {"route": "internal|external|hybrid", "confidence": 0-1, "reasoning": "..."}
    """
    result = _router.route_query(question, rag_preview, subject, grade, topic)
    return json.dumps(result, ensure_ascii=False, indent=2)


def get_route_decision(
    question: str,
    rag_preview: str,
    subject: str = "Toán",
    grade: int = 4,
    topic: str = "Bài học"
) -> Dict:
    """
    Helper function to get routing decision as dict
    
    Args:
        question: Student's question
        rag_preview: Preview of internal RAG results
        subject: Current subject
        grade: Current grade level
        topic: Current lesson topic
        
    Returns:
        Dict with route, confidence, and reasoning
    """
    return _router.route_query(question, rag_preview, subject, grade, topic)
