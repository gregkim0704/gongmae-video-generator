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
    Uses Edge TTS (Microsoft) - FREE, no API key required.
    """

    # Korean voices available in Edge TTS
    KOREAN_VOICES = {
        "female": "ko-KR-SunHiNeural",  # 여성 (기본)
        "male": "ko-KR-InJoonNeural",   # 남성
    }

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
                # Use Edge TTS (FREE - Microsoft)
                audio_path = await self._generate_edge_tts(
                    text, language, voice_config, output_filename
                )

            # Cache the result
            if settings.cache_enabled:
                cache_key = get_cache_key(text, language, str(voice_config))
                cache_file(Path(audio_path), self.cache_dir, cache_key, ".mp3")

            return audio_path

        except Exception as e:
            raise Exception(f"TTS generation failed: {str(e)}")

    async def _generate_edge_tts(
        self,
        text: str,
        language: str,
        voice_config: Dict[str, Any],
        output_filename: str
    ) -> str:
        """
        Generate audio using Edge TTS (Microsoft).
        FREE - No API key required!
        https://github.com/rany2/edge-tts
        """
        import edge_tts

        # Select voice
        gender = voice_config.get("gender", "female") if voice_config else "female"
        voice = self.KOREAN_VOICES.get(gender, self.KOREAN_VOICES["female"])

        # Speed/rate adjustment (e.g., "+10%", "-20%")
        rate = voice_config.get("rate", "+0%") if voice_config else "+0%"
        if isinstance(rate, (int, float)):
            rate = f"+{int(rate)}%" if rate >= 0 else f"{int(rate)}%"

        # Volume adjustment
        volume = voice_config.get("volume", "+0%") if voice_config else "+0%"
        if isinstance(volume, (int, float)):
            volume = f"+{int(volume)}%" if volume >= 0 else f"{int(volume)}%"

        output_path = settings.temp_dir / output_filename

        print(f"Edge TTS 생성 중... (음성: {voice})")

        try:
            # Create communicate object
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate,
                volume=volume
            )

            # Generate audio
            await communicate.save(str(output_path))

            print(f"TTS 생성 완료: {output_path}")
            return str(output_path)

        except Exception as e:
            print(f"Edge TTS 오류: {e}")
            # Fallback to mock
            print("mock 오디오로 대체합니다...")
            from .mock_tts import MockTTSGenerator
            mock_tts = MockTTSGenerator()
            return await mock_tts.generate_speech(text, output_filename)

    def _split_text(self, text: str, max_chars: int) -> list:
        """Split text into chunks, preferring sentence boundaries"""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by sentences
        import re
        sentences = re.split(r'(?<=[.!?。])\s*', text)

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_chars:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Handle very long sentences
                if len(sentence) > max_chars:
                    # Split by commas or spaces
                    words = sentence.split()
                    current_chunk = ""
                    for word in words:
                        if len(current_chunk) + len(word) + 1 <= max_chars:
                            current_chunk += word + " "
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = word + " "
                else:
                    current_chunk = sentence + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def _concatenate_audio(self, audio_files: list, output_path: Path):
        """Concatenate multiple audio files into one"""
        from pydub import AudioSegment

        combined = AudioSegment.empty()
        for audio_file in audio_files:
            segment = AudioSegment.from_mp3(str(audio_file))
            combined += segment

        await asyncio.to_thread(
            combined.export,
            str(output_path),
            format="mp3",
            bitrate="192k"
        )

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
