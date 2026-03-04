"""FFmpeg utility for getting the correct ffmpeg binary path."""

import os
import shutil
import logging

logger = logging.getLogger(__name__)


def get_ffmpeg_path() -> str:
    """Get the path to the ffmpeg binary.
    
    Checks in order:
    1. FFMPEG_PATH environment variable (set by Electron app)
    2. System PATH (for development and standalone usage)
    
    Returns:
        Path to ffmpeg binary
        
    Raises:
        RuntimeError: If ffmpeg is not found
    """
    # Check environment variable first (Electron app sets this)
    ffmpeg_env = os.environ.get('FFMPEG_PATH')
    if ffmpeg_env and os.path.isfile(ffmpeg_env):
        logger.debug(f"Using ffmpeg from FFMPEG_PATH: {ffmpeg_env}")
        return ffmpeg_env
    
    # Fall back to system PATH
    ffmpeg_system = shutil.which('ffmpeg')
    if ffmpeg_system:
        logger.debug(f"Using ffmpeg from system PATH: {ffmpeg_system}")
        return ffmpeg_system
    
    # Not found
    raise RuntimeError(
        "ffmpeg not found. Please install ffmpeg:\n"
        "  macOS: brew install ffmpeg\n"
        "  Linux: apt-get install ffmpeg\n"
        "  Windows: Download from https://ffmpeg.org/download.html"
    )


def get_ffprobe_path() -> str:
    """Get the path to the ffprobe binary.
    
    ffprobe is typically bundled with ffmpeg, so we check the same locations.
    
    Checks in order:
    1. FFMPEG_PATH environment variable (derive ffprobe path from ffmpeg path)
    2. System PATH (for development and standalone usage)
    
    Returns:
        Path to ffprobe binary
        
    Raises:
        RuntimeError: If ffprobe is not found
    """
    # Check if FFMPEG_PATH is set, derive ffprobe path
    ffmpeg_env = os.environ.get('FFMPEG_PATH')
    if ffmpeg_env:
        # Get the directory and replace the filename
        ffmpeg_dir = os.path.dirname(ffmpeg_env)
        ffprobe_env = os.path.join(ffmpeg_dir, 'ffprobe')
        if os.path.isfile(ffprobe_env):
            logger.debug(f"Using ffprobe derived from FFMPEG_PATH: {ffprobe_env}")
            return ffprobe_env
        else:
            logger.warning(f"ffprobe not found at derived path: {ffprobe_env}")
    
    # Fall back to system PATH
    ffprobe_system = shutil.which('ffprobe')
    if ffprobe_system:
        logger.debug(f"Using ffprobe from system PATH: {ffprobe_system}")
        return ffprobe_system
    
    # Not found
    raise RuntimeError(
        "ffprobe not found. Please install ffmpeg (includes ffprobe):\n"
        "  macOS: brew install ffmpeg\n"
        "  Linux: apt-get install ffmpeg\n"
        "  Windows: Download from https://ffmpeg.org/download.html"
    )
