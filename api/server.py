"""
FastAPI Backend Server for Video Generation
Handles async video generation jobs
"""
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import VideoGenerationPipeline
from src.scraper import create_template_file, PdfAppraisalScraper
from src.config import settings


# In-memory job storage (use Redis in production)
jobs: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print("Video Generation API Server starting...")
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown
    print("Server shutting down...")


app = FastAPI(
    title="Auction Video Generator API",
    description="Generate auction property introduction videos",
    version="0.1.0",
    lifespan=lifespan
)

# CORS configuration for Vercel frontend
import os
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
allowed_origins = [
    "http://localhost:3000",
]
# Add Vercel URLs (supports pattern matching)
if FRONTEND_URL:
    allowed_origins.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Vercel preview/production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class VideoGenerationRequest(BaseModel):
    """Request to generate a video"""
    case_number: str
    input_mode: str = "mock"  # mock, json
    mock_mode: bool = True
    output_filename: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Job status response"""
    job_id: str
    status: str  # pending, processing, completed, failed, script_ready
    progress: int
    current_step: Optional[str] = None
    video_url: Optional[str] = None
    script_url: Optional[str] = None
    script: Optional[str] = None  # Generated script content
    error: Optional[str] = None
    created_at: str
    updated_at: str


class RegenerateRequest(BaseModel):
    """Request to regenerate video with edited script"""
    script: str
    transition: str = "fade"  # fade, slide, zoom, dissolve, none


class PropertyData(BaseModel):
    """Property data for JSON input"""
    case_number: str
    court: str
    asset_type: str = "OTHER"
    asset_type_name: str = "Other"
    address: str
    appraisal_value: int
    minimum_bid: int
    auction_date: str
    # Optional fields
    address_detail: Optional[str] = None
    region: Optional[str] = None
    district: Optional[str] = None
    land_area: Optional[float] = None
    building_area: Optional[float] = None
    floor: Optional[str] = None
    build_year: Optional[int] = None
    minimum_bid_percent: Optional[float] = None
    auction_round: int = 1
    risk_level: str = "caution"
    has_occupant: bool = False
    has_lease: bool = False


# Background task for video generation
async def generate_video_task(job_id: str, request: VideoGenerationRequest):
    """Background task to generate video"""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()

        def progress_callback(progress: int, step: str):
            jobs[job_id]["progress"] = progress
            jobs[job_id]["current_step"] = step
            jobs[job_id]["updated_at"] = datetime.now().isoformat()

        pipeline = VideoGenerationPipeline(
            mock_mode=request.mock_mode,
            input_mode=request.input_mode
        )

        video_path = await pipeline.generate_video(
            case_number=request.case_number,
            output_filename=request.output_filename,
            progress_callback=progress_callback
        )

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["video_path"] = video_path
        jobs[job_id]["video_url"] = f"/api/videos/{Path(video_path).name}"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["updated_at"] = datetime.now().isoformat()


# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Auction Video Generator API",
        "version": "0.1.0"
    }


@app.post("/api/jobs", response_model=JobStatusResponse)
async def create_job(
    request: VideoGenerationRequest,
    background_tasks: BackgroundTasks
):
    """Create a new video generation job"""
    job_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "current_step": "Initializing...",
        "video_url": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "request": request.model_dump()
    }

    # Start background task
    background_tasks.add_task(generate_video_task, job_id, request)

    return JobStatusResponse(**jobs[job_id])


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get job status by ID"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**jobs[job_id])


@app.get("/api/jobs")
async def list_jobs(limit: int = 10):
    """List recent jobs"""
    sorted_jobs = sorted(
        jobs.values(),
        key=lambda x: x["created_at"],
        reverse=True
    )[:limit]
    return {"jobs": sorted_jobs}


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs.pop(job_id)

    # Delete video file if exists
    if job.get("video_path"):
        video_path = Path(job["video_path"])
        if video_path.exists():
            video_path.unlink()

    return {"status": "deleted", "job_id": job_id}


@app.get("/api/videos/{filename}")
async def get_video(filename: str):
    """Download generated video"""
    video_path = settings.output_dir / filename

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=filename
    )


@app.post("/api/properties")
async def upload_property(property_data: PropertyData):
    """Upload property data as JSON and save to input directory"""
    import json

    input_dir = settings.data_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    safe_case = property_data.case_number.replace("/", "_").replace("\\", "_")
    json_path = input_dir / f"{safe_case}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(property_data.model_dump(), f, ensure_ascii=False, indent=2)

    return {
        "status": "saved",
        "case_number": property_data.case_number,
        "path": str(json_path)
    }


@app.get("/api/properties")
async def list_properties(input_mode: str = "mock"):
    """List available properties"""
    from src.scraper import MockScraper, JsonFileScraper

    if input_mode == "json":
        scraper = JsonFileScraper()
    else:
        scraper = MockScraper()

    properties = await scraper.search_properties(limit=100)

    return {
        "properties": [
            {
                "case_number": p.case_number,
                "court": p.court,
                "asset_type": p.asset_type.value,
                "asset_type_name": p.asset_type_name,
                "address": p.address,
                "appraisal_value": p.appraisal_value,
                "minimum_bid": p.minimum_bid,
                "auction_date": p.auction_date
            }
            for p in properties
        ]
    }


@app.get("/api/template")
async def get_template():
    """Get JSON template for property data"""
    return {
        "_help": "Fill in the fields below with auction property data",
        "_reference": "https://www.courtauction.go.kr",
        "case_number": "2024XXXX12345",
        "court": "Example Court",
        "asset_type": "APT",
        "asset_type_name": "Apartment",
        "address": "Full address here",
        "appraisal_value": 100000000,
        "minimum_bid": 80000000,
        "auction_date": "2024-12-31",
        "auction_round": 1,
        "risk_level": "caution"
    }


# PDF Upload and Video Generation
async def generate_pdf_script_task(job_id: str, pdf_path: str):
    """Background task to generate script from PDF (Phase 1)"""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()

        def update_progress(progress: int, step: str):
            jobs[job_id]["progress"] = progress
            jobs[job_id]["current_step"] = step
            jobs[job_id]["updated_at"] = datetime.now().isoformat()
            print(f"[{progress}%] {step}")

        # Step 1: Initialize PDF scraper
        update_progress(10, "PDF 파일 처리 중...")
        scraper = PdfAppraisalScraper()
        scraper.set_pdf(pdf_path)

        # Step 2: Convert PDF to images
        update_progress(25, "PDF를 이미지로 변환 중...")
        images_dir = settings.temp_dir / "pdf_images" / job_id
        image_paths = await scraper.convert_pdf_to_images(images_dir)

        if not image_paths:
            raise ValueError("PDF에서 이미지를 추출할 수 없습니다")

        # Step 3: Extract text from images using Claude Vision
        update_progress(50, "이미지에서 텍스트 추출 중...")
        await scraper.extract_text_from_images()

        # Step 4: Generate narration script
        update_progress(75, "나레이션 스크립트 생성 중...")
        narration_script = await scraper.generate_summary()

        print(f"\n--- Generated Script ---\n{narration_script[:500]}...\n")

        # Save script to file
        script_dir = settings.temp_dir / "scripts"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_path = script_dir / f"{job_id}_script.txt"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(narration_script)

        # Save image paths for later use
        jobs[job_id]["image_paths"] = [str(p) for p in image_paths]
        jobs[job_id]["script"] = narration_script
        jobs[job_id]["script_path"] = str(script_path)

        # Step 5: Mark as script ready - wait for user confirmation
        update_progress(100, "스크립트 생성 완료! 확인 후 영상 생성을 진행해주세요.")
        jobs[job_id]["status"] = "script_ready"
        jobs[job_id]["script_url"] = f"/api/jobs/{job_id}/script"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()

    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["updated_at"] = datetime.now().isoformat()


async def generate_video_from_script_task(job_id: str, script: str, transition: str = "fade"):
    """Background task to generate video from script (Phase 2)"""
    from src.video import VideoComposer
    from src.audio import TTSGenerator
    from src.models import Scene, ScriptSection

    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()

        def update_progress(progress: int, step: str):
            jobs[job_id]["progress"] = progress
            jobs[job_id]["current_step"] = step
            jobs[job_id]["updated_at"] = datetime.now().isoformat()
            print(f"[{progress}%] {step}")

        # Get saved image paths
        image_paths = jobs[job_id].get("image_paths", [])
        if not image_paths:
            raise ValueError("이미지 경로를 찾을 수 없습니다")

        # Step 1: Generate TTS audio with edited script
        update_progress(20, "음성 생성 중 (Edge TTS)...")
        tts = TTSGenerator(mock_mode=False)  # Use real TTS
        audio_filename = f"{job_id}_narration.mp3"
        audio_path = await tts.generate_speech(
            script,
            output_filename=audio_filename
        )

        # Get audio duration
        update_progress(40, "오디오 분석 중...")
        audio_duration = await tts.get_audio_duration(audio_path)

        # Step 2: Create scenes (distribute duration across pages)
        update_progress(60, "영상 장면 구성 중...")
        num_images = len(image_paths)
        duration_per_image = audio_duration / num_images if num_images > 0 else 5.0

        scenes = []
        for i, img_path in enumerate(image_paths):
            scene = Scene(
                scene_id=i,
                section=ScriptSection.INTRO,
                text=f"페이지 {i+1}",
                duration=duration_per_image,
                image_path=str(img_path)
            )
            scenes.append(scene)

        # Step 3: Compose video with selected transition
        update_progress(80, f"슬라이드쇼 영상 생성 중 ({transition} 효과)...")
        composer = VideoComposer()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"pdf_appraisal_{timestamp}.mp4"

        video_path = await composer.compose_video(
            scenes=scenes,
            audio_path=audio_path,
            output_filename=output_filename,
            apply_effects=False,
            transition_type=transition
        )

        # Step 4: Complete
        update_progress(100, "영상 생성 완료!")
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["video_path"] = video_path
        jobs[job_id]["video_url"] = f"/api/videos/{Path(video_path).name}"
        jobs[job_id]["final_script"] = script
        jobs[job_id]["transition"] = transition
        jobs[job_id]["updated_at"] = datetime.now().isoformat()

    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["updated_at"] = datetime.now().isoformat()


@app.get("/api/jobs/{job_id}/script")
async def get_script(job_id: str):
    """Download the generated script as a text file"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    script = job.get("script")

    if not script:
        raise HTTPException(status_code=404, detail="Script not found for this job")

    # Return as downloadable text file
    from fastapi.responses import Response
    return Response(
        content=script,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{job_id}_script.txt"'
        }
    )


