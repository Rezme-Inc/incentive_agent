"""
Tavily Web Search Client wrapper
"""
from typing import List, Dict, Any, Optional
from langchain_community.tools.tavily_search import TavilySearchResults

from src.core.config import settings


class TavilyClient:
    """Wrapper for Tavily web search with retry logic"""

    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self._client: Optional[TavilySearchResults] = None

    @property
    def client(self) -> TavilySearchResults:
        """Lazy initialization of Tavily client"""
        if self._client is None:
            self._client = TavilySearchResults(
                max_results=self.max_results,
                api_key=settings.tavily_api_key
            )
        return self._client

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search the web using Tavily.

        Args:
            query: Search query string

        Returns:
            List of search results with url, title, content
        """
        try:
            results = await self.client.ainvoke(query)
            if isinstance(results, list):
                return results
            elif isinstance(results, str):
                return [{"content": results}]
            return []
        except Exception as e:
            print(f"Tavily search error: {e}")
            return []

    def search_sync(self, query: str) -> List[Dict[str, Any]]:
        """Synchronous version of search"""
        try:
            results = self.client.invoke(query)
            if isinstance(results, list):
                return results
            elif isinstance(results, str):
                return [{"content": results}]
            return []
        except Exception as e:
            print(f"Tavily search error: {e}")
            return []
