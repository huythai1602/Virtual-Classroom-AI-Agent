"""
Token Budget & Optimization System
"""

import tiktoken
from typing import List, Dict, Tuple
import json


class TokenBudget:
    """
    Manage token budgets and optimize context usage
    """
    
    # Model limits
    GPT4_LIMIT = 8192
    GPT35_LIMIT = 4096
    
    # Budget allocation
    MAX_INPUT = 4000
    MAX_OUTPUT = 1500
    SYSTEM_BUDGET = 500
    HISTORY_BUDGET = 800
    CONTEXT_BUDGET = 2700  # Remaining for retrieved context
    
    def __init__(self, model: str = "gpt-4"):
        self.encoding = tiktoken.encoding_for_model("gpt-4")
        self.model = model
        self.total_tokens = 0
        self.query_count = 0
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        try:
            return len(self.encoding.encode(text))
        except:
            # Fallback: rough estimate
            return len(text) // 4
    
    def truncate_to_budget(self, text: str, budget: int) -> str:
        """Truncate text to fit token budget"""
        tokens = self.encoding.encode(text)
        if len(tokens) <= budget:
            return text
        
        # Truncate and add ellipsis
        truncated = self.encoding.decode(tokens[:budget-10])
        return truncated + "\n...(nội dung bị cắt)"
    
    def optimize_chunks(
        self, 
        chunks: List[Dict], 
        budget: int = CONTEXT_BUDGET
    ) -> Tuple[List[Dict], int]:
        """
        Select and truncate chunks to fit budget
        
        Returns:
            (optimized_chunks, total_tokens)
        """
        optimized = []
        total_tokens = 0
        
        for chunk in chunks:
            text = chunk["content"]
            tokens = self.count_tokens(text)
            
            if total_tokens + tokens <= budget:
                optimized.append(chunk)
                total_tokens += tokens
            elif total_tokens < budget:
                # Partial chunk to fill remaining budget
                remaining = budget - total_tokens
                chunk["content"] = self.truncate_to_budget(text, remaining)
                optimized.append(chunk)
                total_tokens = budget
                break
            else:
                break
        
        return optimized, total_tokens
    
    def optimize_history(
        self, 
        messages: List[Dict],
        budget: int = HISTORY_BUDGET
    ) -> List[Dict]:
        """
        Optimize conversation history to fit budget
        Keep recent messages, summarize old ones
        """
        # Always keep last 3 messages
        recent = messages[-3:] if len(messages) >= 3 else messages
        
        recent_tokens = sum(self.count_tokens(str(m)) for m in recent)
        
        if recent_tokens <= budget:
            return recent
        
        # Truncate messages if needed
        optimized = []
        current_tokens = 0
        
        for msg in reversed(recent):
            msg_tokens = self.count_tokens(str(msg))
            if current_tokens + msg_tokens <= budget:
                optimized.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        return optimized if optimized else [recent[-1]]
    
    def adaptive_k(self, query: str, intent: str = "normal") -> int:
        """
        Determine optimal k based on query complexity
        
        Returns:
            k value (number of chunks to retrieve)
        """
        query_length = len(query)
        
        # Simple heuristic
        if intent == "normal":
            return 2  # Short answer
        elif query_length < 50:
            return 3  # Simple question
        elif query_length < 100:
            return 4  # Medium question
        else:
            return 5  # Complex question
    
    def compress_context(self, chunks: List[Dict]) -> List[Dict]:
        """
        Remove redundant information from chunks
        - Deduplicate similar content
        - Remove filler words
        """
        if not chunks:
            return chunks
        
        compressed = []
        seen_content = set()
        
        for chunk in chunks:
            content = chunk["content"]
            
            # Create fingerprint (first 100 + last 100 chars)
            fingerprint = content[:100] + content[-100:]
            
            if fingerprint not in seen_content:
                # Light compression: remove extra whitespace
                content = " ".join(content.split())
                chunk["content"] = content
                compressed.append(chunk)
                seen_content.add(fingerprint)
        
        return compressed
    
    def log_usage(self, input_tokens: int, output_tokens: int, cost: float):
        """Log token usage for monitoring"""
        self.total_tokens += input_tokens + output_tokens
        self.query_count += 1
        
        avg_tokens = self.total_tokens / self.query_count if self.query_count > 0 else 0
        
        print(f"📊 Token Usage:")
        print(f"   Input: {input_tokens}, Output: {output_tokens}")
        print(f"   Cost: ${cost:.5f}")
        print(f"   Total: {self.total_tokens} tokens across {self.query_count} queries")
        print(f"   Average: {avg_tokens:.0f} tokens/query")
    
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "gpt-4") -> float:
        """
        Estimate cost for OpenAI API call
        
        Prices (per 1K tokens):
        - GPT-4: $0.03 input, $0.06 output
        - GPT-3.5-turbo: $0.001 input, $0.002 output
        """
        prices = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002}
        }
        
        model_prices = prices.get(model, prices["gpt-4"])
        
        cost = (input_tokens / 1000 * model_prices["input"]) + \
               (output_tokens / 1000 * model_prices["output"])
        
        return cost


# Global instance
_budget_instance = None

def get_token_budget() -> TokenBudget:
    """Get or create global token budget instance"""
    global _budget_instance
    if _budget_instance is None:
        _budget_instance = TokenBudget()
    return _budget_instance
