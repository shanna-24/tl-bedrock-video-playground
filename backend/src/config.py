"""Configuration module for TL-Video-Playground.

This module handles loading and validating configuration from YAML files.
Validates: Requirements 6.1, 6.2, 6.3, 6.4
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class EmbeddingProcessorConfig(BaseModel):
    """Configuration for the embedding job processor.
    
    Attributes:
        enabled: Whether the embedding processor is enabled
        polling_interval: How often to check for job updates (in seconds)
        max_concurrent_jobs: Maximum number of jobs to process concurrently
        max_retries: Maximum number of retry attempts for failed jobs
        retry_backoff_base: Base for exponential backoff calculation
    """
    
    enabled: bool = Field(default=True)
    polling_interval: int = Field(default=30, ge=1)
    max_concurrent_jobs: int = Field(default=5, ge=1, le=20)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_backoff_base: int = Field(default=2, ge=1, le=10)


class JockeyConfig(BaseModel):
    """Configuration for Jockey-inspired orchestration system.
    
    Attributes:
        enabled: Whether Jockey orchestration is enabled for index analysis
        claude_model_id: Claude model ID for reasoning and planning
        max_segments_per_query: Maximum number of video segments to analyze per request
        max_search_results: Maximum number of search results to retrieve from Marengo
        parallel_analysis_limit: Maximum number of concurrent Pegasus analyses
        search_cache_ttl: Time-to-live for search result cache in seconds
        claude_temperature: Temperature parameter for Claude model (0.0-1.0)
        claude_max_tokens: Maximum tokens for Claude responses
        web_search_enabled: Whether to enable web search enrichment at aggregation stage
        brave_api_key: Brave Search API key for web search functionality
    """
    
    enabled: bool = Field(default=True)
    claude_model_id: str = Field(default="anthropic.claude-sonnet-4-5-20250929-v1:0")
    max_segments_per_query: int = Field(default=10, ge=1, le=50)
    max_search_results: int = Field(default=15, ge=1, le=100)
    parallel_analysis_limit: int = Field(default=3, ge=1, le=10)
    search_cache_ttl: int = Field(default=300, ge=0)  # 5 minutes
    claude_temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    claude_max_tokens: int = Field(default=4096, ge=256, le=8192)
    web_search_enabled: bool = Field(default=False)
    brave_api_key: Optional[str] = Field(default=None)


class LoggingConfig(BaseModel):
    """Configuration for logging settings.
    
    Attributes:
        file_logging_enabled: Whether to enable file logging
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    
    file_logging_enabled: bool = Field(default=True)
    level: str = Field(default="INFO")
    
    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()


class ThemeConfig(BaseModel):
    """Configuration for UI theme settings.
    
    Attributes:
        default_mode: Default theme mode on startup ('light' or 'dark')
    """
    
    default_mode: str = Field(default="light")
    
    @field_validator("default_mode")
    @classmethod
    def validate_theme_mode(cls, v: str) -> str:
        """Validate theme mode is either 'light' or 'dark'."""
        if v not in ["light", "dark"]:
            raise ValueError("Theme mode must be either 'light' or 'dark'")
        return v


class ComplianceConfig(BaseModel):
    """Configuration for compliance analysis settings.

    Attributes:
        pegasus_temperature: Temperature parameter for Pegasus model during compliance analysis (0.0-1.0)
    """

    pegasus_temperature: float = Field(default=0.0, ge=0.0, le=1.0)


class Config(BaseSettings):
    """System configuration loaded from config file.
    
    Attributes:
        marengo_model_id: TwelveLabs Marengo model identifier for video indexing
        pegasus_model_id: TwelveLabs Pegasus model identifier for video analysis
        inference_profile_prefix: Prefix for inference profiles (e.g., "us", "eu")
        aws_region: AWS region for all services
        s3_bucket_name: S3 bucket name for video storage
        s3_vectors_collection: Bedrock S3 Vectors collection name for embeddings
        max_indexes: Maximum number of indexes allowed (default: 3)
        auth_password_hash: Bcrypt hash of the authentication password
        environment: Environment name (local, production)
        embedding_processor: Configuration for the embedding job processor
        jockey: Configuration for Jockey-inspired orchestration system
    """
    
    marengo_model_id: str = Field(..., min_length=1)
    pegasus_model_id: str = Field(..., min_length=1)
    inference_profile_prefix: str = Field(default="us", min_length=1)
    aws_region: str = Field(..., min_length=1)
    s3_bucket_name: str = Field(..., min_length=1)
    s3_vectors_collection: Optional[str] = Field(default=None, min_length=1)
    max_indexes: int = Field(default=3, ge=1, le=10)
    auth_password_hash: str = Field(..., min_length=1)
    environment: str = Field(default="local")
    embedding_processor: EmbeddingProcessorConfig = Field(default_factory=EmbeddingProcessorConfig)
    jockey: JockeyConfig = Field(default_factory=JockeyConfig)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)
    
    @model_validator(mode='after')
    def set_s3_vectors_collection_default(self) -> 'Config':
        """Set s3_vectors_collection to s3_bucket_name if not provided."""
        if self.s3_vectors_collection is None:
            self.s3_vectors_collection = self.s3_bucket_name
        return self
    
    @field_validator("aws_region")
    @classmethod
    def validate_aws_region(cls, v: str) -> str:
        """Validate AWS region format."""
        if not v or len(v) < 3:
            raise ValueError("AWS region must be a valid region code (e.g., us-east-1)")
        return v
    
    @field_validator("marengo_model_id", "pegasus_model_id")
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        """Validate model ID format."""
        if not v or len(v) < 3:
            raise ValueError("Model ID must be a valid identifier")
        return v
    
    @classmethod
    def load_from_file(cls, path: str) -> "Config":
        """Load configuration from a YAML file.
        
        Args:
            path: Path to the configuration YAML file
            
        Returns:
            Config: Validated configuration object
            
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            ValueError: If the configuration is invalid
            yaml.YAMLError: If the YAML file is malformed
        """
        config_path = Path(path)
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {path}. "
                "Please create a config.yaml file with required settings."
            )
        
        try:
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")
        
        if not config_data:
            raise ValueError("Configuration file is empty")
        
        try:
            return cls(**config_data)
        except Exception as e:
            raise ValueError(f"Invalid configuration: {e}")
    
    def validate(self) -> bool:
        """Validate all configuration values.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ValueError: If any configuration value is invalid
        """
        # Pydantic already validates on initialization, but we can add
        # additional cross-field validation here if needed
        
        if self.max_indexes < 1:
            raise ValueError("max_indexes must be at least 1")
        
        if self.max_indexes > 10:
            raise ValueError("max_indexes cannot exceed 10")
        
        return True


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from file or environment.
    
    Args:
        config_path: Optional path to configuration file.
                    Defaults to config.local.yaml or config.prod.yaml
                    based on ENVIRONMENT variable.
    
    Returns:
        Config: Validated configuration object
    """
    import os
    
    if config_path is None:
        env = os.getenv("ENVIRONMENT", "local")
        config_path = f"config.{env}.yaml"
    
    return Config.load_from_file(config_path)
