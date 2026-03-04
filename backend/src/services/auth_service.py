"""Authentication service for TL-Video-Playground.

This module handles password verification and JWT token management.
Validates: Requirements 5.1, 5.2, 5.3, 5.4
"""

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import jwt, JWTError

from config import Config


class AuthService:
    """Simple password-based authentication service.
    
    This service provides password verification using bcrypt and JWT token
    generation/verification for session management.
    
    Attributes:
        password_hash: Bcrypt hash of the authentication password
        secret_key: Secret key for JWT token signing
        algorithm: JWT algorithm (HS256)
        token_expiration_hours: Token expiration time in hours (default: 24)
    """
    
    def __init__(self, config: Config, secret_key: Optional[str] = None):
        """Initialize the authentication service.
        
        Args:
            config: System configuration containing password hash
            secret_key: Optional secret key for JWT signing. If not provided,
                       uses a default key (should be overridden in production)
        """
        self.password_hash = config.auth_password_hash
        self.secret_key = secret_key or "default-secret-key-change-in-production"
        self.algorithm = "HS256"
        self.token_expiration_hours = 24
    
    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash.
        
        Args:
            password: Plain text password to verify
            
        Returns:
            bool: True if password matches, False otherwise
            
        Validates: Requirements 5.1, 5.3
        """
        try:
            # Convert password to bytes
            password_bytes = password.encode('utf-8')
            hash_bytes = self.password_hash.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except Exception:
            # If verification fails for any reason (invalid hash format, etc.),
            # return False rather than raising an exception
            return False
    
    def generate_token(self) -> str:
        """Generate a JWT token for authenticated sessions.
        
        The token includes an expiration time and is signed with the secret key.
        
        Returns:
            str: JWT token string
            
        Validates: Requirements 5.2
        """
        expiration = datetime.utcnow() + timedelta(hours=self.token_expiration_hours)
        payload = {
            "exp": expiration,
            "iat": datetime.utcnow(),
            "authenticated": True
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> bool:
        """Verify a JWT token.
        
        Args:
            token: JWT token string to verify
            
        Returns:
            bool: True if token is valid and not expired, False otherwise
            
        Validates: Requirements 5.2
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload.get("authenticated", False)
        except JWTError:
            # Token is invalid (expired, malformed, wrong signature, etc.)
            return False
        except Exception:
            # Any other error should result in failed verification
            return False
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt.
        
        This is a utility method for generating password hashes to store
        in the configuration file.
        
        Args:
            password: Plain text password to hash
            
        Returns:
            str: Bcrypt hash of the password
        """
        password_bytes = password.encode('utf-8')
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        return hashed.decode('utf-8')
