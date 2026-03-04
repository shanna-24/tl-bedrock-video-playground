"""Web search client for enriching analysis with external information.

This module provides a client for the Brave Search API, allowing Claude to
augment video analysis insights with current web information when needed.
"""

import logging
import ssl
from typing import List, Dict, Optional
import aiohttp
import certifi

logger = logging.getLogger(__name__)


class WebSearchClient:
    """Client for Brave Search API integration.
    
    This client provides web search capabilities to enrich video analysis
    with current information from the web. It's designed to be used by
    Claude during the aggregation stage to supplement video insights.
    
    Attributes:
        api_key: Brave Search API key
        base_url: Base URL for Brave Search API
    """
    
    def __init__(self, api_key: str):
        """Initialize the WebSearchClient.
        
        Args:
            api_key: Brave Search API key
        """
        self.api_key = api_key
        self.base_url = "https://api.search.brave.com/res/v1"
        logger.info("Initialized WebSearchClient")
    
    async def search(
        self,
        query: str,
        count: int = 5,
        freshness: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Execute a web search query.
        
        Args:
            query: Search query string
            count: Number of results to return (max 20)
            freshness: Optional freshness filter (e.g., "pd" for past day,
                      "pw" for past week, "pm" for past month, "py" for past year)
        
        Returns:
            List of search results, each containing:
                - title: Result title
                - url: Result URL
                - description: Result snippet/description
        
        Raises:
            Exception: If the API request fails
        """
        if not query or not query.strip():
            logger.warning("Empty search query provided")
            return []
        
        # Limit count to API maximum
        count = min(count, 20)
        
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }
        
        params = {
            "q": query,
            "count": count
        }
        
        if freshness:
            params["freshness"] = freshness
        
        try:
            logger.info(f"Executing web search: {query[:100]}... (count={count})")
            
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                async with session.get(
                    f"{self.base_url}/web/search",
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"Brave Search API error (status {response.status}): {error_text}"
                        )
                        return []
                    
                    data = await response.json()
                    
                    # Extract web results
                    web_results = data.get("web", {}).get("results", [])
                    
                    # Format results
                    formatted_results = []
                    for result in web_results[:count]:
                        formatted_results.append({
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "description": result.get("description", "")
                        })
                    
                    logger.info(f"Retrieved {len(formatted_results)} search results")
                    
                    return formatted_results
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error during web search: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during web search: {e}")
            return []
    
    def format_search_results(self, results: List[Dict[str, str]]) -> str:
        """Format search results as text for inclusion in prompts.
        
        Args:
            results: List of search result dictionaries
        
        Returns:
            Formatted string with search results
        """
        if not results:
            return "No web search results available."
        
        lines = ["Web Search Results:"]
        for i, result in enumerate(results, 1):
            lines.append(
                f"\n{i}. {result['title']}\n"
                f"   URL: {result['url']}\n"
                f"   {result['description']}"
            )
        
        return "\n".join(lines)
