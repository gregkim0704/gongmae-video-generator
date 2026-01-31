"""
Mock TTS Generator for testing without API costs
Generates silent audio with correct duration based on text length
"""
import asyncio
from pathlib import Path

from src.config import settings


class MockTTSGenerator:
    """
    Generates silent audio files with duration based on text length.
    Used for development and testing without TTS API costs.
    """

    def __init__(self):
        self.output_dir = settings.temp_dir / "audio"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Korean speech rate: approximately 300-400 syllables per minute
        self.syllables_per_minute = 350

    async def generate_speech(
        self,
        text: str,
        output_filename: str = "speech.mp3"
    ) -> str:
        """
        Generate a silent audio file with duration based on text length.

        Args:
            text: Text that would be spoken
            output_filename: Output filename

        Returns:
            Path to generated audio file
        """
        output_path = self.output_dir / output_filename

        # Calculate duration based on text length
        duration = self._estimate_duration(text)

        print(f"Generating mock audio ({duration:.1f} seconds)...")

        # Generate silent audio with pydub
        await self._generate_silent_audio(output_path, duration)

        return str(output_path)

    def _estimate_duration(self, text: str) -> float:
        """
        Estimate speech duration for Korean text.

        Args:
            text: The text to be spoken

        Returns:
            Estimated duration in seconds
        """
        # Remove whitespace for character count
        char_count = len(text.replace(" ", "").replace("\n", ""))

        # Calculate duration based on syllables per minute
        duration_minutes = char_count / self.syllables_per_minute
        duration_seconds = duration_minutes * 60

        # Minimum 5 seconds, maximum 10 minutes
        return max(5.0, min(duration_seconds, 600.0))

    async def _generate_silent_audio(
        self,
        output_path: Path,
        duration: float
    ) -> None:
        """
        Generate a silent (very quiet) audio file.

        Args:
            output_path: Where to save the audio
            duration: Duration in seconds
        """
        try:
            from pydub import AudioSegment
            from pydub.generators import Sine

            # Generate a very quiet tone (effectively silent)
            # Using a low frequency sine wave at very low volume
            audio = Sine(220).to_audio_segment(
                duration=int(duration * 1000)
            ).apply_gain(-60)  # Very quiet

            # Export as MP3
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: audio.export(
                    str(output_path),
                    format="mp3",
                    bitrate=settings.audio_bitrate
                )
            )

        except ImportError:
            # Fallback: create empty file if pydub not available
            print("Warning: pydub not available, creating empty audio file")
            output_path.touch()

    async def get_audio_duration(self, audio_path: str) -> float:
        """Get duration of audio file in seconds"""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except Exception as e:
            print(f"Failed to get audio duration: {e}")
            return 60.0  # Default fallback
