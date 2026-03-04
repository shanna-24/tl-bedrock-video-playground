"""Configuration API endpoints.

This module provides endpoints for retrieving application configuration
that should be accessible to the frontend.

Note: These endpoints are public (no authentication required) as they
provide non-sensitive configuration data needed before login.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from config import Config
from main import get_config


router = APIRouter()


class ThemeConfigResponse(BaseModel):
    """Response model for theme configuration."""
    default_mode: str


@router.get("/theme", response_model=ThemeConfigResponse)
async def get_theme_config(config: Config = Depends(get_config)) -> ThemeConfigResponse:
    """Get theme configuration (public endpoint).
    
    This endpoint is publicly accessible as it provides the default theme
    setting which is needed before user authentication.
    
    Returns:
        ThemeConfigResponse: Theme configuration with default mode
    """
    return ThemeConfigResponse(default_mode=config.theme.default_mode)
