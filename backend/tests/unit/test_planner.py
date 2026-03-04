"""Unit tests for Planner component.

Tests the Planner's ability to create execution plans using Claude.
Validates: Requirements 1.2, 2.1, 3.1
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from orchestration.planner import Planner
from models.orchestration import AnalysisIntent, ExecutionPlan
from exceptions import BedrockError


@pytest.fixture
def mock_bedrock_client():
    """Create a mock BedrockClient for testing."""
    mock_client = Mock()
    return mock_client


@pytest.fixture
def planner(mock_bedrock_client):
    """Create a Planner instance with mocked dependencies."""
    return Planner(
        bedrock=mock_bedrock_client,
        claude_model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        max_segments_limit=50
    )


@pytest.fixture
def search_intent():
    """Create an AnalysisIntent that requires search."""
    return AnalysisIntent(
        needs_search=True,
        analysis_type="specific",
        reasoning="Query asks about specific content"
    )


@pytest.fixture
def direct_intent():
    """Create an AnalysisIntent that doesn't require search."""
    return AnalysisIntent(
        needs_search=False,
        analysis_type="general",
        reasoning="Query asks for general overview"
    )


class TestPlannerInitialization:
    """Tests for Planner initialization."""
    
    def test_planner_initialization(self, mock_bedrock_client):
        """Test that Planner initializes correctly."""
        planner = Planner(
            bedrock=mock_bedrock_client,
            claude_model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            max_segments_limit=50
        )
        
        assert planner.bedrock == mock_bedrock_client
        assert planner.claude_model_id == "anthropic.claude-3-5-sonnet-20241022-v2:0"


class TestExecutionPlanCreation:
    """Tests for execution plan creation."""
    
    @pytest.mark.asyncio
    async def test_create_execution_plan_with_search(
        self, planner, mock_bedrock_client, search_intent
    ):
        """Test creating execution plan for query that needs search."""
        # Mock Claude response for search-based planning
        claude_response = json.dumps({
            "search_queries": ["dogs", "canine animals"],
            "analysis_prompts": ["Describe the dogs and their activities in this scene"],
            "max_segments": 10,
            "parallel_execution": True
        })
        
        mock_bedrock_client.invoke_claude.return_value = claude_response
        
        # Test
        plan = await planner.create_execution_plan(
            query="Show me all scenes with dogs",
            intent=search_intent,
            video_count=5
        )
        
        # Verify
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.search_queries) == 2
        assert "dogs" in plan.search_queries
        assert len(plan.analysis_prompts) == 1
        assert plan.max_segments == 10
        assert plan.parallel_execution is True
        
        # Verify Claude was called
        mock_bedrock_client.invoke_claude.assert_called_once()
        call_args = mock_bedrock_client.invoke_claude.call_args
        assert "Show me all scenes with dogs" in call_args[1]["prompt"]
        assert "5 videos" in call_args[1]["prompt"]
    
    @pytest.mark.asyncio
    async def test_create_execution_plan_without_search(
        self, planner, mock_bedrock_client, direct_intent
    ):
        """Test creating execution plan for query that doesn't need search."""
        # Mock Claude response for direct analysis planning
        claude_response = json.dumps({
            "search_queries": [],
            "analysis_prompts": ["Provide a comprehensive summary of the main themes"],
            "max_segments": 5,
            "parallel_execution": True
        })
        
        mock_bedrock_client.invoke_claude.return_value = claude_response
        
        # Test
        plan = await planner.create_execution_plan(
            query="What is this video about?",
            intent=direct_intent,
            video_count=10
        )
        
        # Verify
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.search_queries) == 0
        assert len(plan.analysis_prompts) == 1
        assert plan.max_segments == 5
        assert plan.parallel_execution is True
    
    @pytest.mark.asyncio
    async def test_create_execution_plan_multiple_prompts(
        self, planner, mock_bedrock_client, search_intent
    ):
        """Test creating execution plan with multiple analysis prompts."""
        # Mock Claude response with multiple prompts
        claude_response = json.dumps({
            "search_queries": ["action scenes", "fight sequences"],
            "analysis_prompts": [
                "Describe the action sequences",
                "Identify the participants in the action"
            ],
            "max_segments": 12,
            "parallel_execution": True
        })
        
        mock_bedrock_client.invoke_claude.return_value = claude_response
        
        # Test
        plan = await planner.create_execution_plan(
            query="Find all action scenes",
            intent=search_intent,
            video_count=8
        )
        
        # Verify
        assert len(plan.search_queries) == 2
        assert len(plan.analysis_prompts) == 2
        assert plan.max_segments == 12
    
    @pytest.mark.asyncio
    async def test_create_execution_plan_claude_parameters(
        self, planner, mock_bedrock_client, search_intent
    ):
        """Test that Claude is invoked with correct parameters."""
        claude_response = json.dumps({
            "search_queries": ["test"],
            "analysis_prompts": ["test prompt"],
            "max_segments": 10,
            "parallel_execution": True
        })
        
        mock_bedrock_client.invoke_claude.return_value = claude_response
        
        # Test
        await planner.create_execution_plan(
            query="Test query",
            intent=search_intent,
            video_count=5
        )
        
        # Verify Claude invocation parameters
        call_args = mock_bedrock_client.invoke_claude.call_args
        assert call_args[1]["model_id"] == "anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert call_args[1]["temperature"] == 0.2
        assert call_args[1]["max_tokens"] == 2048


