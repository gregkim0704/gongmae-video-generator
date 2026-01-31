"""
Mock scraper that returns predefined test data
Used for development and testing without API costs
"""
import json
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from src.models import AuctionProperty, RightIssue, AssetType, RiskLevel
from src.config import settings
from .base import BaseScraper


class MockScraper(BaseScraper):
    """Mock scraper using local JSON data and generated placeholder images"""

    def __init__(self):
        self.data_file = settings.mock_dir / "sample_properties.json"
        self._properties: List[dict] = []
        self._load_data()

    def _load_data(self):
        """Load mock data from JSON file"""
        if self.data_file.exists():
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._properties = data.get("properties", [])

    async def get_property(self, case_number: str) -> Optional[AuctionProperty]:
        """Get property by case number from mock data"""
        for prop_data in self._properties:
            if prop_data.get("case_number") == case_number:
                return self._parse_property(prop_data)
        return None

    async def search_properties(
        self,
        court: Optional[str] = None,
        asset_type: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 10
    ) -> List[AuctionProperty]:
        """Search mock properties with filters"""
        results = []

        for prop_data in self._properties:
            # Apply filters
            if court and prop_data.get("court") != court:
                continue
            if asset_type and prop_data.get("asset_type") != asset_type:
                continue
            if region and prop_data.get("region") != region:
                continue

            results.append(self._parse_property(prop_data))

            if len(results) >= limit:
                break

        return results

    async def download_images(
        self,
        property_data: AuctionProperty,
        output_dir: Path
    ) -> List[Path]:
        """Generate placeholder images for mock data"""
        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []

        # Generate placeholder images for each URL
        for i, url in enumerate(property_data.image_urls):
            output_path = output_dir / f"{property_data.case_number}_image_{i}.png"
            self._generate_placeholder_image(
                output_path,
                property_data.address,
                f"Property Image {i + 1}"
            )
            downloaded.append(output_path)

        # Generate map placeholder if needed
        if property_data.map_image_url:
            map_path = output_dir / f"{property_data.case_number}_map.png"
            self._generate_placeholder_image(
                map_path,
                property_data.address,
                "Location Map",
                color=(200, 220, 200)  # Greenish for map
            )
            downloaded.append(map_path)

        # Ensure at least one image exists
        if not downloaded:
            default_path = output_dir / f"{property_data.case_number}_default.png"
            self._generate_placeholder_image(
                default_path,
                property_data.address,
                property_data.asset_type_name
            )
            downloaded.append(default_path)

        return downloaded

    def _generate_placeholder_image(
        self,
        output_path: Path,
        address: str,
        label: str,
        color: tuple = (100, 120, 140),
        size: tuple = (1920, 1080)
    ):
        """Generate a placeholder image with text"""
        # Create image with solid color
        img = Image.new("RGB", size, color)
        draw = ImageDraw.Draw(img)

        # Try to use a basic font, fall back to default
        try:
            # Try system fonts
            font_large = ImageFont.truetype("arial.ttf", 72)
            font_small = ImageFont.truetype("arial.ttf", 36)
        except OSError:
            try:
                font_large = ImageFont.truetype("malgun.ttf", 72)
                font_small = ImageFont.truetype("malgun.ttf", 36)
            except OSError:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

        # Draw label at center
        label_bbox = draw.textbbox((0, 0), label, font=font_large)
        label_width = label_bbox[2] - label_bbox[0]
        label_height = label_bbox[3] - label_bbox[1]
        label_x = (size[0] - label_width) // 2
        label_y = (size[1] - label_height) // 2 - 50

        draw.text((label_x, label_y), label, fill="white", font=font_large)

        # Draw address below
        # Truncate if too long
        display_address = address[:50] + "..." if len(address) > 50 else address
        addr_bbox = draw.textbbox((0, 0), display_address, font=font_small)
        addr_width = addr_bbox[2] - addr_bbox[0]
        addr_x = (size[0] - addr_width) // 2
        addr_y = label_y + label_height + 30

        draw.text((addr_x, addr_y), display_address, fill="white", font=font_small)

        # Draw border
        draw.rectangle(
            [(20, 20), (size[0] - 20, size[1] - 20)],
            outline="white",
            width=3
        )

        # Save image
        img.save(output_path)

    def _parse_property(self, data: dict) -> AuctionProperty:
        """Parse JSON data into AuctionProperty model"""
        # Parse rights issues
        rights_issues = []
        for ri in data.get("rights_issues", []):
            rights_issues.append(RightIssue(
                type=ri.get("type", "other"),
                type_name=ri.get("type_name", "기타"),
                description=ri.get("description", ""),
                risk_level=RiskLevel(ri.get("risk_level", "caution")),
                survives_auction=ri.get("survives_auction", False),
                amount=ri.get("amount"),
                priority=ri.get("priority", 0),
                registration_date=ri.get("registration_date")
            ))

        return AuctionProperty(
            case_number=data.get("case_number", ""),
            court=data.get("court", ""),
            asset_type=AssetType(data.get("asset_type", "OTHER")),
            asset_type_name=data.get("asset_type_name", "기타"),
            address=data.get("address", ""),
            address_detail=data.get("address_detail"),
            region=data.get("region"),
            district=data.get("district"),
            land_area=data.get("land_area"),
            building_area=data.get("building_area"),
            land_area_sqm=data.get("land_area_sqm"),
            building_area_sqm=data.get("building_area_sqm"),
            floor=data.get("floor"),
            build_year=data.get("build_year"),
            structure=data.get("structure"),
            roof_type=data.get("roof_type"),
            current_use=data.get("current_use"),
            appraisal_value=data.get("appraisal_value", 0),
            minimum_bid=data.get("minimum_bid", 0),
            minimum_bid_percent=data.get("minimum_bid_percent", 0.0),
            auction_date=data.get("auction_date", ""),
            auction_round=data.get("auction_round", 1),
            bid_deposit_percent=data.get("bid_deposit_percent", 0.1),
            risk_level=RiskLevel(data.get("risk_level", "caution")),
            has_occupant=data.get("has_occupant", False),
            has_lease=data.get("has_lease", False),
            lease_deposit=data.get("lease_deposit"),
            monthly_rent=data.get("monthly_rent"),
            zoning=data.get("zoning"),
            terrain=data.get("terrain"),
            road_access=data.get("road_access"),
            rights_issues=rights_issues,
            image_urls=data.get("image_urls", []),
            map_image_url=data.get("map_image_url")
        )
