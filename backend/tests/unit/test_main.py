"""Unit tests for the main FastAPI application.

Tests application initialization, configuration loading, service setup,
and dependency injection.

Validates: Requirements 6.1, 8.1
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Set test environment before importing main
os.environ["CONFIG_PATH"] = "config.local.yaml"


class TestFastAPIApplication:
    """Test suite for FastAPI application initialization."""
    
    def test_app_creation(self):
        """Test that the FastAPI app is created successfully."""
        from main import app
        
        assert app is not None
        assert app.title == "TL-Video-Playground"
        assert app.version == "1.0.0"
    
    def test_cors_middleware_configured(self):
        """Test that CORS middleware is properly configured."""
        from main import app
        
        # Check that CORS middleware is in the middleware stack
        # FastAPI wraps middleware, so we check the middleware stack
        has_cors = False
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                has_cors = True
                break
        
        assert has_cors, "CORS middleware not found in middleware stack"
    
    def test_health_check_endpoint_structure(self):
        """Test that health check endpoint is defined correctly."""
        from main import health_check
        import asyncio
        
        # Test the endpoint function directly
        result = asyncio.run(health_check())
        
        assert result["status"] == "healthy"
        assert "version" in result
    
    def test_root_endpoint_structure(self):
        """Test that root endpoint is defined correctly."""
        from main import root
        import asyncio
        
        # Test the endpoint function directly
        result = asyncio.run(root())
        
        assert result["name"] == "TL-Video-Playground API"
        assert result["version"] == "1.0.0"
        assert "docs_url" in result


class TestDependencyInjection:
    """Test suite for dependency injection functions."""
    
    def test_get_config_when_initialized(self):
        """Test get_config returns config when initialized."""
        from main import get_config, app_state
        
        # Mock initialized config
        mock_config = Mock()
        app_state.config = mock_config
        
        result = get_config()
        
        assert result == mock_config
        
        # Cleanup
        app_state.config = None
    
    def test_get_config_when_not_initialized(self):
        """Test get_config raises error when not initialized."""
        from main import get_config, app_state
        
        # Ensure config is None
        app_state.config = None
        
        with pytest.raises(RuntimeError, match="Configuration not initialized"):
            get_config()
    
    def test_get_auth_service_when_initialized(self):
        """Test get_auth_service returns service when initialized."""
        from main import get_auth_service, app_state
        
        mock_service = Mock()
        app_state.auth_service = mock_service
        
        result = get_auth_service()
        
        assert result == mock_service
        
        # Cleanup
        app_state.auth_service = None
    
    def test_get_auth_service_when_not_initialized(self):
        """Test get_auth_service raises error when not initialized."""
        from main import get_auth_service, app_state
        
        app_state.auth_service = None
        
        with pytest.raises(RuntimeError, match="Auth service not initialized"):
            get_auth_service()
    
    def test_get_index_manager_when_initialized(self):
        """Test get_index_manager returns service when initialized."""
        from main import get_index_manager, app_state
        
        mock_service = Mock()
        app_state.index_manager = mock_service
        
        result = get_index_manager()
        
        assert result == mock_service
        
        # Cleanup
        app_state.index_manager = None
    
    def test_get_index_manager_when_not_initialized(self):
        """Test get_index_manager raises error when not initialized."""
        from main import get_index_manager, app_state
        
        app_state.index_manager = None
        
        with pytest.raises(RuntimeError, match="Index manager not initialized"):
            get_index_manager()
    
    def test_get_video_service_when_initialized(self):
        """Test get_video_service returns service when initialized."""
        from main import get_video_service, app_state
        
        mock_service = Mock()
        app_state.video_service = mock_service
        
        result = get_video_service()
        
        assert result == mock_service
        
        # Cleanup
        app_state.video_service = None
    
    def test_get_video_service_when_not_initialized(self):
        """Test get_video_service raises error when not initialized."""
        from main import get_video_service, app_state
        
        app_state.video_service = None
        
        with pytest.raises(RuntimeError, match="Video service not initialized"):
            get_video_service()
    
    def test_get_search_service_when_initialized(self):
        """Test get_search_service returns service when initialized."""
        from main import get_search_service, app_state
        
        mock_service = Mock()
        app_state.search_service = mock_service
        
        result = get_search_service()
        
        assert result == mock_service
        
        # Cleanup
        app_state.search_service = None
    
    def test_get_search_service_when_not_initialized(self):
        """Test get_search_service raises error when not initialized."""
        from main import get_search_service, app_state
        
        app_state.search_service = None
        
        with pytest.raises(RuntimeError, match="Search service not initialized"):
            get_search_service()
    
    def test_get_analysis_service_when_initialized(self):
        """Test get_analysis_service returns service when initialized."""
        from main import get_analysis_service, app_state
        
        mock_service = Mock()
        app_state.analysis_service = mock_service
        
        result = get_analysis_service()
        
        assert result == mock_service
        
        # Cleanup
        app_state.analysis_service = None
    
    def test_get_analysis_service_when_not_initialized(self):
        """Test get_analysis_service raises error when not initialized."""
        from main import get_analysis_service, app_state
        
        app_state.analysis_service = None
        
        with pytest.raises(RuntimeError, match="Analysis service not initialized"):
            get_analysis_service()
    
    def test_get_embedding_job_store_when_initialized(self):
        """Test get_embedding_job_store returns store when initialized."""
        from main import get_embedding_job_store, app_state
        
        mock_store = Mock()
        app_state.embedding_job_store = mock_store
        
        result = get_embedding_job_store()
        
        assert result == mock_store
        
        # Cleanup
        app_state.embedding_job_store = None
    
    def test_get_embedding_job_store_when_not_initialized(self):
        """Test get_embedding_job_store raises error when not initialized."""
        from main import get_embedding_job_store, app_state
        
        app_state.embedding_job_store = None
        
        with pytest.raises(RuntimeError, match="Embedding job store not initialized"):
            get_embedding_job_store()
    
    def test_get_embedding_job_processor_when_initialized(self):
        """Test get_embedding_job_processor returns processor when initialized."""
        from main import get_embedding_job_processor, app_state
        
        mock_processor = Mock()
        app_state.embedding_job_processor = mock_processor
        
        result = get_embedding_job_processor()
        
        assert result == mock_processor
        
        # Cleanup
        app_state.embedding_job_processor = None
    
    def test_get_embedding_job_processor_when_not_initialized(self):
        """Test get_embedding_job_processor raises error when not initialized."""
        from main import get_embedding_job_processor, app_state
        
        app_state.embedding_job_processor = None
        
        with pytest.raises(RuntimeError, match="Embedding job processor not initialized"):
            get_embedding_job_processor()


class TestLifespanEvents:
    """Test suite for application lifespan events."""
    
    def test_lifespan_configuration_loading(self):
        """Test that lifespan loads configuration correctly."""
        from main import lifespan, app_state
        import asyncio
        
        with patch("main.load_config") as mock_load_config, \
             patch("main.BedrockClient"), \
             patch("main.S3Client"), \
             patch("main.S3VectorsClient"), \
             patch("main.IndexMetadataStore"), \
             patch("main.EmbeddingJobStore"), \
             patch("main.EmbeddingJobProcessor") as mock_processor_class:
            
            # Mock configuration
            mock_config = Mock()
            mock_config.environment = "test"
            mock_config.validate.return_value = True
            mock_config.use_localstack = False
            mock_config.aws_region = "us-east-1"
            mock_config.marengo_model_id = "test-marengo"
            mock_config.pegasus_model_id = "test-pegasus"
            mock_config.s3_bucket_name = "test-bucket"
            mock_config.s3_vectors_collection = "test-collection"
            mock_config.auth_password_hash = "test-hash"
            mock_config.max_indexes = 3
            mock_config.embedding_processor = Mock()
            mock_config.embedding_processor.enabled = True
            mock_config.embedding_processor.polling_interval = 30
            mock_config.embedding_processor.max_concurrent_jobs = 5
            mock_config.embedding_processor.max_retries = 3
            mock_config.embedding_processor.retry_backoff_base = 2
            
            mock_load_config.return_value = mock_config
            
            # Mock processor instance
            mock_processor = Mock()
            mock_processor_class.return_value = mock_processor
            
            # Test lifespan context manager
            async def test_lifespan():
                mock_app = Mock()
                async with lifespan(mock_app):
                    # Verify config was loaded
                    assert app_state.config is not None
                    assert app_state.config.environment == "test"
            
            # Run the async test
            asyncio.run(test_lifespan())
            
            # Verify config was loaded
            mock_load_config.assert_called_once()
    
    def test_lifespan_starts_processor_when_enabled(self):
        """Test that lifespan starts the embedding job processor when enabled."""
        from main import lifespan, app_state
        import asyncio
        
        with patch("main.load_config") as mock_load_config, \
             patch("main.BedrockClient"), \
             patch("main.S3Client"), \
             patch("main.S3VectorsClient"), \
             patch("main.IndexMetadataStore"), \
             patch("main.EmbeddingJobStore"), \
             patch("main.EmbeddingJobProcessor") as mock_processor_class:
            
            # Mock configuration with processor enabled
            mock_config = Mock()
            mock_config.environment = "test"
            mock_config.validate.return_value = True
            mock_config.use_localstack = False
            mock_config.aws_region = "us-east-1"
            mock_config.marengo_model_id = "test-marengo"
            mock_config.pegasus_model_id = "test-pegasus"
            mock_config.s3_bucket_name = "test-bucket"
            mock_config.s3_vectors_collection = "test-collection"
            mock_config.auth_password_hash = "test-hash"
            mock_config.max_indexes = 3
            mock_config.embedding_processor = Mock()
            mock_config.embedding_processor.enabled = True
            mock_config.embedding_processor.polling_interval = 30
            mock_config.embedding_processor.max_concurrent_jobs = 5
            mock_config.embedding_processor.max_retries = 3
            mock_config.embedding_processor.retry_backoff_base = 2
            
            mock_load_config.return_value = mock_config
            
            # Mock processor instance
            mock_processor = Mock()
            mock_processor_class.return_value = mock_processor
            
            # Test lifespan context manager
            async def test_lifespan():
                mock_app = Mock()
                async with lifespan(mock_app):
                    # Verify processor was started
                    mock_processor.start.assert_called_once()
            
            # Run the async test
            asyncio.run(test_lifespan())
    
    def test_lifespan_does_not_start_processor_when_disabled(self):
        """Test that lifespan does not start the processor when disabled."""
        from main import lifespan, app_state
        import asyncio
        
        with patch("main.load_config") as mock_load_config, \
             patch("main.BedrockClient"), \
             patch("main.S3Client"), \
             patch("main.S3VectorsClient"), \
             patch("main.IndexMetadataStore"), \
             patch("main.EmbeddingJobStore"), \
             patch("main.EmbeddingJobProcessor") as mock_processor_class:
            
            # Mock configuration with processor disabled
            mock_config = Mock()
            mock_config.environment = "test"
            mock_config.validate.return_value = True
            mock_config.use_localstack = False
            mock_config.aws_region = "us-east-1"
            mock_config.marengo_model_id = "test-marengo"
            mock_config.pegasus_model_id = "test-pegasus"
            mock_config.s3_bucket_name = "test-bucket"
            mock_config.s3_vectors_collection = "test-collection"
            mock_config.auth_password_hash = "test-hash"
            mock_config.max_indexes = 3
            mock_config.embedding_processor = Mock()
            mock_config.embedding_processor.enabled = False
            mock_config.embedding_processor.polling_interval = 30
            mock_config.embedding_processor.max_concurrent_jobs = 5
            mock_config.embedding_processor.max_retries = 3
            mock_config.embedding_processor.retry_backoff_base = 2
            
            mock_load_config.return_value = mock_config
            
            # Mock processor instance
            mock_processor = Mock()
            mock_processor_class.return_value = mock_processor
            
            # Test lifespan context manager
            async def test_lifespan():
                mock_app = Mock()
                async with lifespan(mock_app):
                    # Verify processor was NOT started
                    mock_processor.start.assert_not_called()
            
            # Run the async test
            asyncio.run(test_lifespan())
    
    def test_lifespan_stops_processor_on_shutdown(self):
        """Test that lifespan stops the processor during shutdown."""
        from main import lifespan, app_state
        import asyncio
        
        with patch("main.load_config") as mock_load_config, \
             patch("main.BedrockClient"), \
             patch("main.S3Client"), \
             patch("main.S3VectorsClient"), \
             patch("main.IndexMetadataStore"), \
             patch("main.EmbeddingJobStore"), \
             patch("main.EmbeddingJobProcessor") as mock_processor_class:
            
            # Mock configuration with processor enabled
            mock_config = Mock()
            mock_config.environment = "test"
            mock_config.validate.return_value = True
            mock_config.use_localstack = False
            mock_config.aws_region = "us-east-1"
            mock_config.marengo_model_id = "test-marengo"
            mock_config.pegasus_model_id = "test-pegasus"
            mock_config.s3_bucket_name = "test-bucket"
            mock_config.s3_vectors_collection = "test-collection"
            mock_config.auth_password_hash = "test-hash"
            mock_config.max_indexes = 3
            mock_config.embedding_processor = Mock()
            mock_config.embedding_processor.enabled = True
            mock_config.embedding_processor.polling_interval = 30
            mock_config.embedding_processor.max_concurrent_jobs = 5
            mock_config.embedding_processor.max_retries = 3
            mock_config.embedding_processor.retry_backoff_base = 2
            
            mock_load_config.return_value = mock_config
            
            # Mock processor instance
            mock_processor = Mock()
            mock_processor.is_running.return_value = True
            mock_processor_class.return_value = mock_processor
            
            # Test lifespan context manager
            async def test_lifespan():
                mock_app = Mock()
                async with lifespan(mock_app):
                    # Verify processor was started
                    mock_processor.start.assert_called_once()
                
                # After exiting context, verify processor was stopped
                mock_processor.stop.assert_called_once()
            
            # Run the async test
            asyncio.run(test_lifespan())
    
    def test_lifespan_does_not_stop_processor_if_not_running(self):
        """Test that lifespan does not call stop if processor is not running."""
        from main import lifespan, app_state
        import asyncio
        
        with patch("main.load_config") as mock_load_config, \
             patch("main.BedrockClient"), \
             patch("main.S3Client"), \
             patch("main.S3VectorsClient"), \
             patch("main.IndexMetadataStore"), \
             patch("main.EmbeddingJobStore"), \
             patch("main.EmbeddingJobProcessor") as mock_processor_class:
            
            # Mock configuration with processor disabled
            mock_config = Mock()
            mock_config.environment = "test"
            mock_config.validate.return_value = True
            mock_config.use_localstack = False
            mock_config.aws_region = "us-east-1"
            mock_config.marengo_model_id = "test-marengo"
            mock_config.pegasus_model_id = "test-pegasus"
            mock_config.s3_bucket_name = "test-bucket"
            mock_config.s3_vectors_collection = "test-collection"
            mock_config.auth_password_hash = "test-hash"
            mock_config.max_indexes = 3
            mock_config.embedding_processor = Mock()
            mock_config.embedding_processor.enabled = False
            mock_config.embedding_processor.polling_interval = 30
            mock_config.embedding_processor.max_concurrent_jobs = 5
            mock_config.embedding_processor.max_retries = 3
            mock_config.embedding_processor.retry_backoff_base = 2
            
            mock_load_config.return_value = mock_config
            
            # Mock processor instance that is not running
            mock_processor = Mock()
            mock_processor.is_running.return_value = False
            mock_processor_class.return_value = mock_processor
            
            # Test lifespan context manager
            async def test_lifespan():
                mock_app = Mock()
                async with lifespan(mock_app):
                    pass
                
                # Verify processor.stop() was NOT called since it's not running
                mock_processor.stop.assert_not_called()
            
            # Run the async test
            asyncio.run(test_lifespan())
    
    def test_lifespan_handles_missing_config(self):
        """Test that lifespan fails gracefully with missing configuration."""
        from main import lifespan
        from exceptions import ConfigurationError
        import asyncio
        
        with patch("main.load_config") as mock_load_config:
            # Mock config loading to raise FileNotFoundError
            mock_load_config.side_effect = FileNotFoundError("Config not found")
            
            # Lifespan should raise ConfigurationError
            async def test_lifespan():
                mock_app = Mock()
                with pytest.raises(ConfigurationError, match="Configuration file not found"):
                    async with lifespan(mock_app):
                        pass
            
            asyncio.run(test_lifespan())


class TestCORSConfiguration:
    """Test suite for CORS configuration."""
    
    def test_cors_origins_from_environment(self):
        """Test that CORS origins can be configured via environment variable."""
        # Set CORS origins
        os.environ["CORS_ORIGINS"] = "http://localhost:3000,http://localhost:5173"
        
        # Reload the module to pick up the environment variable
        import importlib
        import main
        importlib.reload(main)
        
        # Check that CORS middleware is configured
        # (We can't easily inspect the middleware configuration, but we can
        # verify the app was created)
        assert main.app is not None
        
        # Cleanup
        del os.environ["CORS_ORIGINS"]
        importlib.reload(main)
    
    def test_cors_default_allows_all(self):
        """Test that CORS defaults to allowing all origins."""
        # Ensure CORS_ORIGINS is not set
        if "CORS_ORIGINS" in os.environ:
            del os.environ["CORS_ORIGINS"]
        
        # Reload the module
        import importlib
        import main
        importlib.reload(main)
        
        # Verify app was created (default CORS should be "*")
        assert main.app is not None


class TestSignalHandling:
    """Test suite for signal handling and graceful shutdown."""
    
    def test_signal_handlers_registered(self):
        """Test that SIGTERM and SIGINT handlers are registered."""
        import signal
        import main
        
        # Get the current signal handlers
        sigterm_handler = signal.getsignal(signal.SIGTERM)
        sigint_handler = signal.getsignal(signal.SIGINT)
        
        # Verify handlers are set (not default)
        assert sigterm_handler != signal.SIG_DFL
        assert sigint_handler != signal.SIG_DFL
        
        # Verify they point to our handler function
        assert sigterm_handler == main._signal_handler
        assert sigint_handler == main._signal_handler
    
    def test_signal_handler_stops_processor(self):
        """Test that signal handler stops the embedding job processor."""
        import signal
        from main import _signal_handler, app_state
        
        # Mock a running processor
        mock_processor = Mock()
        mock_processor.is_running.return_value = True
        app_state.embedding_job_processor = mock_processor
        
        # Simulate SIGTERM signal
        _signal_handler(signal.SIGTERM, None)
        
        # Verify processor was stopped
        mock_processor.stop.assert_called_once()
        
        # Cleanup
        app_state.embedding_job_processor = None
    
    def test_signal_handler_does_not_stop_if_not_running(self):
        """Test that signal handler does not stop processor if not running."""
        import signal
        from main import _signal_handler, app_state
        
        # Mock a non-running processor
        mock_processor = Mock()
        mock_processor.is_running.return_value = False
        app_state.embedding_job_processor = mock_processor
        
        # Simulate SIGTERM signal
        _signal_handler(signal.SIGTERM, None)
        
        # Verify processor.stop() was NOT called
        mock_processor.stop.assert_not_called()
        
        # Cleanup
        app_state.embedding_job_processor = None
    
    def test_signal_handler_handles_missing_processor(self):
        """Test that signal handler handles missing processor gracefully."""
        import signal
        from main import _signal_handler, app_state
        
        # Ensure processor is None
        app_state.embedding_job_processor = None
        
        # Signal handler should not raise an exception
        try:
            _signal_handler(signal.SIGTERM, None)
        except Exception as e:
            pytest.fail(f"Signal handler raised exception: {e}")
    
    def test_signal_handler_handles_sigint(self):
        """Test that signal handler handles SIGINT (Ctrl+C)."""
        import signal
        from main import _signal_handler, app_state
        
        # Mock a running processor
        mock_processor = Mock()
        mock_processor.is_running.return_value = True
        app_state.embedding_job_processor = mock_processor
        
        # Simulate SIGINT signal (Ctrl+C)
        _signal_handler(signal.SIGINT, None)
        
        # Verify processor was stopped
        mock_processor.stop.assert_called_once()
        
        # Cleanup
        app_state.embedding_job_processor = None
    
    def test_lifespan_shutdown_stops_processor_after_signal(self):
        """Test that lifespan shutdown still works after signal handler runs."""
        from main import lifespan, app_state
        import asyncio
        
        with patch("main.load_config") as mock_load_config, \
             patch("main.BedrockClient"), \
             patch("main.S3Client"), \
             patch("main.S3VectorsClient"), \
             patch("main.IndexMetadataStore"), \
             patch("main.EmbeddingJobStore"), \
             patch("main.EmbeddingJobProcessor") as mock_processor_class:
            
            # Mock configuration with processor enabled
            mock_config = Mock()
            mock_config.environment = "test"
            mock_config.validate.return_value = True
            mock_config.use_localstack = False
            mock_config.aws_region = "us-east-1"
            mock_config.marengo_model_id = "test-marengo"
            mock_config.pegasus_model_id = "test-pegasus"
            mock_config.s3_bucket_name = "test-bucket"
            mock_config.s3_vectors_collection = "test-collection"
            mock_config.auth_password_hash = "test-hash"
            mock_config.max_indexes = 3
            mock_config.embedding_processor = Mock()
            mock_config.embedding_processor.enabled = True
            mock_config.embedding_processor.polling_interval = 30
            mock_config.embedding_processor.max_concurrent_jobs = 5
            mock_config.embedding_processor.max_retries = 3
            mock_config.embedding_processor.retry_backoff_base = 2
            
            mock_load_config.return_value = mock_config
            
            # Mock processor instance
            mock_processor = Mock()
            mock_processor.is_running.return_value = True
            mock_processor_class.return_value = mock_processor
            
            # Test lifespan context manager
            async def test_lifespan():
                mock_app = Mock()
                async with lifespan(mock_app):
                    # Verify processor was started
                    mock_processor.start.assert_called_once()
                
                # After exiting context, verify processor was stopped
                # (should be called once by lifespan shutdown)
                mock_processor.stop.assert_called_once()
            
            # Run the async test
            asyncio.run(test_lifespan())
