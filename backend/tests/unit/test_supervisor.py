"""Unit tests for Supervisor component.

Tests the Supervisor's ability to determine query intent using Claude.
Validates: Requirements 1.1
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from orchestration.supervisor import Supervisor
from models.orchestration import AnalysisIntent
from exceptions import BedrockError


@pytest.fixture
def mock_bedrock_client():
    """Create a mock BedrockClient for testing."""
    mock_client = Mock()
    return mock_client


@pytest.fixture
def supervisor(mock_bedrock_client):
    """Create a Supervisor instance with mocked dependencies."""
    return Supervisor(
        bedrock=mock_bedrock_client,
        claude_model_id="anthropic.claude-3-5-sonnet-20241022-v2:0"
    )


class TestSupervisorInitialization:
    """Tests for Supervisor initialization."""
    
    def test_supervisor_initialization(self, mock_bedrock_client):
        """Test that Supervisor initializes correctly."""
        supervisor = Supervisor(
            bedrock=mock_bedrock_client,
            claude_model_id="anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        
        assert supervisor.bedrock == mock_bedrock_client
        assert supervisor.claude_model_id == "anthropic.claude-3-5-sonnet-20241022-v2:0"


class TestIntentDetermination:
    """Tests for intent determination functionality."""
    
    @pytest.mark.asyncio
    async def test_determine_intent_specific_query(self, supervisor, mock_bedrock_client):
        """Test intent determination for a specific query that needs search."""
        # Mock Claude response for a specific query
        claude_response = json.dumps({
            "needs_search": True,
            "analysis_type": "specific",
            "reasoning": "Query asks about specific objects (dogs) in the video"
        })
        
        mock_bedrock_client.invoke_claude.return_value = claude_response
        
        # Test
        intent = await supervisor.determine_intent("Show me all scenes with dogs")
        
        # Verify
        assert isinstance(intent, AnalysisIntent)
        assert intent.needs_search is True
        assert intent.analysis_type == "specific"
        assert "dogs" in intent.reasoning.lower() or "specific" in intent.reasoning.lower()
        
        # Verify Claude was called
        mock_bedrock_client.invoke_claude.assert_called_once()
        call_args = mock_bedrock_client.invoke_claude.call_args
        assert "Show me all scenes with dogs" in call_args[1]["prompt"]
    
    @pytest.mark.asyncio
    async def test_determine_intent_general_query(self, supervisor, mock_bedrock_client):
        """Test intent determination for a general query that doesn't need search."""
        # Mock Claude response for a general query
        claude_response = json.dumps({
            "needs_search": False,
            "analysis_type": "general",
            "reasoning": "Query asks for a general overview of the video content"
        })
        
        mock_bedrock_client.invoke_claude.return_value = claude_response
        
        # Test
        intent = await supervisor.determine_intent("What is this video about?")
        
        # Verify
        assert isinstance(intent, AnalysisIntent)
        assert intent.needs_search is False
        assert intent.analysis_type == "general"
        assert "general" in intent.reasoning.lower() or "overview" in intent.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_determine_intent_with_json_in_text(self, supervisor, mock_bedrock_client):
        """Test parsing when Claude includes extra text around JSON."""
        # Mock Claude response with extra text
        claude_response = """Here's my analysis:

{
    "needs_search": true,
    "analysis_type": "specific",
    "reasoning": "The query is looking for specific moments"
}

I hope this helps!"""
        
        mock_bedrock_client.invoke_claude.return_value = claude_response
        
        # Test
        intent = await supervisor.determine_intent("Find moments where people are laughing")
        
        # Verify - should extract JSON correctly
        assert isinstance(intent, AnalysisIntent)
        assert intent.needs_search is True
        assert intent.analysis_type == "specific"
    
    @pytest.mark.asyncio
    async def test_determine_intent_claude_parameters(self, supervisor, mock_bedrock_client):
        """Test that Claude is invoked with correct parameters."""
        claude_response = json.dumps({
            "needs_search": True,
            "analysis_type": "specific",
            "reasoning": "Test reasoning"
        })
        
        mock_bedrock_client.invoke_claude.return_value = claude_response
        
        # Test
        await supervisor.determine_intent("Test query")
        
        # Verify Claude invocation parameters
        call_args = mock_bedrock_client.invoke_claude.call_args
        assert call_args[1]["model_id"] == "anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert call_args[1]["temperature"] == 0.2
        assert call_args[1]["max_tokens"] == 1024


class TestPromptBuilding:
    """Tests for intent prompt building."""
    
    def test_build_intent_prompt_includes_query(self, supervisor):
        """Test that the prompt includes the user's query."""
        query = "Show me action scenes"
        prompt = supervisor._build_intent_prompt(query)
        
        assert query in prompt
        assert "Query:" in prompt
    
    def test_build_intent_prompt_includes_guidelines(self, supervisor):
        """Test that the prompt includes classification guidelines."""
        prompt = supervisor._build_intent_prompt("Test query")
        
        assert "needs_search" in prompt
        assert "analysis_type" in prompt
        assert "reasoning" in prompt
        assert "specific" in prompt
        assert "general" in prompt
    
    def test_build_intent_prompt_includes_examples(self, supervisor):
        """Test that the prompt includes examples."""
        prompt = supervisor._build_intent_prompt("Test query")
        
        # Should include example queries
        assert "dogs" in prompt.lower() or "scenes" in prompt.lower()
        assert "JSON" in prompt