class TestSearchBasedPlanning:
    """Tests for search-based planning."""
    
    @pytest.mark.asyncio
    async def test_plan_search_based_analysis(
        self, planner, mock_bedrock_client
    ):
        """Test search-based planning method."""
        claude_response = json.dumps({
            "search_queries": ["people laughing", "happy moments"],
            "analysis_prompts": ["Describe the emotions and interactions"],
            "max_segments": 8,
            "parallel_execution": True
        })
        
        mock_bedrock_client.invoke_claude.return_value = claude_response
        
        # Test
        plan = await planner._plan_search_based_analysis(
            query="Find moments where people are laughing",
            video_count=6
        )
        
        # Verify
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.search_queries) > 0
        assert "people laughing" in plan.search_queries or "happy moments" in plan.search_queries


class TestDirectAnalysisPlanning:
    """Tests for direct analysis planning."""
    
    @pytest.mark.asyncio
    async def test_plan_direct_analysis(
        self, planner, mock_bedrock_client
    ):
        """Test direct analysis planning method."""
        claude_response = json.dumps({
            "search_queries": [],
            "analysis_prompts": ["Summarize the main themes and topics"],
            "max_segments": 5,
            "parallel_execution": True
        })
        
        mock_bedrock_client.invoke_claude.return_value = claude_response
        
        # Test
        plan = await planner._plan_direct_analysis(
            query="Summarize the main themes",
            video_count=10
        )
        
        # Verify
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.search_queries) == 0
        assert len(plan.analysis_prompts) > 0


class TestPromptBuilding:
    """Tests for prompt building."""
    
    def test_build_search_planning_prompt_includes_query(self, planner):
        """Test that search planning prompt includes the query."""
        query = "Find action scenes"
        prompt = planner._build_search_planning_prompt(query, 5)
        
        assert query in prompt
        assert "Query:" in prompt
    
    def test_build_search_planning_prompt_includes_video_count(self, planner):
        """Test that search planning prompt includes video count."""
        prompt = planner._build_search_planning_prompt("Test query", 10)
        
        assert "10 videos" in prompt
    
    def test_build_search_planning_prompt_includes_guidelines(self, planner):
        """Test that search planning prompt includes guidelines."""
        prompt = planner._build_search_planning_prompt("Test query", 5)
        
        assert "search_queries" in prompt
        assert "analysis_prompts" in prompt
        assert "max_segments" in prompt
        assert "parallel_execution" in prompt
        assert "semantic" in prompt.lower()
    
    def test_build_direct_planning_prompt_includes_query(self, planner):
        """Test that direct planning prompt includes the query."""
        query = "Summarize the video"
        prompt = planner._build_direct_planning_prompt(query, 8)
        
        assert query in prompt
        assert "Query:" in prompt
    
    def test_build_direct_planning_prompt_includes_video_count(self, planner):
        """Test that direct planning prompt includes video count."""
        prompt = planner._build_direct_planning_prompt("Test query", 12)
        
        assert "12 videos" in prompt
    
    def test_build_direct_planning_prompt_no_search(self, planner):
        """Test that direct planning prompt indicates no search."""
        prompt = planner._build_direct_planning_prompt("Test query", 5)
        
        assert "no search" in prompt.lower() or "direct analysis" in prompt.lower()
        assert "empty list" in prompt.lower() or "[]" in prompt


