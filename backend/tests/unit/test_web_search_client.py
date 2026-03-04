"""Unit tests for WebSearchClient.

Tests the Brave Search API integration for web search enrichment.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.web_search_client import WebSearchClient


class TestWebSearchClient:
    """Test suite for WebSearchClient."""
    
    def test_init(self):
        """Test WebSearchClient initialization."""
        client = WebSearchClient(api_key="test_key")
        assert client.api_key == "test_key"
        assert client.base_url == "https://api.search.brave.com/res/v1"
    
    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful web search."""
        client = WebSearchClient(api_key="test_key")
        
        # Mock response data
        mock_response_data = {
            "web": {
                "results": [
                    {
                        "title": "Test Result 1",
                        "url": "https://example.com/1",
                        "description": "Description 1"
                    },
                    {
                        "title": "Test Result 2",
                        "url": "https://example.com/2",
                        "description": "Description 2"
                    }
                ]
            }
        }
        
        # Mock aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)
        
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            results = await client.search("test query", count=5)
        
        assert len(results) == 2
        assert results[0]["title"] == "Test Result 1"
        assert results[0]["url"] == "https://example.com/1"
        assert results[0]["description"] == "Description 1"
    
    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """Test search with empty query."""
        client = WebSearchClient(api_key="test_key")
        results = await client.search("", count=5)
        assert results == []
    
    @pytest.mark.asyncio
    async def test_search_api_error(self):
        """Test search with API error."""
        client = WebSearchClient(api_key="test_key")
        
        # Mock error response
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            results = await client.search("test query", count=5)
        
        # Should return empty list on error
        assert results == []
    
    @pytest.mark.asyncio
    async def test_search_count_limit(self):
        """Test that search count is limited to 20."""
        client = WebSearchClient(api_key="test_key")
        
        mock_response_data = {"web": {"results": []}}
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)
        
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            await client.search("test query", count=100)
        
        # Verify count was limited to 20
        call_args = mock_session.get.call_args
        assert call_args[1]["params"]["count"] == 20
    
    def test_format_search_results(self):
        """Test formatting of search results."""
        client = WebSearchClient(api_key="test_key")
        
        results = [
            {
                "title": "Result 1",
                "url": "https://example.com/1",
                "description": "Description 1"
            },
            {
                "title": "Result 2",
                "url": "https://example.com/2",
                "description": "Description 2"
            }
        ]
        
        formatted = client.format_search_results(results)
        
        assert "Web Search Results:" in formatted
        assert "Result 1" in formatted
        assert "https://example.com/1" in formatted
        assert "Description 1" in formatted
        assert "Result 2" in formatted
    
    def test_format_search_results_empty(self):
        """Test formatting of empty search results."""
        client = WebSearchClient(api_key="test_key")
        formatted = client.format_search_results([])
        assert formatted == "No web search results available."