@app.post("/api/jobs/{job_id}/regenerate", response_model=JobStatusResponse)
async def regenerate_video(
    job_id: str,
    request: RegenerateRequest,
    background_tasks: BackgroundTasks
):
    """
    Regenerate video with edited script and selected transition.

    This endpoint is called after the user edits the script and selects
    a transition effect. It generates TTS audio from the edited script
    and creates the final video with the selected transition.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    # Check if script is ready
    if job.get("status") not in ["script_ready", "completed", "failed"]:
        raise HTTPException(
            status_code=400,
            detail="Script is not ready yet. Wait for script generation to complete."
        )

    # Check if we have image paths
    if not job.get("image_paths"):
        raise HTTPException(
            status_code=400,
            detail="Image paths not found. Please re-upload the PDF."
        )

    # Update job status
    job["status"] = "pending"
    job["progress"] = 0
    job["current_step"] = "영상 재생성 시작..."
    job["video_url"] = None
    job["error"] = None
    job["updated_at"] = datetime.now().isoformat()

    # Start video generation with edited script
    background_tasks.add_task(
        generate_video_from_script_task,
        job_id,
        request.script,
        request.transition
    )

    return JobStatusResponse(**jobs[job_id])


@app.post("/api/upload-pdf", response_model=JobStatusResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Upload PDF appraisal document and generate script (Phase 1).

    The PDF pages will be converted to images, text will be extracted
    using Claude Vision API, and a narration script will be generated.

    After script is ready (status: script_ready), call /api/jobs/{job_id}/regenerate
    with the edited script and transition selection to generate the video.
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다")

    # Create job
    job_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    # Save uploaded PDF
    pdf_dir = settings.temp_dir / "uploads"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{job_id}_{file.filename}"

    with open(pdf_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Initialize job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "current_step": "PDF 업로드 완료, 스크립트 생성 시작...",
        "video_url": None,
        "script_url": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "pdf_path": str(pdf_path),
        "input_mode": "pdf"
    }

    # Start background task for script generation (Phase 1)
    background_tasks.add_task(generate_pdf_script_task, job_id, str(pdf_path))

    return JobStatusResponse(**jobs[job_id])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