class TestResponseParsing:
    """Tests for parsing Claude responses."""
    
    def test_parse_valid_execution_plan(self, planner):
        """Test parsing a valid execution plan response."""
        response = json.dumps({
            "search_queries": ["query1", "query2"],
            "analysis_prompts": ["prompt1"],
            "max_segments": 10,
            "parallel_execution": True
        })
        
        plan = planner._parse_execution_plan(response)
        
        assert isinstance(plan, ExecutionPlan)
        assert plan.search_queries == ["query1", "query2"]
        assert plan.analysis_prompts == ["prompt1"]
        assert plan.max_segments == 10
        assert plan.parallel_execution is True
    
    def test_parse_plan_with_empty_search_queries(self, planner):
        """Test parsing plan with empty search queries (direct analysis)."""
        response = json.dumps({
            "search_queries": [],
            "analysis_prompts": ["prompt1"],
            "max_segments": 5,
            "parallel_execution": True
        })
        
        plan = planner._parse_execution_plan(response)
        
        assert len(plan.search_queries) == 0
        assert len(plan.analysis_prompts) == 1
    
    def test_parse_plan_with_false_parallel_execution(self, planner):
        """Test parsing plan with parallel_execution=false."""
        response = json.dumps({
            "search_queries": ["query1"],
            "analysis_prompts": ["prompt1"],
            "max_segments": 10,
            "parallel_execution": False
        })
        
        plan = planner._parse_execution_plan(response)
        
        assert plan.parallel_execution is False
    
    def test_parse_plan_with_json_in_text(self, planner):
        """Test parsing when Claude includes extra text around JSON."""
        response = """Here's the execution plan:

{
    "search_queries": ["query1"],
    "analysis_prompts": ["prompt1"],
    "max_segments": 10,
    "parallel_execution": true
}

This should work well!"""
        
        plan = planner._parse_execution_plan(response)
        
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.search_queries) == 1
    
    def test_parse_plan_missing_search_queries(self, planner):
        """Test error handling when search_queries is missing."""
        response = json.dumps({
            "analysis_prompts": ["prompt1"],
            "max_segments": 10,
            "parallel_execution": True
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "search_queries" in str(exc_info.value)
    
    def test_parse_plan_missing_analysis_prompts(self, planner):
        """Test error handling when analysis_prompts is missing."""
        response = json.dumps({
            "search_queries": ["query1"],
            "max_segments": 10,
            "parallel_execution": True
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "analysis_prompts" in str(exc_info.value)
    
    def test_parse_plan_missing_max_segments(self, planner):
        """Test error handling when max_segments is missing."""
        response = json.dumps({
            "search_queries": ["query1"],
            "analysis_prompts": ["prompt1"],
            "parallel_execution": True
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "max_segments" in str(exc_info.value)
    
    def test_parse_plan_missing_parallel_execution(self, planner):
        """Test error handling when parallel_execution is missing."""
        response = json.dumps({
            "search_queries": ["query1"],
            "analysis_prompts": ["prompt1"],
            "max_segments": 10
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "parallel_execution" in str(exc_info.value)
    
    def test_parse_plan_search_queries_not_list(self, planner):
        """Test error handling when search_queries is not a list."""
        response = json.dumps({
            "search_queries": "not a list",
            "analysis_prompts": ["prompt1"],
            "max_segments": 10,
            "parallel_execution": True
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "search_queries" in str(exc_info.value)
        assert "list" in str(exc_info.value)
    
    def test_parse_plan_analysis_prompts_not_list(self, planner):
        """Test error handling when analysis_prompts is not a list."""
        response = json.dumps({
            "search_queries": ["query1"],
            "analysis_prompts": "not a list",
            "max_segments": 10,
            "parallel_execution": True
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "analysis_prompts" in str(exc_info.value)
        assert "list" in str(exc_info.value)
    
    def test_parse_plan_empty_analysis_prompts(self, planner):
        """Test error handling when analysis_prompts is empty."""
        response = json.dumps({
            "search_queries": ["query1"],
            "analysis_prompts": [],
            "max_segments": 10,
            "parallel_execution": True
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "analysis_prompts" in str(exc_info.value)
        assert "empty" in str(exc_info.value)
    
    def test_parse_plan_max_segments_not_int(self, planner):
        """Test error handling when max_segments is not an integer."""
        response = json.dumps({
            "search_queries": ["query1"],
            "analysis_prompts": ["prompt1"],
            "max_segments": "10",
            "parallel_execution": True
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "max_segments" in str(exc_info.value)
        assert "integer" in str(exc_info.value)
    
    def test_parse_plan_max_segments_zero(self, planner):
        """Test error handling when max_segments is zero."""
        response = json.dumps({
            "search_queries": ["query1"],
            "analysis_prompts": ["prompt1"],
            "max_segments": 0,
            "parallel_execution": True
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "max_segments" in str(exc_info.value)
        assert "positive" in str(exc_info.value)
    
    def test_parse_plan_max_segments_negative(self, planner):
        """Test error handling when max_segments is negative."""
        response = json.dumps({
            "search_queries": ["query1"],
            "analysis_prompts": ["prompt1"],
            "max_segments": -5,
            "parallel_execution": True
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "max_segments" in str(exc_info.value)
        assert "positive" in str(exc_info.value)
    
    def test_parse_plan_parallel_execution_not_bool(self, planner):
        """Test error handling when parallel_execution is not a boolean."""
        response = json.dumps({
            "search_queries": ["query1"],
            "analysis_prompts": ["prompt1"],
            "max_segments": 10,
            "parallel_execution": "true"
        })
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "parallel_execution" in str(exc_info.value)
        assert "boolean" in str(exc_info.value)
    
    def test_parse_plan_no_json(self, planner):
        """Test error handling when response contains no JSON."""
        response = "This is just plain text without any JSON"
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "No JSON object found" in str(exc_info.value)
    
    def test_parse_plan_invalid_json(self, planner):
        """Test error handling for malformed JSON."""
        response = '{"search_queries": ["query1"], "analysis_prompts":'  # Incomplete JSON
        
        with pytest.raises(ValueError) as exc_info:
            planner._parse_execution_plan(response)
        
        assert "Invalid JSON" in str(exc_info.value) or "No JSON object found" in str(exc_info.value)
    
    def test_parse_plan_with_whitespace(self, planner):
        """Test parsing response with leading/trailing whitespace."""
        response = """
        
        {
            "search_queries": ["query1"],
            "analysis_prompts": ["prompt1"],
            "max_segments": 10,
            "parallel_execution": true
        }
        
        """
        
        plan = planner._parse_execution_plan(response)
        
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.search_queries) == 1


class TestErrorHandling:
    """Tests for error handling in Planner."""
    
    @pytest.mark.asyncio
    async def test_create_execution_plan_claude_error(
        self, planner, mock_bedrock_client, search_intent
    ):
        """Test handling of Claude invocation errors."""
        # Mock Claude error
        mock_bedrock_client.invoke_claude.side_effect = BedrockError("API error")
        
        # Test - should propagate the error
        with pytest.raises(BedrockError):
            await planner.create_execution_plan(
                query="Test query",
                intent=search_intent,
                video_count=5
            )
    
    @pytest.mark.asyncio
    async def test_create_execution_plan_parsing_error(
        self, planner, mock_bedrock_client, search_intent
    ):
        """Test handling of response parsing errors."""
        # Mock invalid Claude response
        mock_bedrock_client.invoke_claude.return_value = "Invalid response"
        
        # Test - should raise ValueError
        with pytest.raises(ValueError):
            await planner.create_execution_plan(
                query="Test query",
                intent=search_intent,
                video_count=5
            )
    
    @pytest.mark.asyncio
    async def test_plan_search_based_analysis_error(
        self, planner, mock_bedrock_client
    ):
        """Test error handling in search-based planning."""
        # Mock Claude error
        mock_bedrock_client.invoke_claude.side_effect = RuntimeError("Unexpected error")
        
        # Test - should propagate the error
        with pytest.raises(RuntimeError):
            await planner._plan_search_based_analysis(
                query="Test query",
                video_count=5
            )
    
    @pytest.mark.asyncio
    async def test_plan_direct_analysis_error(
        self, planner, mock_bedrock_client
    ):
        """Test error handling in direct analysis planning."""
        # Mock Claude error
        mock_bedrock_client.invoke_claude.side_effect = RuntimeError("Unexpected error")
        
        # Test - should propagate the error
        with pytest.raises(RuntimeError):
            await planner._plan_direct_analysis(
                query="Test query",
                video_count=5
            )
