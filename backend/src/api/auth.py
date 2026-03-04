"""Authentication API endpoints for TL-Video-Playground.

This module implements authentication endpoints for login and logout,
as well as authentication middleware for protecting routes.

Validates: Requirements 5.1, 5.2, 5.3
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from services.auth_service import AuthService
from exceptions import AuthenticationError

# Import app_state for dependency injection
import main


# Request/Response models
class LoginRequest(BaseModel):
    """Login request model.
    
    Attributes:
        password: Plain text password for authentication
    """
    password: str = Field(..., min_length=1, description="Authentication password")


class LoginResponse(BaseModel):
    """Login response model.
    
    Attributes:
        token: JWT token for authenticated sessions
        message: Success message
    """
    token: str = Field(..., description="JWT authentication token")
    message: str = Field(default="Login successful", description="Success message")


class LogoutResponse(BaseModel):
    """Logout response model.
    
    Attributes:
        message: Success message
    """
    message: str = Field(default="Logout successful", description="Success message")


class ErrorResponse(BaseModel):
    """Error response model.
    
    Attributes:
        detail: Error message
    """
    detail: str = Field(..., description="Error message")


# Security scheme for Bearer token authentication
security = HTTPBearer()


# Create router
router = APIRouter()


# Dependency injection placeholder (will be set by main.py)
_auth_service: AuthService = None


def set_auth_service(auth_service: AuthService):
    """Set the auth service instance for dependency injection.
    
    This function should be called by main.py during startup to inject
    the initialized AuthService instance.
    
    Args:
        auth_service: Initialized AuthService instance
    """
    global _auth_service
    _auth_service = auth_service


def get_auth_service() -> AuthService:
    """Get the auth service instance.
    
    Returns:
        AuthService instance
        
    Raises:
        RuntimeError: If auth service is not initialized
    """
    if main.app_state.auth_service is None:
        raise RuntimeError("Auth service not initialized")
    return main.app_state.auth_service


async def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> bool:
    """Verify JWT token from Authorization header.
    
    This dependency can be used to protect routes that require authentication.
    
    Args:
        credentials: HTTP Bearer credentials from Authorization header
        auth_service: AuthService instance
        
    Returns:
        bool: True if token is valid
        
    Raises:
        HTTPException: 401 if token is invalid or missing
        
    Validates: Requirements 5.1, 5.2
    """
    token = credentials.credentials
    
    if not auth_service.verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return True


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Login successful",
            "model": LoginResponse
        },
        401: {
            "description": "Invalid credentials",
            "model": ErrorResponse
        }
    },
    summary="Authenticate user",
    description="Authenticate with password and receive a JWT token for subsequent requests"
)
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> LoginResponse:
    """Authenticate user and return JWT token.
    
    This endpoint verifies the provided password and returns a JWT token
    if authentication is successful. The token should be included in the
    Authorization header of subsequent requests as a Bearer token.
    
    Args:
        request: Login request containing password
        auth_service: AuthService instance (injected)
        
    Returns:
        LoginResponse: JWT token and success message
        
    Raises:
        HTTPException: 401 if password is invalid
        
    Validates: Requirements 5.1, 5.2, 5.3
    """
    # Verify password
    if not auth_service.verify_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate token
    try:
        token = auth_service.generate_token()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate authentication token: {str(e)}"
        )
    
    return LoginResponse(token=token, message="Login successful")


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Logout successful",
            "model": LogoutResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        }
    },
    summary="Logout user",
    description="Logout the current user (client should discard the token)"
)
async def logout(
    authenticated: Annotated[bool, Depends(verify_token)]
) -> LogoutResponse:
    """Logout user.
    
    Since JWT tokens are stateless, logout is handled client-side by
    discarding the token. This endpoint simply validates that the user
    is authenticated and returns a success message.
    
    The client should:
    1. Remove the token from local storage
    2. Clear any cached user data
    3. Redirect to the login page
    
    Args:
        authenticated: Authentication verification (injected)
        
    Returns:
        LogoutResponse: Success message
        
    Raises:
        HTTPException: 401 if token is invalid or missing
        
    Validates: Requirements 5.2, 5.3
    """
    return LogoutResponse(message="Logout successful")
