"""
Unit tests for EmbeddingRetriever.

Tests the retriever's ability to download and parse embedding files
from S3, including various formats and error scenarios.
"""

import json
import pytest
from unittest.mock import Mock, MagicMock
from botocore.exceptions import ClientError

from src.services.embedding_retriever import EmbeddingRetriever, EmbeddingData


class TestEmbeddingData:
    """Test suite for EmbeddingData model."""
    
    def test_embedding_data_initialization(self):
        """Test that EmbeddingData initializes correctly."""
        embedding = [0.1, 0.2, 0.3]
        embedding_option = ["visual", "audio"]
        embedding_scope = "clip"
        start_sec = 0.0
        end_sec = 6.0
        
        data = EmbeddingData(
            embedding=embedding,
            embedding_option=embedding_option,
            embedding_scope=embedding_scope,
            start_sec=start_sec,
            end_sec=end_sec
        )
        
        assert data.embedding == embedding
        assert data.embedding_option == embedding_option
        assert data.embedding_scope == embedding_scope
        assert data.start_sec == start_sec
        assert data.end_sec == end_sec
    
    def test_to_dict_converts_correctly(self):
        """Test that to_dict converts EmbeddingData to dictionary."""
        data = EmbeddingData(
            embedding=[0.1, 0.2, 0.3],
            embedding_option=["visual", "audio"],
            embedding_scope="clip",
            start_sec=0.0,
            end_sec=6.0
        )
        
        result = data.to_dict()
        
        assert result == {
            "embedding": [0.1, 0.2, 0.3],
            "embeddingOption": ["visual", "audio"],
            "embeddingScope": "clip",
            "startSec": 0.0,
            "endSec": 6.0
        }
    
    def test_from_dict_creates_embedding_data(self):
        """Test that from_dict creates EmbeddingData from dictionary."""
        input_dict = {
            "embedding": [0.1, 0.2, 0.3],
            "embeddingOption": ["visual", "audio"],
            "embeddingScope": "clip",
            "startSec": 0.0,
            "endSec": 6.0
        }
        
        data = EmbeddingData.from_dict(input_dict)
        
        assert data.embedding == [0.1, 0.2, 0.3]
        assert data.embedding_option == ["visual", "audio"]
        assert data.embedding_scope == "clip"
        assert data.start_sec == 0.0
        assert data.end_sec == 6.0
    
    def test_from_dict_with_defaults(self):
        """Test that from_dict uses defaults for missing fields."""
        input_dict = {
            "embedding": [0.1, 0.2, 0.3]
        }
        
        data = EmbeddingData.from_dict(input_dict)
        
        assert data.embedding == [0.1, 0.2, 0.3]
        assert data.embedding_option == []
        assert data.embedding_scope == "clip"
        assert data.start_sec == 0.0
        assert data.end_sec == 0.0
    
    def test_get_metadata_returns_metadata_without_embedding(self):
        """Test that get_metadata returns metadata without embedding vector."""
        data = EmbeddingData(
            embedding=[0.1, 0.2, 0.3],
            embedding_option=["visual", "audio"],
            embedding_scope="clip",
            start_sec=0.0,
            end_sec=6.0
        )
        
        metadata = data.get_metadata()
        
        assert "embedding" not in metadata
        assert metadata == {
            "embedding_option": ["visual", "audio"],
            "embedding_scope": "clip",
            "start_timecode": 0.0,
            "end_timecode": 6.0
        }


