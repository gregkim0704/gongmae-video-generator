"""
Text-to-Speech Generation Module
Adapted from quote-video-generator with support for Korean TTS
"""
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from src.config import settings
from src.utils.cache import get_cache_key, get_cached_file, cache_file


class TTSGenerator:
    """
    Handles text-to-speech generation with caching.
    Currently uses mock mode, with future support for Naver Clova TTS.
    """

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.cache_dir = settings.temp_dir / "audio_cache"
        self.cache_dir.mkdir(exist_ok=True)

    async def generate_speech(
        self,
        text: str,
        language: str = "ko-KR",
        voice_config: Optional[Dict[str, Any]] = None,
        output_filename: str = "speech.mp3",
        use_cache: bool = True
    ) -> str:
        """
        Generate speech from text.

        Args:
            text: Text to convert to speech
            language: Language code (ko-KR, en-US, etc.)
            voice_config: Voice configuration (speed, pitch, etc.)
            output_filename: Output filename
            use_cache: Whether to use cached audio

        Returns:
            Path to generated audio file
        """
        # Check cache
        if use_cache and settings.cache_enabled:
            cache_key = get_cache_key(text, language, str(voice_config))
            cached = get_cached_file(self.cache_dir, cache_key, ".mp3")
            if cached:
                print("Using cached audio")
                return str(cached)

        # Generate new audio
        print("Generating speech audio...")

        if voice_config is None:
            voice_config = {
                "speed": 1.0,
                "pitch": 0.0,
            }

        try:
            if self.mock_mode:
                # Use mock TTS
                from .mock_tts import MockTTSGenerator
                mock_tts = MockTTSGenerator()
                audio_path = await mock_tts.generate_speech(
                    text, output_filename
                )
            else:
                # Use real TTS (Naver Clova - to be implemented)
                audio_path = await self._generate_naver_tts(
                    text, language, voice_config, output_filename
                )

            # Cache the result
            if settings.cache_enabled:
                cache_key = get_cache_key(text, language, str(voice_config))
                cache_file(Path(audio_path), self.cache_dir, cache_key, ".mp3")

            return audio_path

        except Exception as e:
            raise Exception(f"TTS generation failed: {str(e)}")

    async def _generate_naver_tts(
        self,
        text: str,
        language: str,
        voice_config: Dict[str, Any],
        output_filename: str
    ) -> str:
        """
        Generate audio using Naver Clova TTS API.
        To be implemented when API access is available.
        """
        # Placeholder for Naver Clova TTS implementation
        # Would use settings.naver_client_id and settings.naver_client_secret

        # For now, fall back to mock
        print("Naver TTS not configured, using mock audio")
        from .mock_tts import MockTTSGenerator
        mock_tts = MockTTSGenerator()
        return await mock_tts.generate_speech(text, output_filename)

    async def get_audio_duration(self, audio_path: str) -> float:
        """Get duration of audio file in seconds"""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except Exception as e:
            print(f"Failed to get audio duration: {e}")
            # Estimate based on text length
            return 60.0  # Default fallback

    def cleanup_cache(self, keep_latest: int = 50):
        """Clean up old cached audio files"""
        from src.utils.cache import cleanup_cache
        deleted = cleanup_cache(self.cache_dir, keep_latest)
        if deleted > 0:
            print(f"Cleaned up {deleted} cached audio files")
