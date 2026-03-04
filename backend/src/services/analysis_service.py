"""Analysis service for video content analysis using Pegasus model.

This module provides the AnalysisService class for analyzing video content
using natural language queries with the TwelveLabs Pegasus model.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3
"""

import logging
from datetime import datetime
from typing import List, Optional

from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from config import Config
from models.analysis import AnalysisResult
from exceptions import BedrockError, AWSServiceError, AnalysisCancelledError

logger = logging.getLogger(__name__)


class AnalysisService:
    """Handles video content analysis using Pegasus model.
    
    This service uses the Pegasus model to analyze video content and generate
    insights based on natural language queries. It supports both index-level
    analysis (analyzing all videos in an index) and video-level analysis
    (analyzing a single video).
    
    For index-level analysis, the service can use either:
    1. JockeyOrchestrator (when enabled) - Multi-video RAG-based analysis
    2. Legacy implementation - Single video placeholder analysis
    
    Attributes:
        bedrock: BedrockClient for Pegasus model invocation
        s3: S3Client for accessing video files
        config: Configuration object
        orchestrator: JockeyOrchestrator for multi-video analysis (optional)
    """
    
    def __init__(
        self,
        bedrock_client: BedrockClient,
        s3_client: S3Client,
        config: Config,
        search_service: Optional['SearchService'] = None
    ):
        """Initialize the AnalysisService.
        
        Args:
            bedrock_client: Client for Bedrock API (Pegasus model)
            s3_client: Client for S3 API
            config: Configuration object
            search_service: SearchService for Jockey orchestration (optional)
        """
        self.bedrock = bedrock_client
        self.s3 = s3_client
        self.config = config
        self.orchestrator = None
        
        # Initialize JockeyOrchestrator if enabled and search_service provided
        if config.jockey.enabled and search_service is not None:
            try:
                from orchestration.orchestrator import JockeyOrchestrator
                self.orchestrator = JockeyOrchestrator(
                    bedrock_client=bedrock_client,
                    search_service=search_service,
                    s3_client=s3_client,
                    config=config
                )
                logger.info("Initialized AnalysisService with JockeyOrchestrator enabled")
            except ImportError as e:
                logger.error(
                    f"Failed to import JockeyOrchestrator: {e}. "
                    "Falling back to legacy implementation",
                    exc_info=True
                )
            except Exception as e:
                logger.error(
                    f"Failed to initialize JockeyOrchestrator: {e}. "
                    "Falling back to legacy implementation",
                    exc_info=True
                )
        else:
            if not config.jockey.enabled:
                logger.info("Initialized AnalysisService with JockeyOrchestrator disabled")
            else:
                logger.info("Initialized AnalysisService without SearchService (legacy mode)")
        
        if self.orchestrator is None:
            logger.info("Initialized AnalysisService in legacy mode")
    
    async def analyze_index(
        self,
        index_id: str,
        query: str,
        video_s3_uris: List[str],
        verbosity: str = "concise",
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        progress_callback: Optional[callable] = None,
        correlation_id: Optional[str] = None
    ) -> AnalysisResult:
        """Analyze all videos in an index using natural language query.
        
        This method analyzes all videos in an index. When JockeyOrchestrator
        is enabled, it uses a RAG-based approach with semantic search and
        multi-video analysis. Otherwise, it falls back to the legacy
        implementation that analyzes only the first video.
        
        Args:
            index_id: ID of the index to analyze
            query: Natural language analysis query
            video_s3_uris: List of S3 URIs for videos in the index
            verbosity: Response verbosity level ('concise' or 'extended')
            temperature: Temperature for randomness (0-1, default: 0.2)
            max_output_tokens: Maximum tokens to generate (max: 4096)
            progress_callback: Optional async callback for progress updates
            correlation_id: Optional correlation ID for cancellation tracking
        
        Returns:
            AnalysisResult object containing the analysis insights
        
        Raises:
            BedrockError: If Pegasus model invocation fails
            ValueError: If query is empty or no videos in index
            AnalysisCancelledError: If the analysis is cancelled by the user
        """
        if not query or not query.strip():
            raise ValueError("Analysis query cannot be empty")
        
        if not video_s3_uris:
            raise ValueError("No videos found in index for analysis")
        
        logger.info(
            f"Analyzing index {index_id} with {len(video_s3_uris)} videos, "
            f"query: {query[:50]}..."
        )
        
        # Debug logging - CRITICAL for troubleshooting
        logger.info(f"=" * 80)
        logger.info(f"ANALYSIS DEBUG INFO:")
        logger.info(f"  orchestrator is None: {self.orchestrator is None}")
        logger.info(f"  orchestrator type: {type(self.orchestrator)}")
        logger.info(f"  orchestrator value: {self.orchestrator}")
        logger.info(f"  jockey.enabled: {self.config.jockey.enabled}")
        logger.info(f"  index_id: {index_id}")
        logger.info(f"  video_count: {len(video_s3_uris)}")
        logger.info(f"=" * 80)
        
        # Use JockeyOrchestrator if available, otherwise fall back to legacy
        if self.orchestrator is not None:
            logger.info(f"Using JockeyOrchestrator for index {index_id}")
            try:
                return await self.orchestrator.analyze_index(
                    index_id=index_id,
                    query=query,
                    video_s3_uris=video_s3_uris,
                    verbosity=verbosity,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    progress_callback=progress_callback,
                    correlation_id=correlation_id
                )
            except AnalysisCancelledError:
                # Re-raise cancellation errors - don't fall back to legacy
                raise
            except Exception as e:
                logger.error(
                    f"JockeyOrchestrator failed for index {index_id}: {e}. "
                    "Falling back to legacy implementation",
                    exc_info=True  # Include full traceback
                )
                # Fall through to legacy implementation
        else:
            logger.warning(
                f"JockeyOrchestrator is None for index {index_id}. "
                "Using legacy implementation."
            )
        
        # Legacy implementation: analyze first video as representative
        logger.info(f"Using legacy implementation for index {index_id}")
        
        try:
            # For index-level analysis, we analyze the first video as a representative
            # In a full implementation, this could:
            # 1. Analyze all videos and aggregate results
            # 2. Use a multi-video analysis API if available
            # 3. Sample representative videos from the index
            
            # For now, analyze the first video with context about the index
            primary_video_uri = video_s3_uris[0]
            
            # Enhance the query with index context and verbosity instruction
            verbosity_instructions = {
                "concise": "Provide a brief, focused response with key insights only.",
                "balanced": "Provide a well-rounded response covering key insights in 3-5 paragraphs.",
                "extended": "Provide a detailed, comprehensive analysis with thorough explanations and examples."
            }
            verbosity_instruction = verbosity_instructions.get(verbosity, verbosity_instructions["balanced"])
            
            enhanced_query = (
                f"This video is part of an index containing {len(video_s3_uris)} videos. "
                f"{verbosity_instruction}\n\n"
                f"Query: {query}"
            )
            
            # Invoke Pegasus model
            raw_result = await self._invoke_pegasus(
                video_uri=primary_video_uri,
                query=enhanced_query,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )
            
            # Format the result
            metadata = {
                "video_count": len(video_s3_uris),
                "analyzed_video_uri": primary_video_uri,
                "jockey_enabled": False
            }
            
            analysis_result = self._format_analysis_result(
                raw_result=raw_result,
                query=query,
                scope="index",
                scope_id=index_id,
                metadata=metadata
            )
            
            logger.info(f"Completed index analysis for {index_id}")
            
            return analysis_result
            
        except BedrockError as e:
            logger.error(f"Failed to analyze index: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during index analysis: {e}")
            raise AWSServiceError(f"Index analysis failed: {str(e)}") from e
    
    async def analyze_video(
        self,
        video_id: str,
        query: str,
        video_s3_uri: str,
        verbosity: str = "concise",
        use_jockey: bool = False,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        progress_callback: Optional[callable] = None,
        correlation_id: Optional[str] = None
    ) -> AnalysisResult:
        """Analyze a single video using natural language query.
        
        This method analyzes a specific video. When use_jockey is True, it performs
        standalone Pegasus analysis on the entire video and feeds the output to the
        Claude reasoning model for enhanced insights. When use_jockey is False, it
        performs standalone Pegasus analysis and presents the output directly.
        
        Args:
            video_id: ID of the video to analyze
            query: Natural language analysis query
            video_s3_uri: S3 URI of the video
            verbosity: Response verbosity level ('concise' or 'extended')
            use_jockey: Whether to use Jockey orchestration for enhanced analysis
            temperature: Temperature for randomness (0-1, default: 0.2)
            max_output_tokens: Maximum tokens to generate (max: 4096)
            progress_callback: Optional async callback for progress updates
            correlation_id: Optional correlation ID for cancellation tracking
        
        Returns:
            AnalysisResult object containing the analysis insights
        
        Raises:
            BedrockError: If Pegasus model invocation fails
            ValueError: If query is empty or video URI is invalid
            AnalysisCancelledError: If the analysis is cancelled by the user
        """
        if not query or not query.strip():
            raise ValueError("Analysis query cannot be empty")
        
        if not video_s3_uri or not video_s3_uri.startswith("s3://"):
            raise ValueError("Invalid video S3 URI")
        
        logger.info(
            f"Analyzing video {video_id}, query: {query[:50]}... (use_jockey={use_jockey})"
        )
        
        try:
            # If use_jockey is True and orchestrator is available, use Jockey orchestration
            if use_jockey and self.orchestrator is not None:
                logger.info(f"Using Jockey orchestration for single video {video_id}")
                
                if progress_callback:
                    await progress_callback("Analyzing video content...")
                
                # For single video with Jockey, bypass segment search and go straight to Pegasus analysis
                # This performs Pegasus analysis and feeds output to Claude reasoning model
                return await self.orchestrator.analyze_single_video(
                    video_id=video_id,
                    query=query,
                    video_s3_uri=video_s3_uri,
                    verbosity=verbosity,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    progress_callback=progress_callback,
                    correlation_id=correlation_id
                )
            
            # Standalone Pegasus analysis (no Jockey)
            logger.info(f"Using standalone Pegasus analysis for video {video_id}")
            
            if progress_callback:
                await progress_callback("Analyzing video content...")
            
            # Add verbosity instruction to the query
            verbosity_instructions = {
                "concise": "Provide a brief, focused response with key insights only.",
                "balanced": "Provide a well-rounded response covering key insights in 3-5 paragraphs.",
                "extended": "Provide a detailed, comprehensive analysis with thorough explanations and examples."
            }
            verbosity_instruction = verbosity_instructions.get(verbosity, verbosity_instructions["balanced"])
            
            enhanced_query = f"{verbosity_instruction}\n\n{query}"
            
            # Invoke Pegasus model (synchronous - async not supported by Pegasus)
            raw_result = await self._invoke_pegasus(
                video_uri=video_s3_uri,
                query=enhanced_query,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )
            
            # Format the result
            metadata = {
                "video_s3_uri": video_s3_uri,
                "jockey_enabled": False,
                "use_jockey_requested": use_jockey
            }
            
            analysis_result = self._format_analysis_result(
                raw_result=raw_result,
                query=query,
                scope="video",
                scope_id=video_id,
                metadata=metadata
            )
            
            logger.info(f"Completed video analysis for {video_id}")
            
            return analysis_result
            
        except AnalysisCancelledError:
            # Re-raise cancellation errors
            raise
        except BedrockError as e:
            logger.error(f"Failed to analyze video: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during video analysis: {e}")
            raise AWSServiceError(f"Video analysis failed: {str(e)}") from e
    
    async def _invoke_pegasus(
        self,
        video_uri: str,
        query: str,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None
    ) -> str:
        """Invoke Pegasus model for video analysis.
        
        Args:
            video_uri: S3 URI of the video
            query: Analysis query
            temperature: Temperature for randomness (0-1)
            max_output_tokens: Maximum tokens to generate
        
        Returns:
            Raw analysis text from Pegasus model
        
        Raises:
            BedrockError: If model invocation fails
        """
        try:
            logger.debug(f"Invoking Pegasus for video: {video_uri}")
            
            # Invoke Pegasus model directly without EDL instructions
            # Note: Pegasus is a video analysis model, not a video editing tool.
            # EDL generation should be handled separately after analysis.
            result = self.bedrock.invoke_pegasus_analysis(
                s3_uri=video_uri,
                prompt=query,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )
            
            # Extract message from result
            message = result.get("message", "")
            finish_reason = result.get("finishReason", "unknown")
            
            if not message:
                raise BedrockError("Pegasus returned empty analysis result")
            
            logger.debug(
                f"Pegasus analysis completed (finish reason: {finish_reason})"
            )
            
            return message
            
        except BedrockError as e:
            logger.error(f"Failed to invoke Pegasus: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error invoking Pegasus: {e}")
            raise BedrockError(f"Failed to invoke Pegasus: {str(e)}") from e
    
    def _format_analysis_result(
        self,
        raw_result: str,
        query: str,
        scope: str,
        scope_id: str,
        metadata: dict
    ) -> AnalysisResult:
        """Format raw analysis result into structured AnalysisResult object.
        
        Args:
            raw_result: Raw analysis text from Pegasus
            query: Original analysis query
            scope: Analysis scope ("index" or "video")
            scope_id: ID of the index or video
            metadata: Additional metadata to include
        
        Returns:
            AnalysisResult object with formatted insights
        """
        try:
            # Create AnalysisResult object
            analysis_result = AnalysisResult(
                query=query,
                scope=scope,
                scope_id=scope_id,
                insights=raw_result,
                analyzed_at=datetime.now(),
                metadata=metadata
            )
            
            logger.debug(f"Formatted analysis result for {scope} {scope_id}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Failed to format analysis result: {e}")
            raise ValueError(f"Failed to format analysis result: {str(e)}") from e
    