class TestEmbeddingRetriever:
    """Test suite for EmbeddingRetriever."""
    
    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        return Mock()
    
    @pytest.fixture
    def retriever(self, mock_s3_client):
        """Create an EmbeddingRetriever instance with mock S3 client."""
        return EmbeddingRetriever(s3_client=mock_s3_client)
    
    # S3 URI Parsing Tests
    
    def test_parse_s3_uri_valid(self, retriever):
        """Test parsing a valid S3 URI."""
        bucket, key = retriever._parse_s3_uri("s3://my-bucket/path/to/file.json")
        
        assert bucket == "my-bucket"
        assert key == "path/to/file.json"
    
    def test_parse_s3_uri_with_nested_path(self, retriever):
        """Test parsing S3 URI with nested path."""
        bucket, key = retriever._parse_s3_uri("s3://bucket/a/b/c/file.json")
        
        assert bucket == "bucket"
        assert key == "a/b/c/file.json"
    
    def test_parse_s3_uri_invalid_prefix(self, retriever):
        """Test that invalid URI prefix raises ValueError."""
        with pytest.raises(ValueError, match="Invalid S3 URI format.*Must start with s3://"):
            retriever._parse_s3_uri("http://bucket/key")
    
    def test_parse_s3_uri_missing_key(self, retriever):
        """Test that URI without key raises ValueError."""
        with pytest.raises(ValueError, match="Invalid S3 URI format.*Must be s3://bucket/key"):
            retriever._parse_s3_uri("s3://bucket")
    
    def test_parse_s3_uri_empty_bucket(self, retriever):
        """Test that URI with empty bucket is parsed (bucket will be empty string)."""
        bucket, key = retriever._parse_s3_uri("s3:///key")
        
        assert bucket == ""
        assert key == "key"
    
    # S3 Download Tests
    
    def test_download_from_s3_success(self, retriever, mock_s3_client):
        """Test successful download from S3."""
        # Mock S3 response with streaming body
        mock_body = Mock()
        mock_body.iter_chunks = Mock(return_value=[b'chunk1', b'chunk2', b'chunk3'])
        mock_s3_client.get_object.return_value = {'Body': mock_body}
        
        result = retriever._download_from_s3("bucket", "key")
        
        assert result == b'chunk1chunk2chunk3'
        mock_s3_client.get_object.assert_called_once_with(Bucket="bucket", Key="key")
    
    def test_download_from_s3_large_file(self, retriever, mock_s3_client):
        """Test downloading large file with streaming."""
        # Create large chunks
        large_chunk = b'x' * (1024 * 1024)  # 1MB
        mock_body = Mock()
        mock_body.iter_chunks = Mock(return_value=[large_chunk, large_chunk, large_chunk])
        mock_s3_client.get_object.return_value = {'Body': mock_body}
        
        result = retriever._download_from_s3("bucket", "key")
        
        assert len(result) == 3 * 1024 * 1024
        assert result == large_chunk * 3
    
    def test_download_from_s3_client_error(self, retriever, mock_s3_client):
        """Test that S3 client errors are propagated."""
        error_response = {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, 'GetObject')
        
        with pytest.raises(ClientError):
            retriever._download_from_s3("bucket", "nonexistent-key")
    
    def test_download_from_s3_access_denied(self, retriever, mock_s3_client):
        """Test handling of access denied error."""
        error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, 'GetObject')
        
        with pytest.raises(ClientError):
            retriever._download_from_s3("bucket", "key")
    
    # JSON Parsing Tests
    
    def test_parse_json_marengo_single_embedding(self, retriever):
        """Test parsing Marengo 3.0 format with single embedding."""
        content = json.dumps({
            "data": {
                "embedding": [0.1, 0.2, 0.3],
                "embeddingOption": ["visual", "audio"],
                "embeddingScope": "clip",
                "startSec": 0.0,
                "endSec": 6.0
            }
        })
        
        embeddings = retriever._parse_json(content)
        
        assert len(embeddings) == 1
        assert embeddings[0].embedding == [0.1, 0.2, 0.3]
        assert embeddings[0].embedding_option == ["visual", "audio"]
        assert embeddings[0].embedding_scope == "clip"
        assert embeddings[0].start_sec == 0.0
        assert embeddings[0].end_sec == 6.0
    
    def test_parse_json_marengo_multiple_embeddings(self, retriever):
        """Test parsing Marengo 3.0 format with multiple embeddings."""
        content = json.dumps({
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3],
                    "embeddingOption": ["visual"],
                    "embeddingScope": "clip",
                    "startSec": 0.0,
                    "endSec": 6.0
                },
                {
                    "embedding": [0.4, 0.5, 0.6],
                    "embeddingOption": ["audio"],
                    "embeddingScope": "clip",
                    "startSec": 6.0,
                    "endSec": 12.0
                }
            ]
        })
        
        embeddings = retriever._parse_json(content)
        
        assert len(embeddings) == 2
        assert embeddings[0].embedding == [0.1, 0.2, 0.3]
        assert embeddings[0].start_sec == 0.0
        assert embeddings[1].embedding == [0.4, 0.5, 0.6]
        assert embeddings[1].start_sec == 6.0
    
    def test_parse_json_legacy_format(self, retriever):
        """Test parsing legacy format with embeddings array."""
        content = json.dumps({
            "embeddings": [
                {
                    "embedding": [0.1, 0.2, 0.3],
                    "embeddingOption": ["visual", "audio"],
                    "embeddingScope": "clip",
                    "startSec": 0.0,
                    "endSec": 6.0
                }
            ]
        })
        
        embeddings = retriever._parse_json(content)
        
        assert len(embeddings) == 1
        assert embeddings[0].embedding == [0.1, 0.2, 0.3]
    
    def test_parse_json_missing_data_and_embeddings_field(self, retriever):
        """Test that missing both data and embeddings fields raises ValueError."""
        content = json.dumps({"other_field": "value"})
        
        with pytest.raises(ValueError, match="Missing 'data' or 'embeddings' field"):
            retriever._parse_json(content)
    
    def test_parse_json_invalid_data_type(self, retriever):
        """Test that invalid data field type raises ValueError."""
        content = json.dumps({"data": "invalid"})
        
        with pytest.raises(ValueError, match="'data' field must be an object or array"):
            retriever._parse_json(content)
    
    def test_parse_json_invalid_embeddings_type(self, retriever):
        """Test that invalid embeddings field type raises ValueError."""
        content = json.dumps({"embeddings": "invalid"})
        
        with pytest.raises(ValueError, match="'embeddings' field must be an array"):
            retriever._parse_json(content)
    
    def test_parse_json_skips_invalid_embeddings(self, retriever):
        """Test that invalid embeddings in array are skipped."""
        content = json.dumps({
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3],
                    "embeddingOption": ["visual"],
                    "embeddingScope": "clip",
                    "startSec": 0.0,
                    "endSec": 6.0
                },
                {
                    "invalid": "data"
                },
                {
                    "embedding": [0.4, 0.5, 0.6],
                    "embeddingOption": ["audio"],
                    "embeddingScope": "clip",
                    "startSec": 6.0,
                    "endSec": 12.0
                }
            ]
        })
        
        embeddings = retriever._parse_json(content)
        
        assert len(embeddings) == 2
        assert embeddings[0].embedding == [0.1, 0.2, 0.3]
        assert embeddings[1].embedding == [0.4, 0.5, 0.6]
    
    # JSONL Parsing Tests
    
    def test_parse_jsonl_multiple_lines(self, retriever):
        """Test parsing JSONL format with multiple lines."""
        content = '\n'.join([
            json.dumps({
                "embedding": [0.1, 0.2, 0.3],
                "embeddingOption": ["visual"],
                "embeddingScope": "clip",
                "startSec": 0.0,
                "endSec": 6.0
            }),
            json.dumps({
                "embedding": [0.4, 0.5, 0.6],
                "embeddingOption": ["audio"],
                "embeddingScope": "clip",
                "startSec": 6.0,
                "endSec": 12.0
            })
        ])
        
        embeddings = retriever._parse_jsonl(content)
        
        assert len(embeddings) == 2
        assert embeddings[0].embedding == [0.1, 0.2, 0.3]
        assert embeddings[1].embedding == [0.4, 0.5, 0.6]
    
    def test_parse_jsonl_skips_empty_lines(self, retriever):
        """Test that empty lines in JSONL are skipped."""
        content = '\n'.join([
            json.dumps({"embedding": [0.1, 0.2, 0.3]}),
            "",
            json.dumps({"embedding": [0.4, 0.5, 0.6]}),
            "   ",
            json.dumps({"embedding": [0.7, 0.8, 0.9]})
        ])
        
        embeddings = retriever._parse_jsonl(content)
        
        assert len(embeddings) == 3
    
    def test_parse_jsonl_skips_invalid_lines(self, retriever):
        """Test that invalid JSON lines are skipped."""
        content = '\n'.join([
            json.dumps({"embedding": [0.1, 0.2, 0.3]}),
            "invalid json",
            json.dumps({"embedding": [0.4, 0.5, 0.6]})
        ])
        
        embeddings = retriever._parse_jsonl(content)
        
        assert len(embeddings) == 2
        assert embeddings[0].embedding == [0.1, 0.2, 0.3]
        assert embeddings[1].embedding == [0.4, 0.5, 0.6]
    
    # General Parsing Tests
    
    def test_parse_embeddings_json_format(self, retriever):
        """Test that _parse_embeddings handles JSON format."""
        data = json.dumps({
            "data": {
                "embedding": [0.1, 0.2, 0.3],
                "embeddingOption": ["visual"],
                "embeddingScope": "clip",
                "startSec": 0.0,
                "endSec": 6.0
            }
        }).encode('utf-8')
        
        embeddings = retriever._parse_embeddings(data)
        
        assert len(embeddings) == 1
        assert embeddings[0].embedding == [0.1, 0.2, 0.3]
    
    def test_parse_embeddings_invalid_utf8(self, retriever):
        """Test that invalid UTF-8 raises ValueError."""
        data = b'\xff\xfe invalid utf-8'
        
        with pytest.raises(ValueError, match="Invalid embedding data format"):
            retriever._parse_embeddings(data)
    
    def test_parse_embeddings_invalid_json(self, retriever):
        """Test that invalid JSON raises ValueError."""
        data = b'{ invalid json }'
        
        with pytest.raises(ValueError, match="Invalid embedding data format"):
            retriever._parse_embeddings(data)
    
    # Integration Tests
    
    def test_retrieve_embeddings_success(self, retriever, mock_s3_client):
        """Test successful end-to-end embedding retrieval."""
        # Mock S3 response
        embedding_data = json.dumps({
            "data": {
                "embedding": [0.1, 0.2, 0.3],
                "embeddingOption": ["visual", "audio"],
                "embeddingScope": "clip",
                "startSec": 0.0,
                "endSec": 6.0
            }
        }).encode('utf-8')
        
        mock_body = Mock()
        mock_body.iter_chunks = Mock(return_value=[embedding_data])
        mock_s3_client.get_object.return_value = {'Body': mock_body}
        
        embeddings = retriever.retrieve_embeddings("s3://my-bucket/embeddings.json")
        
        assert len(embeddings) == 1
        assert embeddings[0].embedding == [0.1, 0.2, 0.3]
        assert embeddings[0].embedding_option == ["visual", "audio"]
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="my-bucket",
            Key="embeddings.json"
        )
    
    def test_retrieve_embeddings_multiple(self, retriever, mock_s3_client):
        """Test retrieving multiple embeddings."""
        embedding_data = json.dumps({
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3],
                    "embeddingOption": ["visual"],
                    "embeddingScope": "clip",
                    "startSec": 0.0,
                    "endSec": 6.0
                },
                {
                    "embedding": [0.4, 0.5, 0.6],
                    "embeddingOption": ["audio"],
                    "embeddingScope": "clip",
                    "startSec": 6.0,
                    "endSec": 12.0
                }
            ]
        }).encode('utf-8')
        
        mock_body = Mock()
        mock_body.iter_chunks = Mock(return_value=[embedding_data])
        mock_s3_client.get_object.return_value = {'Body': mock_body}
        
        embeddings = retriever.retrieve_embeddings("s3://bucket/path/to/embeddings.json")
        
        assert len(embeddings) == 2
        assert embeddings[0].start_sec == 0.0
        assert embeddings[1].start_sec == 6.0
    
    def test_retrieve_embeddings_invalid_uri(self, retriever):
        """Test that invalid S3 URI raises ValueError."""
        with pytest.raises(ValueError, match="Invalid S3 URI format"):
            retriever.retrieve_embeddings("http://bucket/key")
    
    def test_retrieve_embeddings_s3_error(self, retriever, mock_s3_client):
        """Test that S3 errors are propagated."""
        error_response = {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, 'GetObject')
        
        with pytest.raises(ClientError):
            retriever.retrieve_embeddings("s3://bucket/nonexistent.json")
    
    def test_retrieve_embeddings_with_metadata(self, retriever, mock_s3_client):
        """Test that metadata is correctly extracted."""
        embedding_data = json.dumps({
            "data": {
                "embedding": [0.1, 0.2, 0.3],
                "embeddingOption": ["visual", "audio", "transcription"],
                "embeddingScope": "asset",
                "startSec": 10.5,
                "endSec": 20.5
            }
        }).encode('utf-8')
        
        mock_body = Mock()
        mock_body.iter_chunks = Mock(return_value=[embedding_data])
        mock_s3_client.get_object.return_value = {'Body': mock_body}
        
        embeddings = retriever.retrieve_embeddings("s3://bucket/embeddings.json")
        
        assert len(embeddings) == 1
        metadata = embeddings[0].get_metadata()
        assert metadata["embedding_option"] == ["visual", "audio", "transcription"]
        assert metadata["embedding_scope"] == "asset"
        assert metadata["start_timecode"] == 10.5
        assert metadata["end_timecode"] == 20.5
