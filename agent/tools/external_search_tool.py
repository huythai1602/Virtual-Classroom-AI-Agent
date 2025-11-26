"""
External Search Tool - Search external sources (Google/Wikipedia) when internal RAG insufficient
Part of Agentic RAG architecture for handling out-of-scope questions
"""
import os
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

# Google Custom Search API credentials
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")


class ExternalSearchTool:
    """Manages external search queries to Google and Wikipedia"""
    
    def __init__(self):
        self.google_api_key = GOOGLE_API_KEY
        self.google_cse_id = GOOGLE_CSE_ID
    
    def search_google(self, query: str, num_results: int = 3) -> List[Dict]:
        """
        Search Google Custom Search API
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of search results with title, snippet, link
        """
        if not self.google_api_key or not self.google_cse_id:
            print("[WARNING] Google API credentials not configured")
            return []
        
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key,
                "cx": self.google_cse_id,
                "q": query,
                "num": num_results,
                "lr": "lang_vi",  # Prioritize Vietnamese results
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "link": item.get("link", ""),
                    "source": "Google"
                })
            
            return results
            
        except Exception as e:
            print(f"[ERROR] Google search failed: {e}")
            return []
    
    def search_wikipedia(self, query: str, num_results: int = 2) -> List[Dict]:
        """
        Search Wikipedia API
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of Wikipedia results with title, snippet, link
        """
        try:
            # Wikipedia API endpoint
            url = "https://vi.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srlimit": num_results,
                "srprop": "snippet"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                snippet = item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
                page_id = item.get("pageid", "")
                
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "link": f"https://vi.wikipedia.org/?curid={page_id}",
                    "source": "Wikipedia"
                })
            
            return results
            
        except Exception as e:
            print(f"[ERROR] Wikipedia search failed: {e}")
            return []
    
    def search_combined(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search both Google and Wikipedia, combine and deduplicate results
        
        Args:
            query: Search query
            max_results: Maximum total results to return
            
        Returns:
            Combined list of search results
        """
        google_results = self.search_google(query, num_results=3)
        wiki_results = self.search_wikipedia(query, num_results=2)
        
        # Combine results
        all_results = google_results + wiki_results
        
        # Simple deduplication based on title similarity
        unique_results = []
        seen_titles = set()
        
        for result in all_results:
            title_lower = result["title"].lower()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique_results.append(result)
        
        return unique_results[:max_results]


# Global instance
_external_search = ExternalSearchTool()


@tool
def search_external_sources(query: str, max_results: int = 5) -> str:
    """
    Search external sources (Google + Wikipedia) for information not in lesson transcripts.
    Use this when internal RAG cannot answer the question.
    
    Args:
        query: Search query (preferably in Vietnamese for better results)
        max_results: Maximum number of results to return
        
    Returns:
        Formatted string with search results including titles, snippets, and sources
    """
    results = _external_search.search_combined(query, max_results=max_results)
    
    if not results:
        return "Không tìm thấy thông tin từ nguồn bên ngoài."
    
    # Format results
    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(
            f"[Kết quả {i} - {result['source']}]\n"
            f"Tiêu đề: {result['title']}\n"
            f"Nội dung: {result['snippet']}\n"
            f"Link: {result['link']}"
        )
    
    return "\n\n".join(formatted)


def get_external_context(query: str, max_results: int = 5) -> str:
    """
    Helper function to get external search context
    Directly uses ExternalSearchTool without going through @tool wrapper
    
    Args:
        query: Search query
        max_results: Maximum number of results
        
    Returns:
        Formatted search results
    """
    results = _external_search.search_combined(query, max_results=max_results)
    
    if not results:
        return "Không tìm thấy thông tin từ nguồn bên ngoài."
    
    # Format results
    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(
            f"[Kết quả {i} - {result['source']}]\n"
            f"Tiêu đề: {result['title']}\n"
            f"Nội dung: {result['snippet']}\n"
            f"Link: {result['link']}"
        )
    
    return "\n\n".join(formatted)
