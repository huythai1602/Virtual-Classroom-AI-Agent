"""
Synthesis Tool - Combines internal RAG and external search results intelligently
Creates coherent answers that properly cite sources and maintain accuracy
"""
import os
from typing import Dict, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

load_dotenv()

# LLM for synthesis
llm = ChatOpenAI(model="gpt-4o", temperature=0)  # Use GPT-4 for better synthesis


SYNTHESIS_PROMPT = """
You are a patient elementary school teacher synthesizing information from multiple sources.

TASK: Create a coherent, accurate answer by combining information from internal lesson materials and external sources.

STUDENT QUESTION: {question}

LESSON METADATA:
- Subject: {subject}
- Grade: {grade}
- Topic: {topic}

INTERNAL LESSON CONTENT:
{internal_context}

EXTERNAL SEARCH RESULTS:
{external_context}

SYNTHESIS GUIDELINES:

1. PRIORITIZATION:
   - Internal lesson content is PRIMARY source (most authoritative for curriculum)
   - External sources supplement or clarify when internal is insufficient
   - Always cite which source information comes from

2. ACCURACY FIRST:
   - Only use information explicitly stated in sources
   - Do NOT make assumptions or add external knowledge
   - If conflicting information, prioritize internal lesson content
   - If both sources insufficient, acknowledge limitation

3. GRADE-APPROPRIATE LANGUAGE:
   - Write for grade {grade} comprehension level
   - Use simple, natural Vietnamese
   - Avoid overly technical terms unless in lesson

4. SOURCE CITATION:
   - Mention source naturally: "Theo bài học..." or "Theo thông tin tìm được..."
   - Be transparent about information origin
   - Example: "Trong bài học, cô thấy... Thêm vào đó, theo Wikipedia..."

5. RESPONSE STRUCTURE:
   - Start with direct answer to question
   - Provide explanation if needed
   - Add context from external sources if helpful
   - End with encouraging follow-up question

RESPONSE TONE:
- Warm, patient, encouraging ("cô" addressing "em")
- Natural conversation, not robotic
- Honest about limitations when applicable

OUTPUT: Natural Vietnamese answer (max 4-5 sentences for grade {grade})

Synthesize the answer:
"""


class SynthesisTool:
    """Combines internal and external information into coherent answers"""
    
    def __init__(self):
        self.llm = llm
    
    def synthesize(
        self,
        question: str,
        internal_context: str,
        external_context: str,
        subject: str = "Toán",
        grade: int = 4,
        topic: str = "Bài học"
    ) -> str:
        """
        Synthesize answer from multiple sources
        
        Args:
            question: Student's question
            internal_context: Content from lesson transcripts
            external_context: Content from external search
            subject: Current subject
            grade: Current grade level
            topic: Current lesson topic
            
        Returns:
            Synthesized answer in Vietnamese
        """
        try:
            # Format prompt
            prompt = SYNTHESIS_PROMPT.format(
                question=question,
                internal_context=internal_context if internal_context else "Không có thông tin từ bài học.",
                external_context=external_context if external_context else "Không có thông tin từ nguồn ngoài.",
                subject=subject,
                grade=grade,
                topic=topic
            )
            
            # Get synthesis
            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            
            return response.content
            
        except Exception as e:
            print(f"[ERROR] Synthesis failed: {e}")
            # Fallback: use internal context if available
            if internal_context and "Không tìm thấy" not in internal_context:
                return f"Dựa vào bài học: {internal_context[:500]}..."
            return "Xin lỗi em, cô không tìm thấy đủ thông tin để trả lời câu hỏi này."


# Global instance
_synthesizer = SynthesisTool()


@tool
def synthesize_answer(
    question: str,
    internal_context: str,
    external_context: str = "",
    subject: str = "Toán",
    grade: int = 4,
    topic: str = "Bài học"
) -> str:
    """
    Synthesize a coherent answer from internal lesson content and external search results.
    
    Args:
        question: Student's question
        internal_context: Content from lesson transcripts (RAG)
        external_context: Content from external search (Google/Wikipedia)
        subject: Current subject (default: Toán)
        grade: Current grade level (default: 4)
        topic: Current lesson topic (default: Bài học)
        
    Returns:
        Synthesized answer in natural Vietnamese with proper source citation
    """
    return _synthesizer.synthesize(
        question,
        internal_context,
        external_context,
        subject,
        grade,
        topic
    )


def create_hybrid_answer(
    question: str,
    internal_context: str,
    external_context: str,
    metadata: Dict = None
) -> str:
    """
    Helper function to create hybrid answer with optional metadata dict
    
    Args:
        question: Student's question
        internal_context: Internal RAG context
        external_context: External search context
        metadata: Optional dict with subject, grade, topic
        
    Returns:
        Synthesized answer
    """
    if metadata is None:
        metadata = {"subject": "Toán", "grade": 4, "topic": "Bài học"}
    
    return _synthesizer.synthesize(
        question,
        internal_context,
        external_context,
        subject=metadata.get("subject", "Toán"),
        grade=metadata.get("grade", 4),
        topic=metadata.get("topic", "Bài học")
    )
