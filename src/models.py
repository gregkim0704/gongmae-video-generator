"""
Data models for Real Estate Auction Video Generator
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel


class AssetType(str, Enum):
    """Property asset types"""
    APT = "APT"
    LAND = "LAND"
    COMMERCIAL = "COMMERCIAL"
    HOUSE = "HOUSE"
    OFFICE = "OFFICE"
    FACTORY = "FACTORY"
    OTHER = "OTHER"


class RiskLevel(str, Enum):
    """Auction risk assessment levels"""
    SAFE = "safe"
    CAUTION = "caution"
    DANGER = "danger"


class ScriptSection(str, Enum):
    """Script sections for auction video"""
    INTRO = "intro"
    CASE_OVERVIEW = "case_overview"
    PRICE_INFO = "price_info"
    LOCATION_ANALYSIS = "location_analysis"
    PROPERTY_DETAILS = "property_details"
    LEGAL_NOTES = "legal_notes"
    CLOSING = "closing"


class AspectRatio(str, Enum):
    """Video aspect ratios"""
    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"
    SQUARE = "1:1"


class JobStatus(str, Enum):
    """Video generation job status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RightIssue(BaseModel):
    """Rights issue affecting auction property"""
    type: str  # lease, mortgage, lien, etc.
    type_name: str  # Korean name
    description: str
    risk_level: RiskLevel
    survives_auction: bool
    amount: Optional[int] = None
    priority: int = 0
    registration_date: Optional[str] = None


class AuctionProperty(BaseModel):
    """Complete auction property information"""

    # Basic Info
    case_number: str  # e.g., "2024타경12345"
    court: str  # e.g., "수원지방법원"
    asset_type: AssetType
    asset_type_name: str  # e.g., "단독주택"

    # Location
    address: str
    address_detail: Optional[str] = None
    region: Optional[str] = None
    district: Optional[str] = None

    # Property Details
    land_area: Optional[float] = None  # in pyeong (평)
    building_area: Optional[float] = None  # in pyeong
    land_area_sqm: Optional[float] = None  # in square meters
    building_area_sqm: Optional[float] = None  # in square meters
    floor: Optional[str] = None
    build_year: Optional[int] = None
    structure: Optional[str] = None  # e.g., "철근콘크리트조"
    roof_type: Optional[str] = None  # e.g., "슬라브지붕"
    current_use: Optional[str] = None

    # Auction Info
    appraisal_value: int  # 감정가 (won)
    minimum_bid: int  # 최저매각금액
    minimum_bid_percent: float  # e.g., 0.64 for 64%
    auction_date: str  # YYYY-MM-DD
    auction_round: int = 1
    bid_deposit_percent: float = 0.1  # 입찰보증금 비율

    # Analysis
    risk_level: RiskLevel = RiskLevel.CAUTION
    has_occupant: bool = False
    has_lease: bool = False
    rights_issues: List[RightIssue] = []

    # Lease Info (if applicable)
    lease_deposit: Optional[int] = None  # 보증금
    monthly_rent: Optional[int] = None  # 월세

    # Zoning
    zoning: Optional[str] = None  # e.g., "제1종일반주거지역"
    terrain: Optional[str] = None  # e.g., "평지"
    road_access: Optional[str] = None  # e.g., "노폭 6m 도로"

    # Images
    image_urls: List[str] = []
    map_image_url: Optional[str] = None


class AuctionScript(BaseModel):
    """Generated script for auction video"""
    property: AuctionProperty
    sections: Dict[str, str]  # ScriptSection -> text
    full_script: str
    estimated_duration: float  # seconds
    word_count: int = 0


@dataclass
class Scene:
    """A single scene in the video"""
    scene_id: int
    section: ScriptSection
    text: str
    duration: float
    image_path: Optional[str] = None


@dataclass
class VideoJob:
    """Video generation job tracking"""
    job_id: str
    case_number: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0  # 0-100
    current_step: str = ""
    property_data: Optional[AuctionProperty] = None
    script: Optional[AuctionScript] = None
    scenes: List[Scene] = field(default_factory=list)
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    error: Optional[str] = None


class SubtitleSegment(BaseModel):
    """A subtitle segment with timing"""
    start_time: float  # seconds
    end_time: float  # seconds
    text: str
