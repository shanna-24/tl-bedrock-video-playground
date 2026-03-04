"""Unit tests for Claude integration in BedrockClient.

Tests the invoke_claude method for orchestration tasks.
Validates: Requirements 1.5
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from aws.bedrock_client import BedrockClient
from config import Config
from exceptions import BedrockError


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=Config)
    config.marengo_model_id = "twelvelabs.marengo-embed-2-7-v1:0"
    config.pegasus_model_id = "twelvelabs.pegasus-1-2-v1:0"
    config.aws_region = "us-east-1"
    config.s3_bucket_name = "test-bucket"
    config.use_localstack = True  # Use localstack to avoid STS calls
    config.inference_profile_prefix = "us"
    return config


class TestClaudeIntegration:
    """Test suite for Claude model invocation."""
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_claude_success(self, mock_boto_client, mock_config):
        """Test successful Claude invocation."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Mock Claude response
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "content": [
                {
                    "type": "text",
                    "text": "This is Claude's response to the prompt."
                }
            ],
            "stop_reason": "end_turn"
        }).encode()
        
        mock_client_instance.invoke_model.return_value = mock_response
        
        # Create client and invoke
        client = BedrockClient(mock_config)
        response = client.invoke_claude("What is the meaning of life?")
        
        # Verify
        assert response == "This is Claude's response to the prompt."
        mock_client_instance.invoke_model.assert_called_once()
        
        # Check the request body
        call_args = mock_client_instance.invoke_model.call_args
        assert call_args[1]["modelId"] == "anthropic.claude-3-5-sonnet-20241022-v2:0"
        
        request_body = json.loads(call_args[1]["body"])
        assert request_body["anthropic_version"] == "bedrock-2023-05-31"
        assert request_body["messages"][0]["role"] == "user"
        assert request_body["messages"][0]["content"] == "What is the meaning of life?"
        assert request_body["temperature"] == 0.2
        assert request_body["max_tokens"] == 4096
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_claude_with_custom_parameters(self, mock_boto_client, mock_config):
        """Test Claude invocation with custom temperature and max_tokens."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "content": [
                {
                    "type": "text",
                    "text": "Custom response"
                }
            ]
        }).encode()
        
        mock_client_instance.invoke_model.return_value = mock_response
        
        client = BedrockClient(mock_config)
        response = client.invoke_claude(
            "Test prompt",
            temperature=0.7,
            max_tokens=2048
        )
        
        assert response == "Custom response"
        
        # Check the request parameters
        call_args = mock_client_instance.invoke_model.call_args
        request_body = json.loads(call_args[1]["body"])
        assert request_body["temperature"] == 0.7
        assert request_body["max_tokens"] == 2048
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_claude_with_custom_model_id(self, mock_boto_client, mock_config):
        """Test Claude invocation with custom model ID."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "content": [
                {
                    "type": "text",
                    "text": "Response from custom model"
                }
            ]
        }).encode()
        
        mock_client_instance.invoke_model.return_value = mock_response
        
        client = BedrockClient(mock_config)
        response = client.invoke_claude(
            "Test prompt",
            model_id="anthropic.claude-3-opus-20240229-v1:0"
        )
        
        assert response == "Response from custom model"
        
        # Check the model ID
        call_args = mock_client_instance.invoke_model.call_args
        assert call_args[1]["modelId"] == "anthropic.claude-3-opus-20240229-v1:0"
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_claude_multiple_content_blocks(self, mock_boto_client, mock_config):
        """Test Claude response with multiple content blocks."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "content": [
                {
                    "type": "text",
                    "text": "First part. "
                },
                {
                    "type": "text",
                    "text": "Second part."
                }
            ]
        }).encode()
        
        mock_client_instance.invoke_model.return_value = mock_response
        
        client = BedrockClient(mock_config)
        response = client.invoke_claude("Test prompt")
        
        # Should concatenate all text blocks
        assert response == "First part. Second part."
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_claude_empty_content(self, mock_boto_client, mock_config):
        """Test handling of empty content in response."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "content": []
        }).encode()
        
        mock_client_instance.invoke_model.return_value = mock_response
        
        client = BedrockClient(mock_config)
        
        with pytest.raises(BedrockError) as exc_info:
            client.invoke_claude("Test prompt")
        
        assert "Invalid response from Claude" in str(exc_info.value)
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_claude_empty_text(self, mock_boto_client, mock_config):
        """Test handling of empty text in content blocks."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "content": [
                {
                    "type": "text",
                    "text": ""
                }
            ]
        }).encode()
        
        mock_client_instance.invoke_model.return_value = mock_response
        
        client = BedrockClient(mock_config)
        
        with pytest.raises(BedrockError) as exc_info:
            client.invoke_claude("Test prompt")
        
        assert "Received empty text from Claude" in str(exc_info.value)
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_claude_client_error(self, mock_boto_client, mock_config):
        """Test handling of ClientError from Bedrock API."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Simulate ClientError
        error_response = {
            "Error": {
                "Code": "ThrottlingException",
                "Message": "Rate limit exceeded"
            }
        }
        mock_client_instance.invoke_model.side_effect = ClientError(
            error_response, "InvokeModel"
        )
        
        client = BedrockClient(mock_config)
        
        with pytest.raises(BedrockError) as exc_info:
            client.invoke_claude("Test prompt")
        
        assert "Failed to invoke Claude" in str(exc_info.value)
        assert "Rate limit exceeded" in str(exc_info.value)
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_claude_unexpected_error(self, mock_boto_client, mock_config):
        """Test handling of unexpected errors."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Simulate unexpected error
        mock_client_instance.invoke_model.side_effect = ValueError("Unexpected error")
        
        client = BedrockClient(mock_config)
        
        with pytest.raises(BedrockError) as exc_info:
            client.invoke_claude("Test prompt")
        
        assert "Failed to invoke Claude" in str(exc_info.value)
        assert "Unexpected error" in str(exc_info.value)
