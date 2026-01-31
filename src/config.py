"""
Configuration management for Real Estate Auction Video Generator
Adapted from quote-video-generator
"""
import os
from pathlib import Path
from typing import Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings(BaseSettings):
    """Application settings"""

    # API Keys
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Naver TTS (optional)
    naver_client_id: Optional[str] = os.getenv("NAVER_CLIENT_ID")
    naver_client_secret: Optional[str] = os.getenv("NAVER_CLIENT_SECRET")

    # Server Configuration
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Paths
    base_dir: Path = Path(__file__).parent.parent
    output_dir: Path = base_dir / "output"
    temp_dir: Path = base_dir / "temp"
    assets_dir: Path = base_dir / "assets"
    data_dir: Path = base_dir / "data"
    mock_dir: Path = data_dir / "mock"

    # FFmpeg path (Windows - WinGet installation)
    ffmpeg_path: str = os.getenv("FFMPEG_PATH", r"C:\Users\Greg Kim\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin")

    # Video Settings
    default_width: int = int(os.getenv("DEFAULT_WIDTH", "1920"))
    default_height: int = int(os.getenv("DEFAULT_HEIGHT", "1080"))
    default_fps: int = int(os.getenv("DEFAULT_FPS", "30"))
    default_bitrate: str = os.getenv("DEFAULT_BITRATE", "5000k")

    # Audio Settings
    tts_language: str = os.getenv("TTS_LANGUAGE", "ko-KR")
    audio_bitrate: str = os.getenv("AUDIO_BITRATE", "192k")

    # Processing
    max_concurrent_jobs: int = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))
    cache_enabled: bool = os.getenv("CACHE_ENABLED", "True").lower() == "true"
    retry_attempts: int = int(os.getenv("RETRY_ATTEMPTS", "3"))

    # Channel/Brand
    channel_name: str = os.getenv("CHANNEL_NAME", "경매TV")

    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories if they don't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.mock_dir.mkdir(parents=True, exist_ok=True)

        # Add FFmpeg to PATH if not already there
        if self.ffmpeg_path and self.ffmpeg_path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = self.ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

    def validate_api_keys(self, mock_mode: bool = False) -> bool:
        """Validate that required API keys are set"""
        if mock_mode:
            return True
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required but not set in environment")
        return True


# Global settings instance
settings = Settings()
