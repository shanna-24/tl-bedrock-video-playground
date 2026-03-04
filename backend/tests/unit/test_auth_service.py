"""Unit tests for authentication service.

Tests password verification, token generation, and token validation.
Validates: Requirements 5.1, 5.2, 5.3, 5.4
"""

import sys
import time
from pathlib import Path
from unittest.mock import Mock

from jose import jwt
import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from config import Config
from services.auth_service import AuthService


class TestAuthService:
    """Test suite for AuthService class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration with a test password hash."""
        config = Mock(spec=Config)
        # Pre-computed bcrypt hash for the password "testpass"
        # Generated with: bcrypt.hashpw(b'testpass', bcrypt.gensalt())
        config.auth_password_hash = "$2b$12$nwluL4QIKcHv7t2K2BvQqugdkC0JA9lisYkXqH2o5nAdQu8.JylFe"
        return config
    
    @pytest.fixture
    def auth_service(self, mock_config):
        """Create an AuthService instance with test configuration."""
        return AuthService(mock_config, secret_key="test-secret-key")
    
    def test_verify_password_correct(self, auth_service):
        """Test successful authentication with correct password.
        
        Validates: Requirements 5.1, 5.2
        """
        result = auth_service.verify_password("testpass")
        assert result is True
    
    def test_verify_password_incorrect(self, auth_service):
        """Test failed authentication with incorrect password.
        
        Validates: Requirements 5.1, 5.3
        """
        result = auth_service.verify_password("wrong_password")
        assert result is False
    
    def test_verify_password_empty(self, auth_service):
        """Test authentication with empty password."""
        result = auth_service.verify_password("")
        assert result is False
    
    def test_verify_password_invalid_hash(self):
        """Test password verification with invalid hash format."""
        config = Mock(spec=Config)
        config.auth_password_hash = "invalid_hash_format"
        auth_service = AuthService(config)
        
        # Should return False rather than raising an exception
        result = auth_service.verify_password("any_password")
        assert result is False
    
    def test_generate_token(self, auth_service):
        """Test JWT token generation.
        
        Validates: Requirements 5.2
        """
        token = auth_service.generate_token()
        
        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Token should be decodable
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert payload["authenticated"] is True
        assert "exp" in payload
        assert "iat" in payload
    
    def test_generate_token_unique(self, auth_service):
        """Test that generated tokens are unique (due to timestamp)."""
        token1 = auth_service.generate_token()
        time.sleep(1.1)  # Sleep for more than 1 second to ensure different timestamp
        token2 = auth_service.generate_token()
        
        # Tokens should be different due to different iat (issued at) times
        assert token1 != token2
    
    def test_verify_token_valid(self, auth_service):
        """Test verification of a valid token.
        
        Validates: Requirements 5.2
        """
        token = auth_service.generate_token()
        result = auth_service.verify_token(token)
        
        assert result is True
    
    def test_verify_token_invalid_signature(self, auth_service, mock_config):
        """Test verification of a token with invalid signature."""
        # Generate token with one secret key
        token = auth_service.generate_token()
        
        # Try to verify with different secret key
        different_auth_service = AuthService(
            mock_config,
            secret_key="different-secret-key"
        )
        
        result = different_auth_service.verify_token(token)
        assert result is False
    
    def test_verify_token_malformed(self, auth_service):
        """Test verification of a malformed token."""
        result = auth_service.verify_token("not.a.valid.token")
        assert result is False
    
    def test_verify_token_empty(self, auth_service):
        """Test verification of an empty token."""
        result = auth_service.verify_token("")
        assert result is False
    
    def test_verify_token_expired(self, auth_service):
        """Test verification of an expired token."""
        # Create a token that expires immediately
        auth_service.token_expiration_hours = -1  # Negative means already expired
        token = auth_service.generate_token()
        
        # Reset expiration for verification
        auth_service.token_expiration_hours = 24
        
        result = auth_service.verify_token(token)
        assert result is False
    
    def test_verify_token_missing_authenticated_field(self, auth_service):
        """Test verification of a token without authenticated field."""
        # Manually create a token without the authenticated field
        from datetime import datetime, timedelta
        
        payload = {
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow(),
            # Missing "authenticated" field
        }
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
        
        result = auth_service.verify_token(token)
        assert result is False
    
    def test_default_secret_key(self, mock_config):
        """Test that a default secret key is used if none provided."""
        auth_service = AuthService(mock_config)
        
        # Should use default secret key
        assert auth_service.secret_key == "default-secret-key-change-in-production"
        
        # Should still be able to generate and verify tokens
        token = auth_service.generate_token()
        assert auth_service.verify_token(token) is True
    
    def test_custom_secret_key(self, mock_config):
        """Test that custom secret key is used when provided."""
        custom_key = "my-custom-secret-key"
        auth_service = AuthService(mock_config, secret_key=custom_key)
        
        assert auth_service.secret_key == custom_key
        
        # Tokens should work with custom key
        token = auth_service.generate_token()
        assert auth_service.verify_token(token) is True
    
    def test_token_expiration_hours_default(self, auth_service):
        """Test that default token expiration is 24 hours."""
        assert auth_service.token_expiration_hours == 24
    
    def test_algorithm_is_hs256(self, auth_service):
        """Test that JWT algorithm is HS256."""
        assert auth_service.algorithm == "HS256"
    
    def test_full_authentication_flow(self, auth_service):
        """Test complete authentication flow: verify password, generate token, verify token.
        
        Validates: Requirements 5.1, 5.2, 5.3, 5.4
        """
        # Step 1: Verify correct password
        password_valid = auth_service.verify_password("testpass")
        assert password_valid is True
        
        # Step 2: Generate token after successful authentication
        token = auth_service.generate_token()
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Step 3: Verify token for subsequent requests
        token_valid = auth_service.verify_token(token)
        assert token_valid is True
        
        # Step 4: Verify incorrect password fails
        password_invalid = auth_service.verify_password("wrong_password")
        assert password_invalid is False
    
    def test_authentication_error_message_scenario(self, auth_service):
        """Test scenario where authentication should fail with error message.
        
        This simulates the requirement that incorrect credentials should
        deny access and display an error message.
        
        Validates: Requirements 5.3
        """
        # Attempt authentication with wrong password
        is_authenticated = auth_service.verify_password("wrong_password")
        
        # Should return False, allowing the API layer to return
        # "Invalid password" error message
        assert is_authenticated is False
    
    def test_token_contains_required_fields(self, auth_service):
        """Test that generated tokens contain all required fields."""
        token = auth_service.generate_token()
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        
        # Check required fields
        assert "authenticated" in payload
        assert "exp" in payload  # Expiration time
        assert "iat" in payload  # Issued at time
        
        # Check field values
        assert payload["authenticated"] is True
        assert isinstance(payload["exp"], int)
        assert isinstance(payload["iat"], int)
        assert payload["exp"] > payload["iat"]  # Expiration should be after issuance
