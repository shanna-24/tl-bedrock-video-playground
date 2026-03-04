"""JockeyOrchestrator - Main coordination component for Jockey-inspired analysis.

The JockeyOrchestrator coordinates the entire index-level video analysis workflow,
bringing together the Supervisor, Planner, Workers, and Aggregator components.
It manages the complete analysis process from query to final result, with robust
error handling and fallback strategies.

Validates: Requirements 1.4, 7.1, 7.2, 7.3, 7.5
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from services.search_service import SearchService
from config import Config
from models.analysis import AnalysisResult
from models.orchestration import VideoSegment
from orchestration.supervisor import Supervisor
from orchestration.planner import Planner
from orchestration.marengo_worker import MarengoWorker
from orchestration.pegasus_worker import PegasusWorker
from orchestration.aggregator import Aggregator
from exceptions import AWSServiceError, AnalysisCancelledError
from utils.progress_tracker import check_cancellation

logger = logging.getLogger(__name__)


class JockeyOrchestrator:
    """Main orchestration component for Jockey-inspired analysis.
    
    The JockeyOrchestrator is the entry point for index-level video analysis.
    It coordinates all components in the Jockey workflow:
    1. Supervisor - Determines user intent
    2. Planner - Creates execution plan
    3. MarengoWorker - Finds relevant video segments
    4. PegasusWorker - Analyzes video segments
    5. Aggregator - Combines insights into final result
    
    The orchestrator also implements fallback strategies for graceful error handling:
    - Falls back to representative videos if search returns no results
    - Returns partial results if some analyses fail
    - Returns raw insights if aggregation fails
    
    Attributes:
        bedrock: BedrockClient instance for Claude and Pegasus
        search: SearchService instance for Marengo search
        config: Configuration object with Jockey settings
        supervisor: Supervisor component for intent determination
        planner: Planner component for execution planning
        marengo_worker: MarengoWorker for semantic search
        pegasus_worker: PegasusWorker for video analysis
        aggregator: Aggregator for insight synthesis
    """
    
    def __init__(
        self,
        bedrock_client: BedrockClient,
        search_service: SearchService,
        s3_client: S3Client,
        config: Config
    ):
        """Initialize the JockeyOrchestrator with all components.
        
        Args:
            bedrock_client: BedrockClient for Claude and Pegasus invocation
            search_service: SearchService for Marengo search
            s3_client: S3Client for video download/upload operations
            config: Configuration object with Jockey settings
        """
        self.bedrock = bedrock_client
        self.search = search_service
        self.s3 = s3_client
        self.config = config
        
        # Get Jockey configuration
        jockey_config = config.jockey
        claude_model_id = jockey_config.claude_model_id
        
        # Initialize web search client if enabled
        web_search_client = None
        if jockey_config.web_search_enabled and jockey_config.brave_api_key:
            try:
                from services.web_search_client import WebSearchClient
                web_search_client = WebSearchClient(jockey_config.brave_api_key)
                logger.info("Web search enrichment enabled for aggregation")
            except Exception as e:
                logger.warning(f"Failed to initialize web search client: {e}")
        elif jockey_config.web_search_enabled:
            logger.warning(
                "Web search is enabled but no Brave API key provided. "
                "Web search will be disabled."
            )
        
        # Initialize all components
        self.supervisor = Supervisor(bedrock_client, claude_model_id)
        self.planner = Planner(
            bedrock_client, 
            claude_model_id,
            max_segments_limit=jockey_config.max_segments_per_query
        )
        self.marengo_worker = MarengoWorker(
            search_service,
            max_results_per_query=jockey_config.max_search_results
        )
        self.pegasus_worker = PegasusWorker(bedrock_client, s3_client)
        self.aggregator = Aggregator(bedrock_client, claude_model_id, web_search_client)
        
        logger.info(
            f"Initialized JockeyOrchestrator with Claude model: {claude_model_id}, "
            f"max_segments_per_query: {jockey_config.max_segments_per_query}, "
            f"max_search_results: {jockey_config.max_search_results}"
        )
    
    async def analyze_single_video(
        self,
        video_id: str,
        query: str,
        video_s3_uri: str,
        verbosity: str = "concise",
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        progress_callback: Optional[callable] = None,
        correlation_id: Optional[str] = None
    ) -> AnalysisResult:
        """Analyze a single video using Jockey pattern (bypassing segment search).
        
        This method is optimized for single video analysis with Jockey framework.
        It bypasses the Supervisor, Planner, and MarengoWorker components and goes
        straight to Pegasus analysis followed by Claude aggregation for enhanced insights.
        
        Workflow:
        1. Create a VideoSegment for the full video
        2. Analyze with PegasusWorker
        3. Aggregate insights with Claude (Aggregator)
        4. Format and return result
        
        Args:
            video_id: ID of the video to analyze
            query: User's natural language analysis query
            video_s3_uri: S3 URI of the video
            verbosity: Response verbosity level ('concise' or 'extended')
            temperature: Temperature for Pegasus analysis (0-1, default: 0.2)
            max_output_tokens: Maximum tokens for Pegasus (optional)
            progress_callback: Optional async callback for progress updates
            correlation_id: Optional correlation ID for cancellation tracking
        
        Returns:
            AnalysisResult object with aggregated insights and metadata
        
        Raises:
            ValueError: If query is empty or video URI is invalid
            AWSServiceError: If critical errors occur during analysis
            AnalysisCancelledError: If the analysis is cancelled by the user
        """
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Analysis query cannot be empty")
        
        if not video_s3_uri or not video_s3_uri.startswith("s3://"):
            raise ValueError("Invalid video S3 URI")
        
        # Use provided correlation ID or generate one for request tracing
        trace_id = correlation_id or str(uuid.uuid4())
        
        logger.info(
            f"[{trace_id}] Starting Jockey single video analysis for {video_id}, "
            f"query: {query[:100]}..."
        )
        
        try:
            # Check for cancellation before starting
            if correlation_id:
                check_cancellation(correlation_id)
            
            # Step 1: Create VideoSegment for full video (bypass search)
            if progress_callback:
                await progress_callback("Analyzing video content...")
            
            logger.info(f"[{trace_id}] Step 1: Creating segment for full video")
            
            segment = VideoSegment(
                video_id=video_id,
                s3_uri=video_s3_uri,
                start_time=0.0,
                end_time=0.0,  # 0.0 indicates full video
                relevance_score=1.0  # Full relevance for single video analysis
            )
            
            # Check for cancellation before Pegasus analysis
            if correlation_id:
                check_cancellation(correlation_id)
            
            # Step 2: Analyze video using PegasusWorker
            logger.info(f"[{trace_id}] Step 2: Analyzing video with Pegasus")
            
            try:
                analysis = await self.pegasus_worker.analyze_segment(
                    segment=segment,
                    prompt=query,
                    temperature=temperature,
                    extract_segment=False  # No segment extraction needed for single video
                )
                
                logger.info(
                    f"[{trace_id}] Pegasus analysis completed "
                    f"({len(analysis.insights)} characters)"
                )
                
            except AnalysisCancelledError:
                raise  # Re-raise cancellation
            except Exception as e:
                logger.error(f"[{trace_id}] Pegasus analysis failed: {e}")
                raise AWSServiceError(
                    f"Failed to analyze video: {str(e)}"
                ) from e
            
            # Check for cancellation before aggregation
            if correlation_id:
                check_cancellation(correlation_id)
            
            # Step 3: Aggregate insights using Claude (Aggregator)
            if progress_callback:
                await progress_callback("Enhancing insights...")
            
            logger.info(f"[{trace_id}] Step 3: Aggregating insights with Claude")
            
            try:
                aggregated_insights = await self.aggregator.aggregate_insights(
                    query=query,
                    analyses=[analysis],
                    verbosity=verbosity
                )
                
                logger.info(
                    f"[{trace_id}] Aggregation completed "
                    f"({len(aggregated_insights)} characters)"
                )
                
            except AnalysisCancelledError:
                raise  # Re-raise cancellation
            except Exception as e:
                logger.warning(
                    f"[{trace_id}] Aggregation failed: {e}. "
                    "Falling back to raw Pegasus insights"
                )
                
                # Fallback: Return raw Pegasus insights without aggregation
                aggregated_insights = analysis.insights
                
                logger.info(
                    f"[{trace_id}] Using raw Pegasus insights fallback"
                )
            
            # Step 4: Format and return result
            logger.info(f"[{trace_id}] Step 4: Formatting result")
            
            metadata = {
                "correlation_id": trace_id,
                "video_s3_uri": video_s3_uri,
                "jockey_enabled": True,
                "single_video_mode": True,
                "bypassed_segment_search": True
            }
            
            result = AnalysisResult(
                query=query,
                scope="video",
                scope_id=video_id,
                insights=aggregated_insights,
                analyzed_at=datetime.now(),
                metadata=metadata
            )
            
            logger.info(
                f"[{trace_id}] Jockey single video analysis completed successfully"
            )
            
            return result
            
        except AnalysisCancelledError:
            # Re-raise cancellation errors
            logger.info(f"[{trace_id}] Analysis cancelled by user")
            raise
        except ValueError as e:
            # Re-raise validation errors
            logger.error(f"[{trace_id}] Validation error: {e}")
            raise
        except Exception as e:
            # Log and wrap unexpected errors
            logger.error(
                f"[{trace_id}] Single video analysis failed with unexpected error: {e}",
                exc_info=True
            )
            raise AWSServiceError(
                f"Single video analysis failed: {str(e)}"
            ) from e
    
    async def analyze_index(
        self,
        index_id: str,
        query: str,
        video_s3_uris: List[str],
        verbosity: str = "balanced",
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        progress_callback: Optional[callable] = None,
        correlation_id: Optional[str] = None
    ) -> AnalysisResult:
        """Orchestrate index-level analysis using Jockey pattern.
        
        This is the main entry point for index-level video analysis. It coordinates
        the entire workflow:
        1. Generate correlation ID for request tracing
        2. Determine user intent (Supervisor)
        3. Create execution plan (Planner)
        4. Search for relevant segments (MarengoWorker) - if needed
        5. Analyze segments (PegasusWorker)
        6. Aggregate insights (Aggregator)
        7. Format and return result
        
        The method implements fallback strategies for graceful error handling:
        - If search returns no results, falls back to analyzing representative videos
        - If some analyses fail, continues with successful ones
        - If aggregation fails, returns raw insights
        
        Args:
            index_id: ID of the index to analyze
            query: User's natural language analysis query
            video_s3_uris: List of S3 URIs for videos in the index
            verbosity: Response verbosity level ('concise' or 'extended')
            temperature: Temperature for Pegasus analysis (0-1, default: 0.2)
            max_output_tokens: Maximum tokens for Pegasus (optional)
            progress_callback: Optional async callback for progress updates
            correlation_id: Optional correlation ID for cancellation tracking
        
        Returns:
            AnalysisResult object with aggregated insights and metadata
        
        Raises:
            ValueError: If query is empty or no videos in index
            AWSServiceError: If critical errors occur during orchestration
            AnalysisCancelledError: If the analysis is cancelled by the user
        """
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Analysis query cannot be empty")
        
        if not video_s3_uris:
            raise ValueError("No videos found in index for analysis")
        
        # Use provided correlation ID or generate one for request tracing
        trace_id = correlation_id or str(uuid.uuid4())
        
        logger.info(
            f"[{trace_id}] Starting Jockey orchestration for index {index_id} "
            f"with {len(video_s3_uris)} videos, query: {query[:100]}..."
        )
        
        try:
            # Check for cancellation before starting
            if correlation_id:
                check_cancellation(correlation_id)
            
            # Step 1: Determine intent using Supervisor
            logger.info(f"[{trace_id}] Step 1: Determining intent")
            if progress_callback:
                await progress_callback("Understanding your question...")
            intent = await self.supervisor.determine_intent(query)
            
            logger.info(
                f"[{trace_id}] Intent determined - needs_search: {intent.needs_search}, "
                f"analysis_type: {intent.analysis_type}"
            )
            
            # Check for cancellation after intent determination
            if correlation_id:
                check_cancellation(correlation_id)
            
            # Step 2: Create execution plan using Planner
            logger.info(f"[{trace_id}] Step 2: Creating execution plan")
            plan = await self.planner.create_execution_plan(
                query=query,
                intent=intent,
                video_count=len(video_s3_uris)
            )
            
            logger.info(
                f"[{trace_id}] Execution plan created - "
                f"search_queries: {len(plan.search_queries)}, "
                f"max_segments: {plan.max_segments}"
            )
            
            # Check for cancellation after planning
            if correlation_id:
                check_cancellation(correlation_id)
            
            # Step 3: Search for relevant segments (if needed)
            segments = []
            if intent.needs_search and plan.search_queries:
                if progress_callback:
                    await progress_callback("Finding relevant video segments...")
                
                logger.info(f"[{trace_id}] Step 3: Searching for relevant segments")
                
                try:
                    segments = await self.marengo_worker.search_segments(
                        index_id=index_id,
                        search_queries=plan.search_queries,
                        max_segments=plan.max_segments
                    )
                    
                    logger.info(
                        f"[{trace_id}] Found {len(segments)} relevant segments"
                    )
                    
                    # Progress update after search completes
                    if progress_callback:
                        await progress_callback("Analyzing video content...")
                    
                except AnalysisCancelledError:
                    raise  # Re-raise cancellation
                except Exception as e:
                    logger.warning(
                        f"[{trace_id}] Search failed: {e}. "
                        "Falling back to representative videos"
                    )
                    segments = []
            
            # Fallback: If no segments found, create segments from representative videos
            if not segments:
                if progress_callback:
                    await progress_callback("Selecting video segments...")
                
                logger.info(
                    f"[{trace_id}] No segments from search, "
                    "using representative videos fallback"
                )
                
                # For Entire Index analysis without search results, analyze ALL videos
                # Don't limit by plan.max_segments since that's meant for segment-level analysis
                segments = self._create_representative_segments(
                    video_s3_uris=video_s3_uris,
                    max_segments=len(video_s3_uris)  # Analyze all videos in the index
                )
                
                logger.info(
                    f"[{trace_id}] Created {len(segments)} representative segments "
                    f"(one per video for comprehensive index coverage)"
                )
                
                # Progress update after fallback segments created
                if progress_callback:
                    await progress_callback("Analyzing video content...")
            
            # Check for cancellation before segment analysis
            if correlation_id:
                check_cancellation(correlation_id)
            
            # NOTE: For Entire Index analysis, we do NOT deduplicate segments by video.
            # Each segment should be analyzed individually to provide comprehensive coverage.
            # Multiple segments from the same video will be analyzed separately.
            
            logger.info(
                f"[{trace_id}] Total segments to analyze: {len(segments)}"
            )
            
            # Step 4: Analyze segments using PegasusWorker with segment extraction
            
            logger.info(
                f"[{trace_id}] Step 4: Analyzing {len(segments)} segments with segment extraction"
            )
            
            # Use the first analysis prompt from the plan
            analysis_prompt = plan.analysis_prompts[0] if plan.analysis_prompts else query
            
            try:
                if plan.parallel_execution and len(segments) > 1:
                    # Parallel analysis with concurrency control and segment extraction
                    analyses = await self.pegasus_worker.analyze_segments_parallel(
                        segments=segments,
                        prompt=analysis_prompt,
                        temperature=temperature,
                        max_concurrent=self.config.jockey.parallel_analysis_limit,
                        extract_segments=True,  # Enable segment extraction for Entire Index analysis
                        correlation_id=correlation_id  # Pass correlation_id for cancellation
                    )
                else:
                    # Sequential analysis with segment extraction
                    # Create a shared temp directory for the sequential analysis session
                    import tempfile
                    from pathlib import Path
                    
                    temp_dir_obj = tempfile.TemporaryDirectory()
                    shared_temp_path = Path(temp_dir_obj.name)
                    
                    try:
                        analyses = []
                        for segment in segments:
                            # Check for cancellation before each segment
                            if correlation_id:
                                check_cancellation(correlation_id)
                            
                            try:
                                analysis = await self.pegasus_worker.analyze_segment(
                                    segment=segment,
                                    prompt=analysis_prompt,
                                    temperature=temperature,
                                    extract_segment=True,  # Enable segment extraction for Entire Index analysis
                                    shared_temp_path=shared_temp_path  # Provide shared temp directory
                                )
                                analyses.append(analysis)
                            except AnalysisCancelledError:
                                raise  # Re-raise cancellation
                            except Exception as e:
                                logger.error(
                                    f"[{trace_id}] Failed to analyze segment "
                                    f"{segment.video_id}: {e}"
                                )
                                # Continue with other segments
                                continue
                    finally:
                        # Clean up temp directory after sequential analysis
                        temp_dir_obj.cleanup()
                
                logger.info(
                    f"[{trace_id}] Completed {len(analyses)} analyses "
                    f"({len(segments) - len(analyses)} failed)"
                )
                
                # Check if we have any successful analyses
                if not analyses:
                    raise AWSServiceError(
                        "All segment analyses failed. Unable to generate insights."
                    )
                
            except AnalysisCancelledError:
                raise  # Re-raise cancellation
            except Exception as e:
                logger.error(f"[{trace_id}] Analysis phase failed: {e}")
                raise
            
            # Check for cancellation before aggregation
            if correlation_id:
                check_cancellation(correlation_id)
            
            # Step 5: Aggregate insights using Aggregator
            if progress_callback:
                await progress_callback("Enhancing insights...")
            
            logger.info(f"[{trace_id}] Step 5: Aggregating insights")
            
            try:
                aggregated_insights = await self.aggregator.aggregate_insights(
                    query=query,
                    analyses=analyses,
                    verbosity=verbosity
                )
                
                logger.info(
                    f"[{trace_id}] Aggregation completed "
                    f"({len(aggregated_insights)} characters)"
                )
                
            except AnalysisCancelledError:
                raise  # Re-raise cancellation
            except Exception as e:
                logger.warning(
                    f"[{trace_id}] Aggregation failed: {e}. "
                    "Falling back to raw insights"
                )
                
                # Fallback: Return raw insights without aggregation
                aggregated_insights = self._format_raw_insights(analyses)
                
                logger.info(
                    f"[{trace_id}] Using raw insights fallback "
                    f"({len(aggregated_insights)} characters)"
                )
            
            # Step 6: Format and return result
            logger.info(f"[{trace_id}] Step 6: Formatting result")
            
            # Count unique videos analyzed
            unique_videos = set(a.segment.video_id for a in analyses)
            
            metadata = {
                "correlation_id": trace_id,
                "video_count": len(video_s3_uris),
                "videos_analyzed": len(unique_videos),
                "segments_analyzed": len(analyses),
                "intent_needs_search": intent.needs_search,
                "intent_analysis_type": intent.analysis_type,
                "search_queries_used": len(plan.search_queries),
                "parallel_execution": plan.parallel_execution,
                "jockey_enabled": True
            }
            
            result = AnalysisResult(
                query=query,
                scope="index",
                scope_id=index_id,
                insights=aggregated_insights,
                analyzed_at=datetime.now(),
                metadata=metadata
            )
            
            logger.info(
                f"[{trace_id}] Jockey orchestration completed successfully - "
                f"analyzed {len(analyses)} segments from {len(unique_videos)} videos"
            )
            
            return result
            
        except AnalysisCancelledError:
            # Re-raise cancellation errors
            logger.info(f"[{trace_id}] Analysis cancelled by user")
            raise
        except ValueError as e:
            # Re-raise validation errors
            logger.error(f"[{trace_id}] Validation error: {e}")
            raise
        except Exception as e:
            # Log and wrap unexpected errors
            logger.error(
                f"[{trace_id}] Orchestration failed with unexpected error: {e}",
                exc_info=True
            )
            raise AWSServiceError(
                f"Index analysis orchestration failed: {str(e)}"
            ) from e
    
    def _create_representative_segments(
        self,
        video_s3_uris: List[str],
        max_segments: int
    ) -> List[VideoSegment]:
        """Create representative video segments as fallback when search returns no results.
        
        This fallback strategy selects videos evenly distributed across the index
        to provide a representative sample for analysis.
        
        Args:
            video_s3_uris: List of S3 URIs for all videos in the index
            max_segments: Maximum number of segments to create
        
        Returns:
            List of VideoSegment objects representing full videos
        """
        # Select evenly distributed videos
        num_videos = min(max_segments, len(video_s3_uris))
        
        if num_videos == len(video_s3_uris):
            # Use all videos
            selected_uris = video_s3_uris
        else:
            # Select evenly distributed videos
            step = len(video_s3_uris) / num_videos
            selected_uris = [
                video_s3_uris[int(i * step)]
                for i in range(num_videos)
            ]
        
        # Create VideoSegment objects for full videos
        # Use video URI as video_id (extract from S3 URI)
        segments = []
        for uri in selected_uris:
            # Extract video ID from S3 URI (last part of path)
            video_id = uri.split('/')[-1].split('.')[0] if '/' in uri else uri
            
            segment = VideoSegment(
                video_id=video_id,
                s3_uri=uri,
                start_time=0.0,
                end_time=0.0,  # 0.0 indicates full video
                relevance_score=0.5  # Neutral score for representative videos
            )
            segments.append(segment)
        
        logger.debug(
            f"Created {len(segments)} representative segments from "
            f"{len(video_s3_uris)} videos"
        )
        
        return segments
    
    def _deduplicate_segments_by_video(
        self,
        segments: List[VideoSegment]
    ) -> List[VideoSegment]:
        """Deduplicate segments by video, keeping the highest relevance score for each video.
        
        Since Pegasus analyzes entire videos regardless of segment timing, we should
        only analyze each unique video once. This method keeps the segment with the
        highest relevance score for each unique video (based on s3_uri).
        
        Args:
            segments: List of VideoSegment objects (may contain multiple segments from same video)
        
        Returns:
            List of VideoSegment objects with one segment per unique video
        """
        if not segments:
            return segments
        
        # Group segments by s3_uri and keep the one with highest relevance score
        video_segments = {}
        
        for segment in segments:
            uri = segment.s3_uri
            
            if uri not in video_segments:
                video_segments[uri] = segment
            else:
                # Keep segment with higher relevance score
                if segment.relevance_score > video_segments[uri].relevance_score:
                    video_segments[uri] = segment
        
        deduplicated = list(video_segments.values())
        
        if len(deduplicated) < len(segments):
            logger.info(
                f"Deduplicated {len(segments)} segments to {len(deduplicated)} unique videos"
            )
        
        return deduplicated
    
    def _format_raw_insights(self, analyses: List) -> str:
        """Format raw insights as fallback when aggregation fails.
        
        This fallback strategy returns the individual insights without synthesis,
        preserving all information even if Claude aggregation fails.
        
        Args:
            analyses: List of SegmentAnalysis objects
        
        Returns:
            Formatted string with raw insights and source attribution
        """
        lines = [
            "# Analysis Results\n",
            f"Analyzed {len(analyses)} video segments:\n"
        ]
        
        for i, analysis in enumerate(analyses):
            seg = analysis.segment
            lines.append(
                f"\n## Video {i+1}: {seg.video_id}\n"
                f"**Timestamp:** {seg.start_time:.1f}s - {seg.end_time:.1f}s\n"
                f"**Relevance Score:** {seg.relevance_score:.3f}\n\n"
                f"{analysis.insights}\n"
            )
        
        # Add summary
        unique_videos = set(a.segment.video_id for a in analyses)
        lines.append(
            f"\n---\n"
            f"*Analyzed {len(analyses)} segments from {len(unique_videos)} video(s)*"
        )
        
        return "".join(lines)

