"""Unit tests for Jockey configuration.

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
"""

import pytest
from pydantic import ValidationError
from src.config import JockeyConfig


class TestJockeyConfig:
    """Tests for JockeyConfig data model."""
    
    def test_default_values(self):
        """Test that JockeyConfig has correct default values."""
        config = JockeyConfig()
        
        assert config.enabled is True
        assert config.claude_model_id == "anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert config.max_segments_per_query == 10
        assert config.max_search_results == 15
        assert config.parallel_analysis_limit == 3
        assert config.search_cache_ttl == 300
        assert config.claude_temperature == 0.2
        assert config.claude_max_tokens == 4096
    
    def test_custom_values(self):
        """Test creating JockeyConfig with custom values."""
        config = JockeyConfig(
            enabled=False,
            claude_model_id="anthropic.claude-3-opus-20240229",
            max_segments_per_query=20,
            max_search_results=30,
            parallel_analysis_limit=5,
            search_cache_ttl=600,
            claude_temperature=0.5,
            claude_max_tokens=8192
        )
        
        assert config.enabled is False
        assert config.claude_model_id == "anthropic.claude-3-opus-20240229"
        assert config.max_segments_per_query == 20
        assert config.max_search_results == 30
        assert config.parallel_analysis_limit == 5
        assert config.search_cache_ttl == 600
        assert config.claude_temperature == 0.5
        assert config.claude_max_tokens == 8192
    
    def test_max_segments_validation_min(self):
        """Test that max_segments_per_query must be at least 1."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(max_segments_per_query=0)
        
        assert "max_segments_per_query" in str(exc_info.value)
    
    def test_max_segments_validation_max(self):
        """Test that max_segments_per_query cannot exceed 50."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(max_segments_per_query=51)
        
        assert "max_segments_per_query" in str(exc_info.value)
    
    def test_max_search_results_validation_min(self):
        """Test that max_search_results must be at least 1."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(max_search_results=0)
        
        assert "max_search_results" in str(exc_info.value)
    
    def test_max_search_results_validation_max(self):
        """Test that max_search_results cannot exceed 100."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(max_search_results=101)
        
        assert "max_search_results" in str(exc_info.value)
    
    def test_parallel_analysis_limit_validation_min(self):
        """Test that parallel_analysis_limit must be at least 1."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(parallel_analysis_limit=0)
        
        assert "parallel_analysis_limit" in str(exc_info.value)
    
    def test_parallel_analysis_limit_validation_max(self):
        """Test that parallel_analysis_limit cannot exceed 10."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(parallel_analysis_limit=11)
        
        assert "parallel_analysis_limit" in str(exc_info.value)
    
    def test_search_cache_ttl_validation_min(self):
        """Test that search_cache_ttl can be 0 (disabled)."""
        config = JockeyConfig(search_cache_ttl=0)
        assert config.search_cache_ttl == 0
    
    def test_search_cache_ttl_validation_negative(self):
        """Test that search_cache_ttl cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(search_cache_ttl=-1)
        
        assert "search_cache_ttl" in str(exc_info.value)
    
    def test_claude_temperature_validation_min(self):
        """Test that claude_temperature can be 0.0."""
        config = JockeyConfig(claude_temperature=0.0)
        assert config.claude_temperature == 0.0
    
    def test_claude_temperature_validation_max(self):
        """Test that claude_temperature can be 1.0."""
        config = JockeyConfig(claude_temperature=1.0)
        assert config.claude_temperature == 1.0
    
    def test_claude_temperature_validation_out_of_range_low(self):
        """Test that claude_temperature cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(claude_temperature=-0.1)
        
        assert "claude_temperature" in str(exc_info.value)
    
    def test_claude_temperature_validation_out_of_range_high(self):
        """Test that claude_temperature cannot exceed 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(claude_temperature=1.1)
        
        assert "claude_temperature" in str(exc_info.value)
    
    def test_claude_max_tokens_validation_min(self):
        """Test that claude_max_tokens must be at least 256."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(claude_max_tokens=255)
        
        assert "claude_max_tokens" in str(exc_info.value)
    
    def test_claude_max_tokens_validation_max(self):
        """Test that claude_max_tokens cannot exceed 8192."""
        with pytest.raises(ValidationError) as exc_info:
            JockeyConfig(claude_max_tokens=8193)
        
        assert "claude_max_tokens" in str(exc_info.value)
    
    def test_valid_boundary_values(self):
        """Test that all boundary values are valid."""
        config = JockeyConfig(
            max_segments_per_query=1,  # min
            max_search_results=1,  # min
            parallel_analysis_limit=1,  # min
            search_cache_ttl=0,  # min
            claude_temperature=0.0,  # min
            claude_max_tokens=256  # min
        )
        
        assert config.max_segments_per_query == 1
        assert config.max_search_results == 1
        assert config.parallel_analysis_limit == 1
        assert config.search_cache_ttl == 0
        assert config.claude_temperature == 0.0
        assert config.claude_max_tokens == 256
        
        config = JockeyConfig(
            max_segments_per_query=50,  # max
            max_search_results=100,  # max
            parallel_analysis_limit=10,  # max
            claude_temperature=1.0,  # max
            claude_max_tokens=8192  # max
        )
        
        assert config.max_segments_per_query == 50
        assert config.max_search_results == 100
        assert config.parallel_analysis_limit == 10
        assert config.claude_temperature == 1.0
        assert config.claude_max_tokens == 8192
