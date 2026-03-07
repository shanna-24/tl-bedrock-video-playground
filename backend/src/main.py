"""Main FastAPI application for TL-Video-Playground.

This module sets up the FastAPI application with CORS configuration,
startup/shutdown event handlers, AWS client initialization, and dependency injection.

Validates: Requirements 6.1, 8.1
"""

import logging
import os
import signal
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import Config, load_config
from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from aws.s3_vectors_client import S3VectorsClient
from services.auth_service import AuthService
from services.index_manager import IndexManager
from services.video_service import VideoService
from services.search_service import SearchService
from services.analysis_service import AnalysisService
from services.compliance_service import ComplianceService
from services.video_reel_service import VideoReelService
from services.embedding_job_processor import EmbeddingJobProcessor, EmbeddingJobProcessorConfig
from services.embedding_job_store import EmbeddingJobStore
from services.transcription_job_processor import TranscriptionJobProcessor
from services.websocket_manager import WebSocketManager
from storage.metadata_store import IndexMetadataStore
from utils.compliance_config_loader import ensure_compliance_config_in_s3
from exceptions import ConfigurationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global state for services (initialized during startup)
class AppState:
    """Application state container for services and clients."""
    
    config: Optional[Config] = None
    bedrock_client: Optional[BedrockClient] = None
    s3_client: Optional[S3Client] = None
    s3_vectors_client: Optional[S3VectorsClient] = None
    auth_service: Optional[AuthService] = None
    index_manager: Optional[IndexManager] = None
    video_service: Optional[VideoService] = None
    search_service: Optional[SearchService] = None
    analysis_service: Optional[AnalysisService] = None
    compliance_service: Optional[ComplianceService] = None
    video_reel_service: Optional[VideoReelService] = None
    metadata_store: Optional[IndexMetadataStore] = None
    embedding_job_store: Optional[EmbeddingJobStore] = None
    embedding_job_processor: Optional[EmbeddingJobProcessor] = None
    transcription_job_processor: Optional['TranscriptionJobProcessor'] = None
    websocket_manager: Optional[WebSocketManager] = None


app_state = AppState()


def _signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals (SIGTERM, SIGINT).
    
    This handler ensures graceful shutdown of background processors
    when the application receives termination signals. This is particularly
    important in production deployments (e.g., Docker, Kubernetes) where
    SIGTERM is sent before forceful termination.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name} signal, initiating graceful shutdown...")
    
    # Stop the embedding job processor if it's running
    if app_state.embedding_job_processor and app_state.embedding_job_processor.is_running():
        logger.info("Stopping embedding job processor due to signal...")
        app_state.embedding_job_processor.stop()
        logger.info("Embedding job processor stopped")
    
    # Stop the transcription job processor if it's running
    if app_state.transcription_job_processor:
        logger.info("Stopping transcription job processor due to signal...")
        app_state.transcription_job_processor.stop()
        logger.info("Transcription job processor stopped")
    
    logger.info(f"Signal handler for {signal_name} completed")


