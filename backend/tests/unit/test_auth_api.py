"""Unit tests for authentication API endpoints.

Tests login, logout, and authentication middleware functionality.
Validates: Requirements 5.1, 5.2, 5.3
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api import auth
from services.auth_service import AuthService
from config import Config


class TestAuthAPI:
    """Test suite for authentication API endpoints."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration with a test password hash."""
        config = Mock(spec=Config)
        # Pre-computed bcrypt hash for the password "testpass"
        config.auth_password_hash = "$2b$12$nwluL4QIKcHv7t2K2BvQqugdkC0JA9lisYkXqH2o5nAdQu8.JylFe"
        return config
    
    @pytest.fixture
    def auth_service(self, mock_config):
        """Create an AuthService instance with test configuration."""
        return AuthService(mock_config, secret_key="test-secret-key")
    
    @pytest.fixture
    def app(self, auth_service):
        """Create a FastAPI test application with auth router."""
        test_app = FastAPI()
        
        # Set up auth service for dependency injection
        auth.set_auth_service(auth_service)
        
        # Include auth router
        test_app.include_router(auth.router, prefix="/api/auth")
        
        return test_app
    
    @pytest.fixture
    def client(self, app):
        """Create a test client for the FastAPI application."""
        return TestClient(app)
    
    def test_login_success(self, client):
        """Test successful login with correct password.
        
        Validates: Requirements 5.1, 5.2
        """
        response = client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "token" in data
        assert "message" in data
        
        # Check token is a non-empty string
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 0
        
        # Check success message
        assert data["message"] == "Login successful"
    
    def test_login_invalid_password(self, client):
        """Test login failure with incorrect password.
        
        Validates: Requirements 5.1, 5.3
        """
        response = client.post(
            "/api/auth/login",
            json={"password": "wrong_password"}
        )
        
        assert response.status_code == 401
        data = response.json()
        
        # Check error message
        assert "detail" in data
        assert data["detail"] == "Invalid password"
    
    def test_login_empty_password(self, client):
        """Test login with empty password."""
        response = client.post(
            "/api/auth/login",
            json={"password": ""}
        )
        
        # Should fail validation or authentication
        assert response.status_code in [401, 422]
    
    def test_login_missing_password(self, client):
        """Test login with missing password field."""
        response = client.post(
            "/api/auth/login",
            json={}
        )
        
        # Should fail validation
        assert response.status_code == 422
    
    def test_login_invalid_json(self, client):
        """Test login with invalid JSON."""
        response = client.post(
            "/api/auth/login",
            data="not json",
            headers={"Content-Type": "application/json"}
        )
        
        # Should fail with bad request
        assert response.status_code == 422
    
    def test_logout_success(self, client, auth_service):
        """Test successful logout with valid token.
        
        Validates: Requirements 5.2, 5.3
        """
        # First, login to get a token
        login_response = client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        token = login_response.json()["token"]
        
        # Then logout with the token
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "message" in data
        assert data["message"] == "Logout successful"
    
    def test_logout_missing_token(self, client):
        """Test logout without authentication token.
        
        Validates: Requirements 5.1
        """
        response = client.post("/api/auth/logout")
        
        # Should fail with unauthorized
        assert response.status_code == 403  # FastAPI returns 403 for missing credentials
    
    def test_logout_invalid_token(self, client):
        """Test logout with invalid token.
        
        Validates: Requirements 5.2
        """
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        # Should fail with unauthorized
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Authentication required"
    
    def test_logout_expired_token(self, client, auth_service):
        """Test logout with expired token."""
        # Create an expired token
        auth_service.token_expiration_hours = -1
        expired_token = auth_service.generate_token()
        auth_service.token_expiration_hours = 24
        
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        # Should fail with unauthorized
        assert response.status_code == 401
    
    def test_logout_malformed_authorization_header(self, client):
        """Test logout with malformed Authorization header."""
        # Missing "Bearer" prefix
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "some_token"}
        )
        
        # Should fail with unauthorized or forbidden
        assert response.status_code in [401, 403]
    
    def test_authentication_flow(self, client):
        """Test complete authentication flow: login, use token, logout.
        
        Validates: Requirements 5.1, 5.2, 5.3
        """
        # Step 1: Login with correct password
        login_response = client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        
        # Step 2: Use token to access protected endpoint (logout)
        logout_response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert logout_response.status_code == 200
        
        # Step 3: Token should still be valid (JWT is stateless)
        # Client is responsible for discarding the token
        second_logout = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert second_logout.status_code == 200
    
    def test_login_response_structure(self, client):
        """Test that login response has correct structure."""
        response = client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields are present
        assert "token" in data
        assert "message" in data
        
        # Check field types
        assert isinstance(data["token"], str)
        assert isinstance(data["message"], str)
    
    def test_logout_response_structure(self, client):
        """Test that logout response has correct structure."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        token = login_response.json()["token"]
        
        # Logout
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "message" in data
        assert isinstance(data["message"], str)
    
    def test_error_response_structure(self, client):
        """Test that error responses have correct structure."""
        response = client.post(
            "/api/auth/login",
            json={"password": "wrong_password"}
        )
        
        assert response.status_code == 401
        data = response.json()
        
        # Check error structure
        assert "detail" in data
        assert isinstance(data["detail"], str)
    
    def test_verify_token_dependency(self, client, auth_service):
        """Test the verify_token dependency function."""
        # Create a protected endpoint for testing
        from fastapi import APIRouter
        from typing import Annotated
        
        test_router = APIRouter()
        
        @test_router.get("/protected")
        async def protected_endpoint(
            authenticated: Annotated[bool, Depends(auth.verify_token)]
        ):
            return {"message": "Access granted"}
        
        # Add test router to app
        client.app.include_router(test_router)
        
        # Test without token
        response = client.get("/protected")
        assert response.status_code == 403
        
        # Test with valid token
        login_response = client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        token = login_response.json()["token"]
        
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Access granted"
        
        # Test with invalid token
        response = client.get(
            "/protected",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401
    
    def test_multiple_logins_generate_different_tokens(self, client):
        """Test that multiple logins generate different tokens."""
        import time
        
        # First login
        response1 = client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        token1 = response1.json()["token"]
        
        # Wait a moment to ensure different timestamp
        time.sleep(1.1)
        
        # Second login
        response2 = client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        token2 = response2.json()["token"]
        
        # Tokens should be different due to different timestamps
        assert token1 != token2
        
        # Both tokens should be valid
        logout1 = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token1}"}
        )
        assert logout1.status_code == 200
        
        logout2 = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert logout2.status_code == 200
    
    def test_case_sensitive_password(self, client):
        """Test that password verification is case-sensitive."""
        # Correct password is "testpass"
        
        # Try with different case
        response = client.post(
            "/api/auth/login",
            json={"password": "TestPass"}
        )
        assert response.status_code == 401
        
        response = client.post(
            "/api/auth/login",
            json={"password": "TESTPASS"}
        )
        assert response.status_code == 401
    
    def test_whitespace_in_password(self, client):
        """Test that whitespace in password is significant."""
        # Try with leading/trailing whitespace
        response = client.post(
            "/api/auth/login",
            json={"password": " testpass"}
        )
        assert response.status_code == 401
        
        response = client.post(
            "/api/auth/login",
            json={"password": "testpass "}
        )
        assert response.status_code == 401
    
    def test_concurrent_authentication(self, client):
        """Test that multiple concurrent authentications work correctly."""
        import concurrent.futures
        
        def login_and_logout():
            # Login
            login_resp = client.post(
                "/api/auth/login",
                json={"password": "testpass"}
            )
            if login_resp.status_code != 200:
                return False
            
            token = login_resp.json()["token"]
            
            # Logout
            logout_resp = client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {token}"}
            )
            return logout_resp.status_code == 200
        
        # Run multiple concurrent authentication flows
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(login_and_logout) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        assert all(results)
    
    def test_auth_service_not_initialized(self):
        """Test behavior when auth service is not initialized."""
        # Create a new app without setting auth service
        test_app = FastAPI()
        auth._auth_service = None  # Reset global state
        test_app.include_router(auth.router, prefix="/api/auth")
        # Use raise_server_exceptions=False to get HTTP response instead of exception
        test_client = TestClient(test_app, raise_server_exceptions=False)
        
        # Should fail with internal server error
        response = test_client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        assert response.status_code == 500
