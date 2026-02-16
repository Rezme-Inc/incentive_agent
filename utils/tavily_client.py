"""
Web search client - uses Exa API (migrated from Tavily).

Function names kept as tavily_search/tavily_extract for backwards compatibility
with legacy pipeline callers (agents/*.py, utils/golden_tavily.py).
"""

import os
from typing import List, Dict, Any

from dotenv import load_dotenv
from exa_py import Exa

load_dotenv()

_api_key = os.getenv("EXA_API_KEY")

if not _api_key:
    raise RuntimeError("EXA_API_KEY not found in environment (.env). Set it before using web search.")

_client = Exa(api_key=_api_key)


def tavily_search(
    query: str,
    depth: str = "basic",
    max_results: int = 5,
    include_raw_content: bool = False,
) -> Dict[str, Any]:
    """Run a web search using Exa.

    Args:
        query: Natural language search query
        depth: Ignored (kept for backwards compat). Exa uses type="auto".
        max_results: Max number of results to return
        include_raw_content: If True, request more text content per result

    Returns:
        Dict with "results" key containing list of {url, title, content} dicts.
        Same shape as the old Tavily response so callers don't break.
    """
    max_chars = 20000 if include_raw_content else 10000
    response = _client.search(
        query=query,
        type="auto",
        num_results=max_results,
        contents={"text": {"max_characters": max_chars}},
    )
    return {
        "results": [
            {
                "url": r.url,
                "title": r.title or "",
                "content": r.text or "",
            }
            for r in response.results
        ]
    }


def tavily_extract(urls: List[str], depth: str = "basic") -> Dict[str, Any]:
    """Extract content from URLs using Exa's contents endpoint.

    Args:
        urls: List of URLs to extract from
        depth: Ignored (kept for backwards compat)

    Returns:
        Dict with "results" key containing extracted content.
    """
    response = _client.get_contents(
        urls=urls,
        text={"max_characters": 20000},
    )
    return {
        "results": [
            {
                "url": r.url,
                "title": r.title or "",
                "content": r.text or "",
            }
            for r in response.results
        ]
    }
