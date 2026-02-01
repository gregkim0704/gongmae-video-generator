"""
Video Composition Module using FFmpeg
Combines images, audio, and text into final auction video
Adapted from quote-video-generator
"""
import os
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any

import ffmpeg

from src.models import Scene, AspectRatio
from src.config import settings


class VideoComposer:
    """Handles video composition with FFmpeg"""

    def __init__(self):
        self.output_dir = settings.output_dir
        self.temp_dir = settings.temp_dir
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Check if FFmpeg is available"""
        try:
            ffmpeg.probe("test")
        except ffmpeg.Error:
            pass  # FFmpeg is available (probe fails on non-existent file, but that's ok)
        except FileNotFoundError:
            raise Exception(
                "FFmpeg not found. Please install FFmpeg or set FFMPEG_PATH in .env"
            )

    # Available transition effects
    TRANSITION_EFFECTS = {
        "fade": "fade",           # Crossfade
        "slide": "slideleft",     # Slide from right to left
        "zoom": "circleopen",     # Zoom/circle open
        "dissolve": "dissolve",   # Dissolve
        "wipe": "wiperight",      # Wipe right
        "none": None              # No transition (hard cut)
    }

    async def compose_video(
        self,
        scenes: List[Scene],
        audio_path: str,
        output_filename: str = "output.mp4",
        aspect_ratio: AspectRatio = AspectRatio.LANDSCAPE,
        apply_effects: bool = True,
        transition_type: str = "fade"
    ) -> str:
        """
        Compose final video from scenes and audio.

        Args:
            scenes: List of scenes with images and durations
            audio_path: Path to narration audio
            output_filename: Output video filename
            aspect_ratio: Video aspect ratio
            apply_effects: Apply pan/zoom (Ken Burns) effects
            transition_type: Transition effect between scenes (fade, slide, zoom, dissolve, wipe, none)

        Returns:
            Path to final video file
        """
        print(f"Starting video composition with {transition_type} transition...")

        try:
            # Get video dimensions
            width, height = self._get_dimensions(aspect_ratio)

            # Get transition effect name
            transition_effect = self.TRANSITION_EFFECTS.get(transition_type, "fade")

            # Create temporary video segments for each scene
            scene_videos = []
            for scene in scenes:
                scene_video = await self._create_scene_video(
                    scene,
                    width,
                    height,
                    apply_effects
                )
                scene_videos.append(scene_video)

            # Concatenate scene videos with transitions
            concatenated = await self._concatenate_scenes_with_transitions(
                scene_videos, transition_effect
            )

            # Add audio
            final_video = await self._add_audio(concatenated, audio_path)

            # Move to output directory
            output_path = self.output_dir / output_filename
            if Path(final_video) != output_path:
                os.replace(final_video, output_path)

            # Cleanup temp files
            self._cleanup_temp_videos(scene_videos)

            print(f"Video composition complete: {output_path}")
            return str(output_path)

        except Exception as e:
            raise Exception(f"Video composition failed: {str(e)}")

    def _get_dimensions(self, aspect_ratio: AspectRatio) -> tuple:
        """Get video dimensions based on aspect ratio"""
        dimensions = {
            AspectRatio.LANDSCAPE: (settings.default_width, settings.default_height),
            AspectRatio.PORTRAIT: (1080, 1920),
            AspectRatio.SQUARE: (1080, 1080)
        }
        return dimensions.get(aspect_ratio, (1920, 1080))

    async def _create_scene_video(
        self,
        scene: Scene,
        width: int,
        height: int,
        apply_effects: bool
    ) -> str:
        """
        Create video segment for a single scene.
        Applies Ken Burns effect (pan/zoom) for dynamic feel.
        """
        if not scene.image_path or not os.path.exists(scene.image_path):
            raise Exception(f"Image not found for scene {scene.scene_id}: {scene.image_path}")

        output_path = self.temp_dir / f"scene_{scene.scene_id}.mp4"

        try:
            # Create FFmpeg input
            input_stream = ffmpeg.input(
                scene.image_path,
                loop=1,
                t=scene.duration
            )

            # Apply video effects
            if apply_effects:
                # Ken Burns effect (slow zoom)
                video = input_stream.video.filter(
                    'zoompan',
                    z='min(zoom+0.0015,1.3)',  # Slow zoom in
                    d=int(scene.duration * settings.default_fps),
                    s=f'{width}x{height}',
                    fps=settings.default_fps
                )
            else:
                # Simple scale to target size
                video = input_stream.video.filter(
                    'scale',
                    width,
                    height,
                    force_original_aspect_ratio='decrease'
                ).filter(
                    'pad',
                    width,
                    height,
                    '(ow-iw)/2',
                    '(oh-ih)/2'
                )

            # Set pixel format and frame rate
            video = video.filter('fps', fps=settings.default_fps)
            video = video.filter('format', 'yuv420p')

            # Output
            output = ffmpeg.output(
                video,
                str(output_path),
                vcodec='libx264',
                preset='medium',
                crf=23
            )

            # Run FFmpeg
            await asyncio.to_thread(
                ffmpeg.run,
                output,
                overwrite_output=True,
                quiet=True
            )

            return str(output_path)

        except Exception as e:
            raise Exception(f"Failed to create scene {scene.scene_id} video: {str(e)}")

    async def _concatenate_scenes(self, scene_videos: List[str]) -> str:
        """Concatenate multiple scene videos (simple, no transitions)"""
        if not scene_videos:
            raise Exception("No scene videos to concatenate")

        if len(scene_videos) == 1:
            return scene_videos[0]

        # Create concat file list
        concat_file = self.temp_dir / "concat_list.txt"
        with open(concat_file, 'w') as f:
            for video_path in scene_videos:
                # FFmpeg concat format - use forward slashes
                video_path_fixed = video_path.replace('\\', '/')
                f.write(f"file '{video_path_fixed}'\n")

        output_path = self.temp_dir / "concatenated.mp4"

        try:
            # Concatenate using concat demuxer
            input_stream = ffmpeg.input(str(concat_file), format='concat', safe=0)

            output = ffmpeg.output(
                input_stream,
                str(output_path),
                c='copy'  # Copy codec without re-encoding
            )

            await asyncio.to_thread(
                ffmpeg.run,
                output,
                overwrite_output=True,
                quiet=True
            )

            return str(output_path)

        except Exception as e:
            raise Exception(f"Failed to concatenate scenes: {str(e)}")

    async def _concatenate_scenes_with_transitions(
        self,
        scene_videos: List[str],
        transition_effect: Optional[str] = "fade"
    ) -> str:
        """
        Concatenate scene videos with artistic transition effects.

        Uses FFmpeg xfade filter for smooth transitions between clips.

        Args:
            scene_videos: List of video paths
            transition_effect: FFmpeg xfade transition name (fade, dissolve, etc.)

        Returns:
            Path to concatenated video
        """
        if not scene_videos:
            raise Exception("No scene videos to concatenate")

        if len(scene_videos) == 1:
            return scene_videos[0]

        # If no transition, use simple concatenation
        if not transition_effect:
            return await self._concatenate_scenes(scene_videos)

        output_path = self.temp_dir / "concatenated.mp4"
        transition_duration = 0.5  # 0.5 second transition

        try:
            # Get durations of each video
            durations = []
            for video_path in scene_videos:
                probe = ffmpeg.probe(video_path)
                duration = float(probe['format']['duration'])
                durations.append(duration)

            # Build complex filter for xfade transitions
            # FFmpeg xfade syntax: [0:v][1:v]xfade=transition=fade:duration=0.5:offset=OFFSET[v01]
            inputs = [ffmpeg.input(v) for v in scene_videos]

            # Chain xfade filters
            current_video = inputs[0].video
            cumulative_offset = 0

            for i in range(1, len(inputs)):
                # Calculate offset (end of previous clip minus transition overlap)
                offset = durations[i-1] - transition_duration + cumulative_offset
                if offset < 0:
                    offset = cumulative_offset + 0.1  # Minimum offset

                # Apply xfade transition
                current_video = ffmpeg.filter(
                    [current_video, inputs[i].video],
                    'xfade',
                    transition=transition_effect,
                    duration=transition_duration,
                    offset=offset
                )

                # Update cumulative offset for next transition
                cumulative_offset = offset

            # Output with re-encoding (required for xfade)
            output = ffmpeg.output(
                current_video,
                str(output_path),
                vcodec='libx264',
                preset='medium',
                crf=23,
                pix_fmt='yuv420p'
            )

            print(f"Applying {transition_effect} transitions...")
            await asyncio.to_thread(
                ffmpeg.run,
                output,
                overwrite_output=True,
                quiet=True
            )

            return str(output_path)

        except Exception as e:
            print(f"Transition failed, falling back to simple concat: {e}")
            # Fallback to simple concatenation if xfade fails
            return await self._concatenate_scenes(scene_videos)

    async def _add_audio(
        self,
        video_path: str,
        audio_path: str
    ) -> str:
        """Add audio track to video"""
        output_path = self.temp_dir / "with_audio.mp4"

        try:
            video = ffmpeg.input(video_path)
            audio = ffmpeg.input(audio_path)

            # Combine video and audio
            output = ffmpeg.output(
                video.video,
                audio.audio,
                str(output_path),
                vcodec='copy',
                acodec='aac',
                audio_bitrate=settings.audio_bitrate,
                shortest=None  # Match shorter stream
            )

            await asyncio.to_thread(
                ffmpeg.run,
                output,
                overwrite_output=True,
                quiet=True
            )

            return str(output_path)

        except Exception as e:
            raise Exception(f"Failed to add audio: {str(e)}")

    def _cleanup_temp_videos(self, scene_videos: List[str]):
        """Clean up temporary video files"""
        patterns = [
            "scene_*.mp4",
            "concatenated.mp4",
            "concat_list.txt"
        ]

        for pattern in patterns:
            for file in self.temp_dir.glob(pattern):
                try:
                    file.unlink()
                except Exception:
                    pass

    async def create_simple_video(
        self,
        images: List[Path],
        audio_path: str,
        durations: List[float],
        output_filename: str = "output.mp4"
    ) -> str:
        """
        Simplified video creation from a list of images.

        Args:
            images: List of image paths
            audio_path: Path to audio file
            durations: Duration for each image in seconds
            output_filename: Output filename

        Returns:
            Path to output video
        """
        from src.models import ScriptSection

        # Create scenes from images
        scenes = []
        for i, (img_path, duration) in enumerate(zip(images, durations)):
            scene = Scene(
                scene_id=i,
                section=ScriptSection.INTRO,  # Placeholder
                text="",
                duration=duration,
                image_path=str(img_path)
            )
            scenes.append(scene)

        return await self.compose_video(
            scenes=scenes,
            audio_path=audio_path,
            output_filename=output_filename
        )
