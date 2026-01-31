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
from src.scraper import create_template_file
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
    ],
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
    status: str  # pending, processing, completed, failed
    progress: int
    current_step: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
