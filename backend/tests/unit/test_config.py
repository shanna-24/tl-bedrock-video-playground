"""Unit tests for configuration module.

Tests configuration loading, validation, and error handling.
Validates: Requirements 6.1, 6.2, 6.3, 6.4
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from config import Config, EmbeddingProcessorConfig, load_config


class TestConfig:
    """Test suite for Config class."""
    
    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "max_indexes": 3,
            "auth_password_hash": "$2b$12$test_hash",
            "environment": "local",
            "use_localstack": True,
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = Config.load_from_file(temp_path)
            
            assert config.marengo_model_id == "twelvelabs.marengo-v1"
            assert config.pegasus_model_id == "twelvelabs.pegasus-v1"
            assert config.aws_region == "us-east-1"
            assert config.s3_bucket_name == "test-bucket"
            assert config.s3_vectors_collection == "test-collection"
            assert config.max_indexes == 3
            assert config.auth_password_hash == "$2b$12$test_hash"
            assert config.environment == "local"
            assert config.use_localstack is True
        finally:
            os.unlink(temp_path)
    
    def test_load_config_file_not_found(self):
        """Test that loading a non-existent config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            Config.load_from_file("nonexistent.yaml")
        
        assert "Configuration file not found" in str(exc_info.value)
    
    def test_load_config_invalid_yaml(self):
        """Test that loading invalid YAML raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                Config.load_from_file(temp_path)
            
            assert "Invalid YAML" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_load_config_empty_file(self):
        """Test that loading an empty config file raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                Config.load_from_file(temp_path)
            
            assert "Configuration file is empty" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_load_config_missing_required_field(self):
        """Test that missing required fields raise ValueError."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            # Missing pegasus_model_id
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "auth_password_hash": "$2b$12$test_hash",
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                Config.load_from_file(temp_path)
            
            assert "Invalid configuration" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_validate_aws_region(self):
        """Test AWS region validation."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "x",  # Too short
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "auth_password_hash": "$2b$12$test_hash",
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                Config.load_from_file(temp_path)
            
            assert "AWS region must be a valid region code" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_validate_model_id(self):
        """Test model ID validation."""
        config_data = {
            "marengo_model_id": "ab",  # Too short
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "auth_password_hash": "$2b$12$test_hash",
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                Config.load_from_file(temp_path)
            
            assert "Model ID must be a valid identifier" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_validate_max_indexes_range(self):
        """Test that max_indexes validation works."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "max_indexes": 0,  # Too low
            "auth_password_hash": "$2b$12$test_hash",
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError):
                Config.load_from_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validate_method(self):
        """Test the validate method."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "max_indexes": 3,
            "auth_password_hash": "$2b$12$test_hash",
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = Config.load_from_file(temp_path)
            assert config.validate() is True
        finally:
            os.unlink(temp_path)
    
    def test_default_values(self):
        """Test that default values are applied correctly."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "auth_password_hash": "$2b$12$test_hash",
            # Not specifying max_indexes, environment, use_localstack
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = Config.load_from_file(temp_path)
            
            assert config.max_indexes == 3  # Default value
            assert config.environment == "local"  # Default value
            assert config.use_localstack is False  # Default value
        finally:
            os.unlink(temp_path)


class TestLoadConfig:
    """Test suite for load_config function."""
    
    def test_load_config_with_explicit_path(self):
        """Test loading config with explicit path."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "auth_password_hash": "$2b$12$test_hash",
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            assert config.marengo_model_id == "twelvelabs.marengo-v1"
        finally:
            os.unlink(temp_path)
    
    def test_load_config_default_local(self):
        """Test loading config defaults to local environment."""
        # This test assumes config.local.yaml exists in the project root
        if Path("config.local.yaml").exists():
            config = load_config()
            assert config is not None
            assert isinstance(config, Config)


class TestEmbeddingProcessorConfig:
    """Test suite for EmbeddingProcessorConfig class."""
    
    def test_default_values(self):
        """Test that default values are applied correctly."""
        config = EmbeddingProcessorConfig()
        
        assert config.enabled is True
        assert config.polling_interval == 30
        assert config.max_concurrent_jobs == 5
        assert config.max_retries == 3
        assert config.retry_backoff_base == 2
    
    def test_custom_values(self):
        """Test creating config with custom values."""
        config = EmbeddingProcessorConfig(
            enabled=False,
            polling_interval=60,
            max_concurrent_jobs=10,
            max_retries=5,
            retry_backoff_base=3
        )
        
        assert config.enabled is False
        assert config.polling_interval == 60
        assert config.max_concurrent_jobs == 10
        assert config.max_retries == 5
        assert config.retry_backoff_base == 3
    
    def test_polling_interval_validation(self):
        """Test that polling_interval must be >= 1."""
        with pytest.raises(ValueError):
            EmbeddingProcessorConfig(polling_interval=0)
        
        with pytest.raises(ValueError):
            EmbeddingProcessorConfig(polling_interval=-1)
        
        # Valid value should work
        config = EmbeddingProcessorConfig(polling_interval=1)
        assert config.polling_interval == 1
    
    def test_max_concurrent_jobs_validation(self):
        """Test that max_concurrent_jobs must be between 1 and 20."""
        with pytest.raises(ValueError):
            EmbeddingProcessorConfig(max_concurrent_jobs=0)
        
        with pytest.raises(ValueError):
            EmbeddingProcessorConfig(max_concurrent_jobs=21)
        
        # Valid values should work
        config = EmbeddingProcessorConfig(max_concurrent_jobs=1)
        assert config.max_concurrent_jobs == 1
        
        config = EmbeddingProcessorConfig(max_concurrent_jobs=20)
        assert config.max_concurrent_jobs == 20
    
    def test_max_retries_validation(self):
        """Test that max_retries must be between 0 and 10."""
        with pytest.raises(ValueError):
            EmbeddingProcessorConfig(max_retries=-1)
        
        with pytest.raises(ValueError):
            EmbeddingProcessorConfig(max_retries=11)
        
        # Valid values should work
        config = EmbeddingProcessorConfig(max_retries=0)
        assert config.max_retries == 0
        
        config = EmbeddingProcessorConfig(max_retries=10)
        assert config.max_retries == 10
    
    def test_retry_backoff_base_validation(self):
        """Test that retry_backoff_base must be between 1 and 10."""
        with pytest.raises(ValueError):
            EmbeddingProcessorConfig(retry_backoff_base=0)
        
        with pytest.raises(ValueError):
            EmbeddingProcessorConfig(retry_backoff_base=11)
        
        # Valid values should work
        config = EmbeddingProcessorConfig(retry_backoff_base=1)
        assert config.retry_backoff_base == 1
        
        config = EmbeddingProcessorConfig(retry_backoff_base=10)
        assert config.retry_backoff_base == 10


class TestConfigWithEmbeddingProcessor:
    """Test suite for Config class with embedding_processor field."""
    
    def test_load_config_with_embedding_processor(self):
        """Test loading config with embedding_processor section."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "auth_password_hash": "$2b$12$test_hash",
            "embedding_processor": {
                "enabled": True,
                "polling_interval": 45,
                "max_concurrent_jobs": 8,
                "max_retries": 4,
                "retry_backoff_base": 3
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = Config.load_from_file(temp_path)
            
            assert config.embedding_processor.enabled is True
            assert config.embedding_processor.polling_interval == 45
            assert config.embedding_processor.max_concurrent_jobs == 8
            assert config.embedding_processor.max_retries == 4
            assert config.embedding_processor.retry_backoff_base == 3
        finally:
            os.unlink(temp_path)
    
    def test_load_config_without_embedding_processor(self):
        """Test that config loads with default embedding_processor when not specified."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "auth_password_hash": "$2b$12$test_hash",
            # No embedding_processor section
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = Config.load_from_file(temp_path)
            
            # Should have default values
            assert config.embedding_processor.enabled is True
            assert config.embedding_processor.polling_interval == 30
            assert config.embedding_processor.max_concurrent_jobs == 5
            assert config.embedding_processor.max_retries == 3
            assert config.embedding_processor.retry_backoff_base == 2
        finally:
            os.unlink(temp_path)
    
    def test_load_config_with_partial_embedding_processor(self):
        """Test loading config with partial embedding_processor section."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "auth_password_hash": "$2b$12$test_hash",
            "embedding_processor": {
                "enabled": False,
                "polling_interval": 60
                # Other fields should use defaults
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = Config.load_from_file(temp_path)
            
            assert config.embedding_processor.enabled is False
            assert config.embedding_processor.polling_interval == 60
            # Defaults for unspecified fields
            assert config.embedding_processor.max_concurrent_jobs == 5
            assert config.embedding_processor.max_retries == 3
            assert config.embedding_processor.retry_backoff_base == 2
        finally:
            os.unlink(temp_path)
    
    def test_load_config_with_invalid_embedding_processor(self):
        """Test that invalid embedding_processor values raise ValueError."""
        config_data = {
            "marengo_model_id": "twelvelabs.marengo-v1",
            "pegasus_model_id": "twelvelabs.pegasus-v1",
            "aws_region": "us-east-1",
            "s3_bucket_name": "test-bucket",
            "s3_vectors_collection": "test-collection",
            "auth_password_hash": "$2b$12$test_hash",
            "embedding_processor": {
                "polling_interval": 0  # Invalid: must be >= 1
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError):
                Config.load_from_file(temp_path)
        finally:
            os.unlink(temp_path)