# Register signal handlers for graceful shutdown
# These handlers work in conjunction with FastAPI's lifespan context manager
# to ensure clean shutdown in production environments
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)
logger.info("Signal handlers registered for SIGTERM and SIGINT")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events.
    
    This function handles:
    - Loading configuration from config file
    - Initializing AWS clients (Bedrock, S3, S3 Vectors)
    - Initializing services (Auth, Index Manager, Video, Search, Analysis)
    - Cleanup on shutdown
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None (context manager)
        
    Raises:
        ConfigurationError: If configuration loading or validation fails
    """
    # Startup
    logger.info("Starting TL-Video-Playground application...")
    
    try:
        # Load configuration
        config_path = os.getenv("CONFIG_PATH", None)
        logger.info(f"Loading configuration from: {config_path or 'default location'}")
        
        try:
            app_state.config = load_config(config_path)
            app_state.config.validate()
            logger.info(
                f"Configuration loaded successfully "
                f"(environment: {app_state.config.environment})"
            )
        except FileNotFoundError as e:
            logger.error(f"Configuration file not found: {e}")
            raise ConfigurationError(
                "Configuration file not found. Please create a config.yaml file "
                "with required settings (marengo_model_id, pegasus_model_id, "
                "aws_region, s3_bucket_name, auth_password_hash)."
            ) from e
        except ValueError as e:
            logger.error(f"Invalid configuration: {e}")
            raise ConfigurationError(
                f"Invalid configuration: {e}. Please check your config.yaml file."
            ) from e
        
        # Initialize AWS clients first (needed for metadata stores)
        logger.info("Initializing AWS clients...")
        
        try:
            # Initialize Bedrock client
            app_state.bedrock_client = BedrockClient(app_state.config)
            logger.info("Bedrock client initialized")
            
            # Initialize S3 client
            app_state.s3_client = S3Client(app_state.config)
            logger.info("S3 client initialized")
            
            # Initialize S3 Vectors client
            app_state.s3_vectors_client = S3VectorsClient(app_state.config)
            logger.info("S3 Vectors client initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise ConfigurationError(
                f"Failed to initialize AWS clients: {e}. "
                "Please check your AWS credentials and configuration."
            ) from e
        
        # Initialize metadata store (uses S3)
        logger.info("Initializing metadata store...")
        app_state.metadata_store = IndexMetadataStore(
            s3_client=app_state.s3_client.client,
            bucket_name=app_state.config.s3_bucket_name
        )
        logger.info(f"Metadata store initialized with S3: s3://{app_state.config.s3_bucket_name}/metadata/")
        
        # Initialize embedding job store (uses S3)
        logger.info("Initializing embedding job store...")
        app_state.embedding_job_store = EmbeddingJobStore(
            s3_client=app_state.s3_client.client,
            bucket_name=app_state.config.s3_bucket_name
        )
        logger.info("Embedding job store initialized")
        
        # Initialize services
        logger.info("Initializing services...")
        
        # Auth service
        jwt_secret = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
        app_state.auth_service = AuthService(
            config=app_state.config,
            secret_key=jwt_secret
        )
        logger.info("Auth service initialized")
        
        # Index manager (now with job store)
        app_state.index_manager = IndexManager(
            bedrock_client=app_state.bedrock_client,
            s3_vectors_client=app_state.s3_vectors_client,
            config=app_state.config,
            metadata_store=app_state.metadata_store,
            embedding_job_store=app_state.embedding_job_store
        )
        logger.info("Index manager initialized")
        
        # Video service
        app_state.video_service = VideoService(
            s3_client=app_state.s3_client,
            config=app_state.config
        )
        logger.info("Video service initialized")
        
        # Search service
        app_state.search_service = SearchService(
            bedrock_client=app_state.bedrock_client,
            s3_vectors_client=app_state.s3_vectors_client,
            s3_client=app_state.s3_client,
            config=app_state.config,
            index_manager=app_state.index_manager
        )
        logger.info("Search service initialized")
        
        # Analysis service
        app_state.analysis_service = AnalysisService(
            bedrock_client=app_state.bedrock_client,
            s3_client=app_state.s3_client,
            config=app_state.config,
            search_service=app_state.search_service
        )
        logger.info("Analysis service initialized")
        
        # Ensure compliance config files exist in S3 (auto-upload if missing)
        logger.info("Checking compliance configuration in S3...")
        try:
            compliance_sync_result = ensure_compliance_config_in_s3(
                s3_client=app_state.s3_client.client,
                bucket_name=app_state.config.s3_bucket_name
            )
            if compliance_sync_result['uploaded'] > 0:
                logger.info(f"Uploaded {compliance_sync_result['uploaded']} compliance config files to S3")
        except Exception as e:
            logger.warning(f"Failed to sync compliance config to S3: {e}. Compliance feature may not work.")
        
        # Compliance service
        app_state.compliance_service = ComplianceService(
            bedrock_client=app_state.bedrock_client,
            s3_client=app_state.s3_client,
            config=app_state.config,
            search_service=app_state.search_service
        )
        logger.info("Compliance service initialized")
        
        # Video reel service
        app_state.video_reel_service = VideoReelService(
            s3_client=app_state.s3_client,
            config=app_state.config
        )
        logger.info("Video reel service initialized")
        
        # Initialize WebSocket manager
        logger.info("Initializing WebSocket manager...")
        app_state.websocket_manager = WebSocketManager()
        logger.info("WebSocket manager initialized")
        
        # Initialize embedding job processor
        logger.info("Initializing embedding job processor...")
        processor_config = EmbeddingJobProcessorConfig(
            poll_interval=app_state.config.embedding_processor.polling_interval,
            max_concurrent_jobs=app_state.config.embedding_processor.max_concurrent_jobs,
            max_retries=app_state.config.embedding_processor.max_retries,
            retry_backoff=app_state.config.embedding_processor.retry_backoff_base,
            enabled=app_state.config.embedding_processor.enabled
        )
        
        app_state.embedding_job_processor = EmbeddingJobProcessor(
            config=app_state.config,
            bedrock_client=app_state.bedrock_client,
            s3_client=app_state.s3_client,
            s3_vectors_client=app_state.s3_vectors_client,
            job_store=app_state.embedding_job_store,
            processor_config=processor_config,
            websocket_manager=app_state.websocket_manager
        )
        logger.info("Embedding job processor initialized")
        
        # Start the embedding job processor if enabled
        if app_state.config.embedding_processor.enabled:
            logger.info("Starting embedding job processor...")
            app_state.embedding_job_processor.start()
            logger.info("Embedding job processor started successfully")
            logger.info("Note: Processor will also generate aligned transcriptions after embeddings complete")
        else:
            logger.info("Embedding job processor is disabled in configuration")
        
        # Initialize and start transcription job processor
        # NOTE: Disabled because we now use Pegasus for transcription (synchronous)
        # Pegasus generates transcriptions immediately during video upload
        logger.info("Transcription job processor disabled (using Pegasus synchronous transcription)")
        app_state.transcription_job_processor = None
        
        # Uncomment below if switching back to AWS Transcribe (async)
        # logger.info("Initializing transcription job processor...")
        # app_state.transcription_job_processor = TranscriptionJobProcessor(
        #     config=app_state.config,
        #     poll_interval=60,
        #     enabled=True
        # )
        # app_state.transcription_job_processor.start()
        # logger.info("Transcription job processor started successfully")
        
        # Set up routers with dependency injection (must be done after services are initialized)
        from api import indexes, search, analysis, compliance, videos, health, websocket, video_reel
        
        indexes.set_index_manager(app_state.index_manager)
        indexes.set_video_service(app_state.video_service)
        indexes.set_s3_client(app_state.s3_client)
        
        search.set_search_service(app_state.search_service)
        
        analysis.set_analysis_service(app_state.analysis_service)
        analysis.set_index_manager(app_state.index_manager)
        analysis.set_websocket_manager(app_state.websocket_manager)
        
        compliance.set_compliance_service(app_state.compliance_service)
        compliance.set_index_manager(app_state.index_manager)
        compliance.set_websocket_manager(app_state.websocket_manager)
        
        videos.set_video_service(app_state.video_service)
        videos.set_index_manager(app_state.index_manager)
        videos.set_s3_client(app_state.s3_client)
        
        video_reel.set_video_reel_service(app_state.video_reel_service)
        
        health.set_dependencies(
            app_state.embedding_job_processor,
            app_state.embedding_job_store,
            app_state.config,
            app_state.websocket_manager
        )
        
        # Import and set up embedding jobs router
        from api import embedding_jobs
        embedding_jobs.set_embedding_job_store(app_state.embedding_job_store)
        
        # Set up WebSocket router
        websocket.set_websocket_manager(app_state.websocket_manager)
        
        logger.info("TL-Video-Playground application started successfully!")
        
        yield
        
    except ConfigurationError:
        # Re-raise configuration errors to prevent startup
        raise
    except Exception as e:
        logger.error(f"Unexpected error during startup: {e}")
        raise ConfigurationError(
            f"Failed to start application: {e}"
        ) from e
    
    # Shutdown
    logger.info("Shutting down TL-Video-Playground application...")
    
    # Stop the embedding job processor if it's running
    if app_state.embedding_job_processor and app_state.embedding_job_processor.is_running():
        logger.info("Stopping embedding job processor...")
        app_state.embedding_job_processor.stop()
        logger.info("Embedding job processor stopped")
    
    # Stop the transcription job processor if it's running
    if app_state.transcription_job_processor:
        logger.info("Stopping transcription job processor...")
        app_state.transcription_job_processor.stop()
        logger.info("Transcription job processor stopped")
    
    # Cleanup resources if needed
    # (AWS clients handle their own cleanup)
    
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="TwelveLabs on Amazon Bedrock",
    description="Video archive search and analysis system using TwelveLabs AI models",
    version="1.0.0",
    lifespan=lifespan
)


# Configure CORS
# In production, replace "*" with specific frontend domain
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS configured with origins: {cors_origins}")


# Dependency injection functions
def get_config() -> Config:
    """Get the application configuration.
    
    Returns:
        Config instance
        
    Raises:
        RuntimeError: If configuration is not initialized
    """
    if app_state.config is None:
        raise RuntimeError("Configuration not initialized")
    return app_state.config


def get_auth_service() -> AuthService:
    """Get the authentication service.
    
    Returns:
        AuthService instance
        
    Raises:
        RuntimeError: If auth service is not initialized
    """
    if app_state.auth_service is None:
        raise RuntimeError("Auth service not initialized")
    return app_state.auth_service


def get_index_manager() -> IndexManager:
    """Get the index manager service.
    
    Returns:
        IndexManager instance
        
    Raises:
        RuntimeError: If index manager is not initialized
    """
    if app_state.index_manager is None:
        raise RuntimeError("Index manager not initialized")
    return app_state.index_manager


def get_video_service() -> VideoService:
    """Get the video service.
    
    Returns:
        VideoService instance
        
    Raises:
        RuntimeError: If video service is not initialized
    """
    if app_state.video_service is None:
        raise RuntimeError("Video service not initialized")
    return app_state.video_service


def get_search_service() -> SearchService:
    """Get the search service.
    
    Returns:
        SearchService instance
        
    Raises:
        RuntimeError: If search service is not initialized
    """
    if app_state.search_service is None:
        raise RuntimeError("Search service not initialized")
    return app_state.search_service


def get_s3_client() -> S3Client:
    """Get the S3 client.
    
    Returns:
        S3Client instance
        
    Raises:
        RuntimeError: If S3 client is not initialized
    """
    if app_state.s3_client is None:
        raise RuntimeError("S3 client not initialized")
    return app_state.s3_client


def get_analysis_service() -> AnalysisService:
    """Get the analysis service.
    
    Returns:
        AnalysisService instance
        
    Raises:
        RuntimeError: If analysis service is not initialized
    """
    if app_state.analysis_service is None:
        raise RuntimeError("Analysis service not initialized")
    return app_state.analysis_service


def get_embedding_job_store() -> EmbeddingJobStore:
    """Get the embedding job store.
    
    Returns:
        EmbeddingJobStore instance
        
    Raises:
        RuntimeError: If embedding job store is not initialized
    """
    if app_state.embedding_job_store is None:
        raise RuntimeError("Embedding job store not initialized")
    return app_state.embedding_job_store


def get_embedding_job_processor() -> EmbeddingJobProcessor:
    """Get the embedding job processor.
    
    Returns:
        EmbeddingJobProcessor instance
        
    Raises:
        RuntimeError: If embedding job processor is not initialized
    """
    if app_state.embedding_job_processor is None:
        raise RuntimeError("Embedding job processor not initialized")
    return app_state.embedding_job_processor


def get_websocket_manager() -> WebSocketManager:
    """Get the WebSocket manager.
    
    Returns:
        WebSocketManager instance
        
    Raises:
        RuntimeError: If WebSocket manager is not initialized
    """
    if app_state.websocket_manager is None:
        raise RuntimeError("WebSocket manager not initialized")
    return app_state.websocket_manager


# Root endpoint - serves frontend if available, otherwise API info
@app.get("/")
async def root():
    """Root endpoint - serves frontend or API information.
    
    Returns:
        FileResponse for frontend or dict for API info
    """
    # Check if static frontend exists (Docker deployment)
    static_dir = Path(__file__).parent.parent / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    
    # Fallback to API info for development
    return {
        "name": "TL-Video-Playground API",
        "version": "1.0.0",
        "description": "Video archive search and analysis system using TwelveLabs AI models",
        "docs_url": "/docs"
    }


# Import and include API routers
from api import auth, indexes, search, analysis, compliance, videos, health, embedding_jobs, websocket, config, video_reel

# Include routers (dependency injection happens in lifespan)
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(config.router, prefix="/api/config", tags=["configuration"])
app.include_router(indexes.router, prefix="/api/indexes", tags=["indexes"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(analysis.router, prefix="/api/analyze", tags=["analysis"])
app.include_router(compliance.router, prefix="/api/compliance", tags=["compliance"])
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(video_reel.router, prefix="/api/video-reel", tags=["video-reel"])
app.include_router(embedding_jobs.router, prefix="/api/embedding-jobs", tags=["embedding-jobs"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


# Serve static frontend files (for Docker deployment)
# Check if static directory exists (only in Docker builds)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    
    # Catch-all route for SPA - serve index.html for any non-API route
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA frontend for any non-API routes."""
        # Don't serve index.html for API routes
        if full_path.startswith("api/") or full_path.startswith("ws/") or full_path == "docs" or full_path == "openapi.json":
            return None
        
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"error": "Frontend not found"}
    
    logger.info(f"Static frontend files mounted from {static_dir}")


if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    # In production, use a proper ASGI server like gunicorn with uvicorn workers
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    )
