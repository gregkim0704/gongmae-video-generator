"""
Video Generation Pipeline Orchestrator
Coordinates all components to generate auction videos
"""
import asyncio
import uuid
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

from src.models import (
    AuctionProperty, AuctionScript, Scene, VideoJob,
    JobStatus, ScriptSection
)
from src.config import settings
from src.scraper import MockScraper, CourtAuctionScraper, JsonFileScraper
from src.script import ScriptWriter
from src.audio import TTSGenerator
from src.video import VideoComposer


class VideoGenerationPipeline:
    """
    Main orchestrator for the video generation pipeline.

    Coordinates:
    1. Property data collection (scraping)
    2. Script generation
    3. TTS audio generation
    4. Video composition

    입력 모드:
    - mock: 목업 데이터 사용 (개발/테스트용)
    - json: JSON 파일에서 물건 정보 읽기 (권장)
    - crawl: 대법원 사이트 크롤링 (불안정)
    """

    def __init__(
        self,
        mock_mode: bool = True,
        input_mode: str = "auto",
        headless: bool = True
    ):
        """
        Args:
            mock_mode: 목업 모드 사용 여부 (True면 mock 모드)
            input_mode: 입력 모드 ("auto", "mock", "json", "crawl")
            headless: 크롤링 시 브라우저 숨김 모드
        """
        self.mock_mode = mock_mode
        self.input_mode = input_mode

        # 스크래퍼 선택
        if input_mode == "mock" or (input_mode == "auto" and mock_mode):
            self.scraper = MockScraper()
            self._scraper_type = "mock"
        elif input_mode == "json" or (input_mode == "auto" and not mock_mode):
            self.scraper = JsonFileScraper()
            self._scraper_type = "json"
        elif input_mode == "crawl":
            self.scraper = CourtAuctionScraper(headless=headless)
            self._scraper_type = "crawl"
        else:
            self.scraper = MockScraper()
            self._scraper_type = "mock"

        self.script_writer = ScriptWriter(mock_mode=mock_mode)
        self.tts = TTSGenerator(mock_mode=mock_mode)
        self.video_composer = VideoComposer()

        # Job tracking
        self.current_job: Optional[VideoJob] = None

    async def generate_video(
        self,
        case_number: str,
        output_filename: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """
        Generate a complete auction video from a case number.

        Args:
            case_number: The auction case number (e.g., "2024타경12345")
            output_filename: Custom output filename (optional)
            progress_callback: Callback function(progress_percent, step_name)

        Returns:
            Path to the generated video file
        """
        # Initialize job
        job_id = str(uuid.uuid4())[:8]
        self.current_job = VideoJob(
            job_id=job_id,
            case_number=case_number,
            status=JobStatus.PROCESSING
        )

        def update_progress(progress: int, step: str):
            if self.current_job:
                self.current_job.progress = progress
                self.current_job.current_step = step
            if progress_callback:
                progress_callback(progress, step)
            print(f"[{progress}%] {step}")

        try:
            # Step 1: Fetch property data (10%)
            update_progress(10, "Fetching property data...")
            property_data = await self.scraper.get_property(case_number)

            if not property_data:
                raise ValueError(f"Property not found: {case_number}")

            self.current_job.property_data = property_data

            # Step 2: Download/generate images (25%)
            update_progress(25, "Preparing property images...")
            images_dir = settings.temp_dir / "images" / job_id
            image_paths = await self.scraper.download_images(property_data, images_dir)

            if not image_paths:
                raise ValueError("No images available for video")

            # Step 3: Generate script (40%)
            update_progress(40, "Generating script...")
            script = await self.script_writer.generate_script(property_data)
            self.current_job.script = script

            print(f"\n--- Generated Script ---\n{script.full_script}\n")
            print(f"Estimated duration: {script.estimated_duration:.1f} seconds\n")

            # Step 4: Generate audio (55%)
            update_progress(55, "Generating audio narration...")
            audio_filename = f"{job_id}_narration.mp3"
            audio_path = await self.tts.generate_speech(
                script.full_script,
                output_filename=audio_filename
            )
            self.current_job.audio_path = audio_path

            # Get actual audio duration
            audio_duration = await self.tts.get_audio_duration(audio_path)

            # Step 5: Create scenes (70%)
            update_progress(70, "Creating video scenes...")
            scenes = self._create_scenes(
                script,
                image_paths,
                audio_duration
            )
            self.current_job.scenes = scenes

            # Step 6: Compose video (85%)
            update_progress(85, "Composing final video...")
            if output_filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_case = case_number.replace("/", "_").replace("\\", "_")
                output_filename = f"{safe_case}_{timestamp}.mp4"

            video_path = await self.video_composer.compose_video(
                scenes=scenes,
                audio_path=audio_path,
                output_filename=output_filename
            )
            self.current_job.video_path = video_path

            # Step 7: Cleanup and finish (100%)
            update_progress(100, "Video generation complete!")
            self.current_job.status = JobStatus.COMPLETED

            return video_path

        except Exception as e:
            if self.current_job:
                self.current_job.status = JobStatus.FAILED
                self.current_job.error = str(e)
            raise

    def _create_scenes(
        self,
        script: AuctionScript,
        image_paths: list,
        total_duration: float
    ) -> list:
        """
        Create video scenes from script sections and images.

        Distributes images across script sections based on content length.
        """
        scenes = []
        section_durations = self.script_writer.get_section_durations(script)

        # Map sections to images
        section_order = [
            ScriptSection.INTRO,
            ScriptSection.CASE_OVERVIEW,
            ScriptSection.PRICE_INFO,
            ScriptSection.LOCATION_ANALYSIS,
            ScriptSection.PROPERTY_DETAILS,
            ScriptSection.LEGAL_NOTES,
            ScriptSection.CLOSING,
        ]

        # Calculate duration per image
        num_images = len(image_paths)
        if num_images == 0:
            raise ValueError("No images available for video")

        # Distribute images across sections
        images_per_section = max(1, num_images // len(section_order))
        image_index = 0

        for i, section in enumerate(section_order):
            section_key = section.value
            if section_key not in script.sections:
                continue

            section_text = script.sections[section_key]
            section_duration = section_durations.get(section_key, total_duration / len(section_order))

            # Get image for this section
            if image_index < num_images:
                image_path = str(image_paths[image_index])
                image_index += 1
            else:
                # Reuse last image if we run out
                image_path = str(image_paths[-1])

            scene = Scene(
                scene_id=i,
                section=section,
                text=section_text,
                duration=section_duration,
                image_path=image_path
            )
            scenes.append(scene)

        # Adjust durations to match total audio duration
        total_scene_duration = sum(s.duration for s in scenes)
        if total_scene_duration > 0 and abs(total_scene_duration - total_duration) > 0.5:
            ratio = total_duration / total_scene_duration
            for scene in scenes:
                scene.duration *= ratio

        return scenes

    def get_job_status(self) -> Optional[VideoJob]:
        """Get current job status"""
        return self.current_job


async def generate_auction_video(
    case_number: str,
    mock_mode: bool = True,
    output_filename: Optional[str] = None
) -> str:
    """
    Convenience function to generate an auction video.

    Args:
        case_number: The auction case number
        mock_mode: Whether to use mock data/audio
        output_filename: Custom output filename

    Returns:
        Path to the generated video
    """
    pipeline = VideoGenerationPipeline(mock_mode=mock_mode)
    return await pipeline.generate_video(
        case_number=case_number,
        output_filename=output_filename
    )
