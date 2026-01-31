"""
Audio generation modules for auction videos
"""
from .tts import TTSGenerator
from .mock_tts import MockTTSGenerator

__all__ = ["TTSGenerator", "MockTTSGenerator"]
