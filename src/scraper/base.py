"""
Base scraper interface for auction data collection
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path

from src.models import AuctionProperty


class BaseScraper(ABC):
    """Abstract base class for auction data scrapers"""

    @abstractmethod
    async def get_property(self, case_number: str) -> Optional[AuctionProperty]:
        """
        Fetch property information by case number.

        Args:
            case_number: The auction case number (e.g., "2024타경12345")

        Returns:
            AuctionProperty if found, None otherwise
        """
        pass

    @abstractmethod
    async def search_properties(
        self,
        court: Optional[str] = None,
        asset_type: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 10
    ) -> List[AuctionProperty]:
        """
        Search for auction properties with filters.

        Args:
            court: Filter by court name
            asset_type: Filter by asset type
            region: Filter by region
            limit: Maximum number of results

        Returns:
            List of matching AuctionProperty objects
        """
        pass

    @abstractmethod
    async def download_images(
        self,
        property_data: AuctionProperty,
        output_dir: Path
    ) -> List[Path]:
        """
        Download property images to local directory.

        Args:
            property_data: The auction property with image URLs
            output_dir: Directory to save images

        Returns:
            List of paths to downloaded images
        """
        pass
