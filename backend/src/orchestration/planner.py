"""Planner component for execution planning in Jockey orchestration.

The Planner breaks down complex multi-video analysis queries into structured
execution steps. It generates Marengo search queries and Pegasus analysis prompts
based on the intent determined by the Supervisor.

Validates: Requirements 1.2, 2.1, 3.1
"""

import json
import logging
from typing import TYPE_CHECKING

from models.orchestration import AnalysisIntent, ExecutionPlan

if TYPE_CHECKING:
    from aws.bedrock_client import BedrockClient

logger = logging.getLogger(__name__)


class Planner:
    """Breaks down complex queries into execution steps.
    
    The Planner is the second component in the Jockey orchestration workflow.
    After the Supervisor determines the intent, the Planner creates a structured
    execution plan that includes:
    1. Search queries for Marengo (if search is needed)
    2. Analysis prompts for Pegasus
    3. Execution parameters (max segments, parallelization)
    
    The Planner uses Claude to intelligently decompose complex queries into
    actionable steps for the Workers.
    
    Attributes:
        bedrock: BedrockClient instance for invoking Claude
        claude_model_id: Model ID for Claude (default: claude-3-5-sonnet)
    """
    
    def __init__(self, bedrock: "BedrockClient", claude_model_id: str, max_segments_limit: int = 10):
        """Initialize the Planner.
        
        Args:
            bedrock: BedrockClient instance for Claude invocation
            claude_model_id: Claude model ID to use for execution planning
            max_segments_limit: Maximum number of segments allowed per query (from config)
        """
        self.bedrock = bedrock
        self.claude_model_id = claude_model_id
        self.max_segments_limit = max_segments_limit
        logger.info(f"Initialized Planner with Claude model: {claude_model_id}, max_segments_limit: {max_segments_limit}")
    
    async def create_execution_plan(
        self,
        query: str,
        intent: AnalysisIntent,
        video_count: int
    ) -> ExecutionPlan:
        """Create structured execution plan for analysis.
        
        This method generates a detailed execution plan based on the user's query
        and the determined intent. The plan includes:
        - Search queries for finding relevant segments (if needed)
        - Analysis prompts for examining content
        - Execution parameters (segment limits, parallelization)
        
        Args:
            query: User's analysis query string
            intent: AnalysisIntent from Supervisor with needs_search and analysis_type
            video_count: Number of videos in the index
        
        Returns:
            ExecutionPlan object with search queries, analysis prompts, and parameters
        
        Raises:
            Exception: If Claude invocation fails or response parsing fails
        
        Examples:
            >>> planner = Planner(bedrock_client, "claude-3-5-sonnet")
            >>> intent = AnalysisIntent(needs_search=True, analysis_type="specific", reasoning="...")
            >>> plan = await planner.create_execution_plan("Find dogs", intent, 10)
            >>> print(plan.search_queries)  # ["dogs", "canine animals"]
            >>> print(plan.max_segments)  # 10
        """
        logger.info(
            f"Creating execution plan for query: {query[:100]}... "
            f"(needs_search={intent.needs_search}, video_count={video_count})"
        )
        
        # Choose planning strategy based on intent
        if intent.needs_search:
            plan = await self._plan_search_based_analysis(query, video_count)
        else:
            plan = await self._plan_direct_analysis(query, video_count)
        
        logger.info(
            f"Execution plan created - search_queries: {len(plan.search_queries)}, "
            f"analysis_prompts: {len(plan.analysis_prompts)}, "
            f"max_segments: {plan.max_segments}"
        )
        logger.debug(f"Search queries: {plan.search_queries}")
        logger.debug(f"Analysis prompts: {plan.analysis_prompts}")
        
        return plan
    
    async def _plan_search_based_analysis(
        self,
        query: str,
        video_count: int
    ) -> ExecutionPlan:
        """Plan analysis that starts with Marengo search.
        
        For queries that require finding specific content, this method uses Claude
        to generate:
        1. Semantic search queries for Marengo
        2. Focused analysis prompts for examining found segments
        3. Appropriate segment limits based on query complexity
        
        Args:
            query: User's analysis query
            video_count: Number of videos in the index
        
        Returns:
            ExecutionPlan with search queries and analysis configuration
        
        Raises:
            Exception: If Claude invocation or parsing fails
        """
        logger.debug(f"Planning search-based analysis for: {query[:100]}...")
        
        # Build the search planning prompt
        prompt = self._build_search_planning_prompt(query, video_count)
        
        # Invoke Claude for planning
        try:
            response = self.bedrock.invoke_claude(
                prompt=prompt,
                temperature=0.2,
                max_tokens=2048
            )
            
            # Parse the response into ExecutionPlan
            plan = self._parse_execution_plan(response)
            
            return plan
            
        except Exception as e:
            logger.error(f"Failed to create search-based execution plan: {e}")
            raise
    
    async def _plan_direct_analysis(
        self,
        query: str,
        video_count: int
    ) -> ExecutionPlan:
        """Plan analysis without search (direct analysis of videos).
        
        For queries that don't require finding specific content (e.g., general
        summaries), this method uses Claude to generate:
        1. Broad analysis prompts for examining videos
        2. Appropriate video selection strategy
        3. Execution parameters
        
        Args:
            query: User's analysis query
            video_count: Number of videos in the index
        
        Returns:
            ExecutionPlan with empty search queries and direct analysis prompts
        
        Raises:
            Exception: If Claude invocation or parsing fails
        """
        logger.debug(f"Planning direct analysis for: {query[:100]}...")
        
        # Build the direct analysis planning prompt
        prompt = self._build_direct_planning_prompt(query, video_count)
        
        # Invoke Claude for planning
        try:
            response = self.bedrock.invoke_claude(
                prompt=prompt,
                temperature=0.2,
                max_tokens=2048
            )
            
            # Parse the response into ExecutionPlan
            plan = self._parse_execution_plan(response)
            
            return plan
            
        except Exception as e:
            logger.error(f"Failed to create direct execution plan: {e}")
            raise
    
    def _build_search_planning_prompt(self, query: str, video_count: int) -> str:
        """Build prompt for search-based planning.
        
        Creates a structured prompt that instructs Claude to generate search
        queries and analysis prompts for finding and examining specific content.
        
        Args:
            query: User's analysis query
            video_count: Number of videos in the index
        
        Returns:
            Formatted prompt string for Claude
        """
        return f"""Create an execution plan for analyzing {video_count} videos to answer this query using semantic search.

Query: {query}

Your task is to:
1. Generate 1-3 semantic search queries to find relevant video segments
2. Create focused analysis prompts for examining the found segments
3. Determine the optimal number of segments to analyze (balance thoroughness vs cost)

Respond with JSON in this exact format:
{{
    "search_queries": ["query1", "query2", ...],
    "analysis_prompts": ["prompt1", "prompt2", ...],
    "max_segments": 10,
    "parallel_execution": true
}}

Guidelines for search_queries:
- Use semantic, descriptive terms (not just keywords)
- Cover different aspects of the query if complex
- Keep queries focused and specific
- Generate 1-3 queries (more queries = broader coverage)
- Examples: "people laughing and smiling", "outdoor nature scenes", "product demonstrations"

Guidelines for analysis_prompts:
- Create prompts that examine the found segments in detail
- Focus on answering the user's specific question
- Be specific about what to look for
- Usually 1-2 prompts are sufficient
- Examples: "Describe the emotions and interactions in this scene", "Identify the products shown and how they are demonstrated"

Guidelines for max_segments:
- For simple queries: 5-8 segments
- For moderate complexity: 8-12 segments
- For complex queries: 12-15 segments
- Consider video_count: more videos = potentially more segments needed

Guidelines for parallel_execution:
- Set to true for most cases (faster execution)
- Set to false only if sequential analysis is required

Respond ONLY with the JSON object, no additional text."""
    
    def _build_direct_planning_prompt(self, query: str, video_count: int) -> str:
        """Build prompt for direct analysis planning.
        
        Creates a structured prompt that instructs Claude to generate analysis
        prompts for direct video examination without search.
        
        Args:
            query: User's analysis query
            video_count: Number of videos in the index
        
        Returns:
            Formatted prompt string for Claude
        """
        return f"""Create an execution plan for analyzing {video_count} videos to answer this query using direct analysis (no search).

Query: {query}

Your task is to:
1. Create comprehensive analysis prompts for examining videos directly
2. Determine how many videos to analyze
3. Set execution parameters

Respond with JSON in this exact format:
{{
    "search_queries": [],
    "analysis_prompts": ["prompt1", "prompt2", ...],
    "max_segments": 5,
    "parallel_execution": true
}}

Guidelines for analysis_prompts:
- Create prompts that examine overall video content
- Focus on answering the user's question comprehensively
- For summaries: ask for main themes, key points, overall narrative
- For general questions: be broad and inclusive
- Usually 1-2 prompts are sufficient
- Examples: "Provide a comprehensive summary of the main themes and topics in this video", "Describe the overall narrative arc and key moments"

Guidelines for max_segments:
- For general summaries: 3-5 videos
- For thematic analysis: 5-8 videos
- For comprehensive overview: 8-10 videos
- Consider video_count: analyze a representative sample

Guidelines for parallel_execution:
- Set to true for most cases (faster execution)

Note: search_queries should be an empty list for direct analysis.

Respond ONLY with the JSON object, no additional text."""
    
    def _parse_execution_plan(self, response: str) -> ExecutionPlan:
        """Parse Claude response into ExecutionPlan object.
        
        Extracts the JSON from Claude's response and validates the structure.
        
        Args:
            response: Raw text response from Claude
        
        Returns:
            ExecutionPlan object with parsed values
        
        Raises:
            ValueError: If response is not valid JSON or missing required fields
            json.JSONDecodeError: If response cannot be parsed as JSON
        """
        try:
            # Try to parse the response as JSON
            # Claude might include some text before/after the JSON, so we need to extract it
            response = response.strip()
            
            # Find JSON object in response
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx == -1 or end_idx == -1:
                raise ValueError(f"No JSON object found in response: {response}")
            
            json_str = response[start_idx:end_idx + 1]
            data = json.loads(json_str)
            
            # Validate required fields
            if "search_queries" not in data:
                raise ValueError("Response missing 'search_queries' field")
            if "analysis_prompts" not in data:
                raise ValueError("Response missing 'analysis_prompts' field")
            if "max_segments" not in data:
                raise ValueError("Response missing 'max_segments' field")
            if "parallel_execution" not in data:
                raise ValueError("Response missing 'parallel_execution' field")
            
            # Validate types
            if not isinstance(data["search_queries"], list):
                raise ValueError("'search_queries' must be a list")
            if not isinstance(data["analysis_prompts"], list):
                raise ValueError("'analysis_prompts' must be a list")
            if not isinstance(data["max_segments"], int):
                raise ValueError("'max_segments' must be an integer")
            if not isinstance(data["parallel_execution"], bool):
                raise ValueError("'parallel_execution' must be a boolean")
            
            # Validate analysis_prompts is not empty
            if not data["analysis_prompts"]:
                raise ValueError("'analysis_prompts' cannot be empty")
            
            # Validate max_segments is positive
            if data["max_segments"] <= 0:
                raise ValueError("'max_segments' must be positive")
            
            # Cap max_segments to configured limit
            original_max_segments = data["max_segments"]
            if data["max_segments"] > self.max_segments_limit:
                logger.info(
                    f"Capping max_segments from {data['max_segments']} to configured limit {self.max_segments_limit}"
                )
                data["max_segments"] = self.max_segments_limit
            
            # Create and return ExecutionPlan
            return ExecutionPlan(
                search_queries=data["search_queries"],
                analysis_prompts=data["analysis_prompts"],
                max_segments=data["max_segments"],
                parallel_execution=data["parallel_execution"]
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response: {response}")
            raise ValueError(f"Invalid JSON in Claude response: {e}") from e
        except Exception as e:
            logger.error(f"Failed to parse execution plan response: {e}")
            raise
