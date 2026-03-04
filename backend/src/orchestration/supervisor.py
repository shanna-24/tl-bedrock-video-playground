"""Supervisor component for intent determination in Jockey orchestration.

The Supervisor analyzes user queries to determine whether semantic search is needed
and what type of analysis to perform. It uses Claude for intent classification.

Validates: Requirements 1.1
"""

import json
import logging
from typing import TYPE_CHECKING

from models.orchestration import AnalysisIntent

if TYPE_CHECKING:
    from aws.bedrock_client import BedrockClient

logger = logging.getLogger(__name__)


class Supervisor:
    """Determines user intent and routes to appropriate workers.
    
    The Supervisor is the first component in the Jockey orchestration workflow.
    It analyzes the user's query using Claude to determine:
    1. Whether semantic search (Marengo) is needed to find relevant segments
    2. What type of analysis is required (specific vs general)
    
    This decision guides the Planner in creating an appropriate execution plan.
    
    Attributes:
        bedrock: BedrockClient instance for invoking Claude
        claude_model_id: Model ID for Claude (default: claude-3-5-sonnet)
    """
    
    def __init__(self, bedrock: "BedrockClient", claude_model_id: str):
        """Initialize the Supervisor.
        
        Args:
            bedrock: BedrockClient instance for Claude invocation
            claude_model_id: Claude model ID to use for intent classification
        """
        self.bedrock = bedrock
        self.claude_model_id = claude_model_id
        logger.info(f"Initialized Supervisor with Claude model: {claude_model_id}")
    
    async def determine_intent(self, query: str) -> AnalysisIntent:
        """Analyze query to determine if search is needed and analysis type.
        
        This method uses Claude to classify the user's query intent. It determines:
        - needs_search: Whether to use Marengo search to find specific segments
        - analysis_type: "specific" for targeted questions, "general" for broad questions
        - reasoning: Explanation of the classification decision
        
        Args:
            query: User's analysis query string
        
        Returns:
            AnalysisIntent object with classification results
        
        Raises:
            Exception: If Claude invocation fails or response parsing fails
        
        Examples:
            >>> supervisor = Supervisor(bedrock_client, "claude-3-5-sonnet")
            >>> intent = await supervisor.determine_intent("Show me all scenes with dogs")
            >>> print(intent.needs_search)  # True
            >>> print(intent.analysis_type)  # "specific"
        """
        logger.info(f"Determining intent for query: {query[:100]}...")
        
        # Build the intent classification prompt
        prompt = self._build_intent_prompt(query)
        
        # Invoke Claude for intent classification
        try:
            response = self.bedrock.invoke_claude(
                prompt=prompt,
                temperature=0.2,
                max_tokens=1024
            )
            
            # Parse the response into AnalysisIntent
            intent = self._parse_intent_response(response)
            
            logger.info(
                f"Intent determined - needs_search: {intent.needs_search}, "
                f"analysis_type: {intent.analysis_type}"
            )
            logger.debug(f"Reasoning: {intent.reasoning}")
            
            return intent
            
        except Exception as e:
            logger.error(f"Failed to determine intent: {e}")
            raise
    
    def _build_intent_prompt(self, query: str) -> str:
        """Build prompt for intent classification.
        
        Creates a structured prompt that instructs Claude to analyze the query
        and return a JSON response with intent classification.
        
        Args:
            query: User's analysis query
        
        Returns:
            Formatted prompt string for Claude
        """
        return f"""Analyze this video analysis query and determine if it requires searching for specific content or can be answered with general analysis.

Query: {query}

Respond with JSON in this exact format:
{{
    "needs_search": true/false,
    "analysis_type": "specific" or "general",
    "reasoning": "explanation"
}}

Guidelines:
- needs_search=true if query asks about specific events, objects, people, topics, or scenes
- needs_search=false if query asks for general summary, overview, or broad themes
- analysis_type="specific" for targeted questions about particular content
- analysis_type="general" for broad questions about overall themes or summaries
- reasoning should explain why you made this classification

Examples:
- "Show me all scenes with dogs" -> needs_search=true, analysis_type="specific"
- "What is this video about?" -> needs_search=false, analysis_type="general"
- "Find moments where people are laughing" -> needs_search=true, analysis_type="specific"
- "Summarize the main themes" -> needs_search=false, analysis_type="general"

Respond ONLY with the JSON object, no additional text."""
    
    def _parse_intent_response(self, response: str) -> AnalysisIntent:
        """Parse Claude response into AnalysisIntent object.
        
        Extracts the JSON from Claude's response and validates the structure.
        
        Args:
            response: Raw text response from Claude
        
        Returns:
            AnalysisIntent object with parsed values
        
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
            if "needs_search" not in data:
                raise ValueError("Response missing 'needs_search' field")
            if "analysis_type" not in data:
                raise ValueError("Response missing 'analysis_type' field")
            if "reasoning" not in data:
                raise ValueError("Response missing 'reasoning' field")
            
            # Validate analysis_type value
            if data["analysis_type"] not in ["specific", "general"]:
                raise ValueError(
                    f"Invalid analysis_type: {data['analysis_type']}. "
                    "Must be 'specific' or 'general'"
                )
            
            # Create and return AnalysisIntent
            return AnalysisIntent(
                needs_search=bool(data["needs_search"]),
                analysis_type=data["analysis_type"],
                reasoning=data["reasoning"]
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response: {response}")
            raise ValueError(f"Invalid JSON in Claude response: {e}") from e
        except Exception as e:
            logger.error(f"Failed to parse intent response: {e}")
            raise