class TestResponseParsing:
    """Tests for parsing Claude responses."""
    
    def test_parse_valid_json_response(self, supervisor):
        """Test parsing a valid JSON response."""
        response = json.dumps({
            "needs_search": True,
            "analysis_type": "specific",
            "reasoning": "Query is specific"
        })
        
        intent = supervisor._parse_intent_response(response)
        
        assert intent.needs_search is True
        assert intent.analysis_type == "specific"
        assert intent.reasoning == "Query is specific"
    
    def test_parse_response_with_false_needs_search(self, supervisor):
        """Test parsing response with needs_search=false."""
        response = json.dumps({
            "needs_search": False,
            "analysis_type": "general",
            "reasoning": "Query is general"
        })
        
        intent = supervisor._parse_intent_response(response)
        
        assert intent.needs_search is False
        assert intent.analysis_type == "general"
    
    def test_parse_response_missing_needs_search(self, supervisor):
        """Test error handling when needs_search is missing."""
        response = json.dumps({
            "analysis_type": "specific",
            "reasoning": "Test"
        })
        
        with pytest.raises(ValueError) as exc_info:
            supervisor._parse_intent_response(response)
        
        assert "needs_search" in str(exc_info.value)
    
    def test_parse_response_missing_analysis_type(self, supervisor):
        """Test error handling when analysis_type is missing."""
        response = json.dumps({
            "needs_search": True,
            "reasoning": "Test"
        })
        
        with pytest.raises(ValueError) as exc_info:
            supervisor._parse_intent_response(response)
        
        assert "analysis_type" in str(exc_info.value)
    
    def test_parse_response_missing_reasoning(self, supervisor):
        """Test error handling when reasoning is missing."""
        response = json.dumps({
            "needs_search": True,
            "analysis_type": "specific"
        })
        
        with pytest.raises(ValueError) as exc_info:
            supervisor._parse_intent_response(response)
        
        assert "reasoning" in str(exc_info.value)
    
    def test_parse_response_invalid_analysis_type(self, supervisor):
        """Test error handling for invalid analysis_type value."""
        response = json.dumps({
            "needs_search": True,
            "analysis_type": "invalid_type",
            "reasoning": "Test"
        })
        
        with pytest.raises(ValueError) as exc_info:
            supervisor._parse_intent_response(response)
        
        assert "Invalid analysis_type" in str(exc_info.value)
        assert "specific" in str(exc_info.value)
        assert "general" in str(exc_info.value)
    
    def test_parse_response_no_json(self, supervisor):
        """Test error handling when response contains no JSON."""
        response = "This is just plain text without any JSON"
        
        with pytest.raises(ValueError) as exc_info:
            supervisor._parse_intent_response(response)
        
        assert "No JSON object found" in str(exc_info.value)
    
    def test_parse_response_invalid_json(self, supervisor):
        """Test error handling for malformed JSON."""
        response = '{"needs_search": true, "analysis_type": "specific"'  # Missing closing brace
        
        with pytest.raises(ValueError) as exc_info:
            supervisor._parse_intent_response(response)
        
        assert "Invalid JSON" in str(exc_info.value) or "No JSON object found" in str(exc_info.value)
    
    def test_parse_response_with_whitespace(self, supervisor):
        """Test parsing response with leading/trailing whitespace."""
        response = """
        
        {
            "needs_search": true,
            "analysis_type": "specific",
            "reasoning": "Test reasoning"
        }
        
        """
        
        intent = supervisor._parse_intent_response(response)
        
        assert intent.needs_search is True
        assert intent.analysis_type == "specific"


class TestErrorHandling:
    """Tests for error handling in Supervisor."""
    
    @pytest.mark.asyncio
    async def test_determine_intent_claude_error(self, supervisor, mock_bedrock_client):
        """Test handling of Claude invocation errors."""
        # Mock Claude error
        mock_bedrock_client.invoke_claude.side_effect = BedrockError("API error")
        
        # Test - should propagate the error
        with pytest.raises(BedrockError):
            await supervisor.determine_intent("Test query")
    
    @pytest.mark.asyncio
    async def test_determine_intent_parsing_error(self, supervisor, mock_bedrock_client):
        """Test handling of response parsing errors."""
        # Mock invalid Claude response
        mock_bedrock_client.invoke_claude.return_value = "Invalid response"
        
        # Test - should raise ValueError
        with pytest.raises(ValueError):
            await supervisor.determine_intent("Test query")
    
    @pytest.mark.asyncio
    async def test_determine_intent_unexpected_error(self, supervisor, mock_bedrock_client):
        """Test handling of unexpected errors."""
        # Mock unexpected error
        mock_bedrock_client.invoke_claude.side_effect = RuntimeError("Unexpected error")
        
        # Test - should propagate the error
        with pytest.raises(RuntimeError):
            await supervisor.determine_intent("Test query")
