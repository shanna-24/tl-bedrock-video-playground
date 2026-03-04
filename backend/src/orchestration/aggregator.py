"""Aggregator component for combining insights from multiple video analyses.

The Aggregator synthesizes insights from multiple video segment analyses into
a coherent summary. It uses Claude to identify common themes, maintain source
attribution, and format the final response. Optionally, it can enrich insights
with web search results when additional context would be helpful.

Validates: Requirements 3.4, 3.5, 4.3, 4.4, 4.5
"""

import logging
from typing import List, Optional, TYPE_CHECKING

from aws.bedrock_client import BedrockClient
from models.orchestration import SegmentAnalysis

if TYPE_CHECKING:
    from services.web_search_client import WebSearchClient

logger = logging.getLogger(__name__)


class Aggregator:
    """Combines insights from multiple video analyses.
    
    The Aggregator is the final component in the Jockey orchestration workflow.
    After the Workers have analyzed multiple video segments, the Aggregator:
    1. Combines insights into a coherent narrative
    2. Identifies common themes and patterns across videos
    3. Preserves source attribution (video IDs, timestamps)
    4. Formats the response with metadata
    5. Optionally enriches insights with web search when helpful
    
    The Aggregator uses Claude to intelligently synthesize insights while
    maintaining factual accuracy and source traceability. When web search is
    enabled, Claude can request additional context from the web to enhance
    the analysis.
    
    Attributes:
        bedrock: BedrockClient instance for invoking Claude
        claude_model_id: Model ID for Claude (default: claude-3-5-sonnet)
        web_search: Optional WebSearchClient for web enrichment
    """
    
    def __init__(
        self,
        bedrock_client: BedrockClient,
        claude_model_id: str,
        web_search_client: Optional['WebSearchClient'] = None
    ):
        """Initialize the Aggregator.
        
        Args:
            bedrock_client: BedrockClient instance for Claude invocation
            claude_model_id: Claude model ID to use for insight aggregation
            web_search_client: Optional WebSearchClient for web enrichment
        """
        self.bedrock = bedrock_client
        self.claude_model_id = claude_model_id
        self.web_search = web_search_client
        
        if web_search_client:
            logger.info(
                f"Initialized Aggregator with Claude model: {claude_model_id} "
                "(web search enabled)"
            )
        else:
            logger.info(
                f"Initialized Aggregator with Claude model: {claude_model_id} "
                "(web search disabled)"
            )
    
    async def aggregate_insights(
        self,
        query: str,
        analyses: List[SegmentAnalysis],
        verbosity: str = "balanced"
    ) -> str:
        """Aggregate insights from multiple segment analyses.
        
        This method synthesizes insights from multiple video analyses into a
        comprehensive response that:
        - Directly addresses the user's query
        - Identifies common themes across videos
        - Highlights unique insights from specific videos
        - Maintains source attribution with video IDs and timestamps
        - Formats as a coherent narrative
        - Optionally enriches with web search when additional context is needed
        
        The aggregation happens in two stages when web search is enabled:
        1. Initial synthesis: Claude analyzes video insights and determines if
           web search would be helpful
        2. Enrichment: If needed, performs web searches and re-synthesizes with
           additional context
        
        Args:
            query: Original user query that prompted the analysis
            analyses: List of SegmentAnalysis objects from Pegasus Worker
            verbosity: Response style - "concise", "balanced", or "extended"
        
        Returns:
            Formatted string with aggregated insights, themes, and source attribution
        
        Raises:
            ValueError: If analyses is empty
            Exception: If Claude invocation fails
        
        Examples:
            >>> aggregator = Aggregator(bedrock_client, "claude-3-5-sonnet")
            >>> analyses = [analysis1, analysis2, analysis3]
            >>> result = await aggregator.aggregate_insights("Find dogs", analyses)
            >>> print(result)
            # "Based on analysis of 3 video segments, dogs appear in multiple scenes..."
        """
        if not analyses:
            raise ValueError("analyses cannot be empty")
        
        logger.info(
            f"Aggregating insights from {len(analyses)} segment analyses "
            f"for query: {query[:100]}... (verbosity: {verbosity})"
        )
        
        # Stage 1: Initial synthesis with option to request web search
        prompt = self._build_aggregation_prompt(query, analyses, verbosity)
        
        try:
            # Use Claude to synthesize insights
            logger.debug("Invoking Claude for insight aggregation (Stage 1)")
            response = self.bedrock.invoke_claude(
                prompt=prompt,
                temperature=0.2,
                max_tokens=4096
            )
            
            # Stage 2: Check if Claude requested web search and if it's enabled
            if self.web_search and self._should_perform_web_search(response):
                logger.info("Claude requested web search enrichment")
                
                # Extract search queries from Claude's response
                search_queries = self._extract_search_queries(response)
                
                if search_queries:
                    # Perform web searches
                    search_results = await self._perform_web_searches(search_queries)
                    
                    if search_results:
                        # Re-synthesize with web search results
                        logger.debug("Re-invoking Claude with web search results (Stage 2)")
                        enriched_prompt = self._build_enriched_prompt(
                            query, analyses, response, search_results, verbosity
                        )
                        response = self.bedrock.invoke_claude(
                            prompt=enriched_prompt,
                            temperature=0.2,
                            max_tokens=4096
                        )
                        logger.info("Completed web-enriched aggregation")
            
            # Format with source attribution (skip sources for concise mode)
            include_sources = verbosity not in ["concise"]
            formatted = self._format_with_attribution(response, analyses, include_sources)
            
            logger.info(
                f"Aggregation completed ({len(formatted)} characters, "
                f"{len(analyses)} sources)"
            )
            
            return formatted
            
        except Exception as e:
            logger.error(f"Failed to aggregate insights: {e}")
            raise
    
    def _build_aggregation_prompt(
        self,
        query: str,
        analyses: List[SegmentAnalysis],
        verbosity: str = "balanced"
    ) -> str:
        """Build prompt for insight aggregation.
        
        Creates a structured prompt that includes all segment analyses and
        instructs Claude to synthesize them into a coherent response.
        
        Args:
            query: User's original query
            analyses: List of SegmentAnalysis objects
            verbosity: Response style - "concise", "balanced", or "verbose"
        
        Returns:
            Formatted prompt string for Claude
        """
        # Build insights text with source attribution
        insights_text = "\n\n".join([
            f"Video {i+1} (ID: {a.segment.video_id}, "
            f"Timestamp: {a.segment.start_time:.1f}s-{a.segment.end_time:.1f}s, "
            f"Relevance: {a.segment.relevance_score:.3f}):\n{a.insights}"
            for i, a in enumerate(analyses)
        ])
        
        # Verbosity instructions - handle both API naming (concise/extended) and internal naming
        verbosity_instructions = {
            "concise": {
                "instruction": "CRITICAL: Keep your response EXTREMELY BRIEF. Provide ONLY the most essential answer in 1-2 SHORT paragraphs. Be direct and eliminate all unnecessary details. Do NOT list sources.",
                "max_paragraphs": "1-2 paragraphs MAXIMUM",
                "include_sources": False
            },
            "balanced": {
                "instruction": "Provide a well-rounded response covering key insights - aim for 3-5 paragraphs.",
                "max_paragraphs": "3-5 paragraphs",
                "include_sources": True
            },
            "extended": {
                "instruction": "Provide a COMPREHENSIVE and DETAILED analysis with thorough explanations, specific examples, and full context from all relevant videos.",
                "max_paragraphs": "5-8 paragraphs",
                "include_sources": True
            },
            "verbose": {
                "instruction": "Provide a COMPREHENSIVE and DETAILED analysis with thorough explanations, specific examples, and full context from all relevant videos.",
                "max_paragraphs": "5-8 paragraphs",
                "include_sources": True
            }
        }
        verbosity_config = verbosity_instructions.get(verbosity, verbosity_instructions["balanced"])
        
        return f"""Synthesize insights from multiple video analyses to answer this query.

Query: {query}

RESPONSE LENGTH REQUIREMENT: {verbosity_config["instruction"]}
Target length: {verbosity_config["max_paragraphs"]}

Video Analyses:
{insights_text}

Your task is to provide an answer that:
1. Directly addresses the user's query
2. Identifies common themes and patterns across the videos
3. Highlights unique or notable insights from specific videos
4. Maintains factual accuracy from the source analyses
5. References specific videos when mentioning insights (e.g., "In Video 1...", "Video 3 shows...")

Guidelines:
- Format your response as a coherent narrative, not a list
- Start with an overview that directly answers the query
- Use specific examples from the videos to support your points
- When mentioning an insight, reference which video(s) it came from
- If videos show different perspectives or contradictions, acknowledge them
- Keep the response focused on answering the user's question
- Do not add information that is not present in the analyses

REMEMBER: {verbosity_config["instruction"]}

{self._get_web_search_instruction()}

---

Respond with a well-structured narrative that synthesizes these insights."""
    
    def _get_web_search_instruction(self) -> str:
        """Get web search instruction based on availability.
        
        Returns:
            Instruction text for web search capability
        """
        if not self.web_search:
            return ""
        
        return """
WEB SEARCH CAPABILITY:
If you determine that current web information would significantly enhance your answer
(e.g., for questions about recent events, current statistics, latest developments, or
technical specifications not fully covered in the videos), you may request web searches.

To request web searches, include in your response:
[WEB_SEARCH_NEEDED]
Search queries (one per line):
- query 1
- query 2
- query 3
[/WEB_SEARCH_NEEDED]

Only request web searches if they would meaningfully improve the answer. Do not request
searches for information that is already adequately covered in the video analyses.
"""
    
    def _should_perform_web_search(self, response: str) -> bool:
        """Check if Claude requested web search in the response.
        
        Args:
            response: Claude's response text
        
        Returns:
            True if web search was requested
        """
        return "[WEB_SEARCH_NEEDED]" in response and "[/WEB_SEARCH_NEEDED]" in response
    
    def _extract_search_queries(self, response: str) -> List[str]:
        """Extract search queries from Claude's response.
        
        Args:
            response: Claude's response containing search request
        
        Returns:
            List of search query strings
        """
        try:
            # Extract content between markers
            start_marker = "[WEB_SEARCH_NEEDED]"
            end_marker = "[/WEB_SEARCH_NEEDED]"
            
            start_idx = response.find(start_marker)
            end_idx = response.find(end_marker)
            
            if start_idx == -1 or end_idx == -1:
                return []
            
            search_block = response[start_idx + len(start_marker):end_idx].strip()
            
            # Extract queries (lines starting with -)
            queries = []
            for line in search_block.split('\n'):
                line = line.strip()
                if line.startswith('-'):
                    query = line[1:].strip()
                    if query:
                        queries.append(query)
            
            logger.info(f"Extracted {len(queries)} search queries from Claude's response")
            return queries[:3]  # Limit to 3 queries
            
        except Exception as e:
            logger.error(f"Failed to extract search queries: {e}")
            return []
    
    async def _perform_web_searches(self, queries: List[str]) -> List[dict]:
        """Perform web searches for the given queries.
        
        Args:
            queries: List of search query strings
        
        Returns:
            List of search result dictionaries with query and results
        """
        if not self.web_search:
            return []
        
        all_results = []
        
        for query in queries:
            try:
                results = await self.web_search.search(query, count=3)
                if results:
                    all_results.append({
                        "query": query,
                        "results": results
                    })
            except Exception as e:
                logger.error(f"Web search failed for query '{query}': {e}")
                continue
        
        return all_results
    
    def _build_enriched_prompt(
        self,
        query: str,
        analyses: List[SegmentAnalysis],
        initial_response: str,
        search_results: List[dict],
        verbosity: str = "balanced"
    ) -> str:
        """Build enriched prompt with web search results.
        
        Args:
            query: Original user query
            analyses: List of SegmentAnalysis objects
            initial_response: Claude's initial response with search request
            search_results: Web search results
            verbosity: Response style
        
        Returns:
            Enriched prompt for Claude
        """
        # Format search results
        search_text = "\n\n".join([
            f"Search Query: {sr['query']}\nResults:\n" + 
            "\n".join([
                f"- {r['title']}: {r['description']}"
                for r in sr['results']
            ])
            for sr in search_results
        ])
        
        # Build insights text
        insights_text = "\n\n".join([
            f"Video {i+1} (ID: {a.segment.video_id}, "
            f"Timestamp: {a.segment.start_time:.1f}s-{a.segment.end_time:.1f}s):\n{a.insights}"
            for i, a in enumerate(analyses)
        ])
        
        verbosity_instructions = {
            "concise": "CRITICAL: Keep your response EXTREMELY BRIEF. Provide ONLY the most essential answer in 1-2 SHORT paragraphs.",
            "balanced": "Provide a well-rounded response covering key insights - aim for 3-5 paragraphs.",
            "extended": "Provide a COMPREHENSIVE and DETAILED analysis with thorough explanations.",
            "verbose": "Provide a COMPREHENSIVE and DETAILED analysis with thorough explanations."
        }
        verbosity_instruction = verbosity_instructions.get(verbosity, verbosity_instructions["balanced"])
        
        return f"""You previously analyzed video insights and requested web searches to enhance your answer.

Original Query: {query}

Video Analyses:
{insights_text}

Web Search Results:
{search_text}

Now, synthesize a comprehensive answer that:
1. Integrates insights from both the video analyses and web search results
2. Clearly distinguishes between information from videos vs. web sources
3. Provides a coherent narrative that fully addresses the user's query
4. References sources appropriately (e.g., "According to the videos..." vs. "Current information shows...")

{verbosity_instruction}

Do NOT include the [WEB_SEARCH_NEEDED] markers in your final response.

Provide your final, enriched answer:"""
    
    def _format_with_attribution(
        self,
        response: str,
        analyses: List[SegmentAnalysis],
        include_sources: bool = True
    ) -> str:
        """Format response with source attribution metadata.
        
        Adds metadata section at the end of the response that lists all
        analyzed videos with their IDs and timestamps for reference.
        
        Args:
            response: Synthesized response from Claude
            analyses: List of SegmentAnalysis objects
            include_sources: Whether to include source attribution (False for concise mode)
        
        Returns:
            Formatted response with attribution metadata
        """
        # For concise mode, return response without sources
        if not include_sources:
            return response.strip()
        
        # Build source attribution section
        attribution_lines = ["\n\n---\n**Sources:**"]
        
        for i, analysis in enumerate(analyses):
            seg = analysis.segment
            attribution_lines.append(
                f"- Video {i+1}: {seg.video_id} "
                f"[{seg.start_time:.1f}s-{seg.end_time:.1f}s] "
                f"(relevance: {seg.relevance_score:.3f})"
            )
        
        # Add metadata summary
        video_ids = set(a.segment.video_id for a in analyses)
        attribution_lines.append(
            f"\n*Analyzed {len(analyses)} segments from {len(video_ids)} video(s)*"
        )
        
        attribution_text = "\n".join(attribution_lines)
        
        # Combine response with attribution
        formatted = response.strip() + attribution_text
        
        return formatted
