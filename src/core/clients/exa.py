"""
Exa Web Search Client wrapper
"""
from typing import List, Dict, Any, Optional
from exa_py import Exa

from src.core.config import settings


class ExaClient:
    """Wrapper for Exa web search"""

    def __init__(self, num_results: int = 5, max_characters: int = 10000):
        self.num_results = num_results
        self.max_characters = max_characters
        self._client: Optional[Exa] = None

    @property
    def client(self) -> Exa:
        """Lazy initialization of Exa client"""
        if self._client is None:
            self._client = Exa(api_key=settings.exa_api_key)
        return self._client

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search the web using Exa.

        Args:
            query: Search query string

        Returns:
            List of search results with url, title, content
        """
        try:
            response = self.client.search(
                query=query,
                type="auto",
                num_results=self.num_results,
                contents={"text": {"max_characters": self.max_characters}},
            )
            return [
                {
                    "url": r.url,
                    "title": r.title or "",
                    "content": r.text or "",
                }
                for r in response.results
            ]
        except Exception as e:
            print(f"Exa search error: {e}")
            return []

    def search_sync(self, query: str) -> List[Dict[str, Any]]:
        """Synchronous version of search"""
        try:
            response = self.client.search(
                query=query,
                type="auto",
                num_results=self.num_results,
                contents={"text": {"max_characters": self.max_characters}},
            )
            return [
                {
                    "url": r.url,
                    "title": r.title or "",
                    "content": r.text or "",
                }
                for r in response.results
            ]
        except Exception as e:
            print(f"Exa search error: {e}")
            return []
