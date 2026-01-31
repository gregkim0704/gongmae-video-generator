"""
Korean script templates for auction videos
Based on standard NPL auction video format
"""
from dataclasses import dataclass
from typing import Dict

from src.models import AuctionProperty, ScriptSection
from src.utils.korean import (
    format_korean_price_simple,
    format_korean_area,
    format_percent,
    format_date_korean
)
from src.config import settings


@dataclass
class ScriptTemplate:
    """Template for generating auction video scripts"""

    channel_name: str = settings.channel_name
    sections: Dict[ScriptSection, str] = None

    def __post_init__(self):
        if self.sections is None:
            self.sections = get_default_sections()

    def fill(self, property_data: AuctionProperty) -> Dict[str, str]:
        """
        Fill template with property data.

        Args:
            property_data: The auction property information

        Returns:
            Dictionary of section name to filled text
        """
        # Prepare template variables
        variables = self._prepare_variables(property_data)

        # Fill each section
        filled_sections = {}
        for section, template in self.sections.items():
            try:
                filled_text = template.format(**variables)
                filled_sections[section.value] = filled_text
            except KeyError as e:
                # Handle missing variables gracefully
                filled_sections[section.value] = template
                print(f"Warning: Missing variable {e} in section {section.value}")

        return filled_sections

    def _prepare_variables(self, prop: AuctionProperty) -> dict:
        """Prepare all template variables from property data"""

        # Format land area
        land_area_str = ""
        if prop.land_area:
            land_area_str = format_korean_area(area_pyeong=prop.land_area)
        elif prop.land_area_sqm:
            land_area_str = format_korean_area(area_sqm=prop.land_area_sqm)

        # Format building area
        building_area_str = ""
        if prop.building_area:
            building_area_str = format_korean_area(area_pyeong=prop.building_area)
        elif prop.building_area_sqm:
            building_area_str = format_korean_area(area_sqm=prop.building_area_sqm)

        # Format lease info
        lease_info = ""
        if prop.has_lease:
            if prop.lease_deposit and prop.monthly_rent:
                lease_info = f"임대보증금 {format_korean_price_simple(prop.lease_deposit)}, 월세 {format_korean_price_simple(prop.monthly_rent)}"
            elif prop.lease_deposit:
                lease_info = f"임대보증금 {format_korean_price_simple(prop.lease_deposit)}"

        # Format rights issues
        rights_info = ""
        if prop.rights_issues:
            rights_list = [f"{ri.type_name}" for ri in prop.rights_issues]
            rights_info = ", ".join(rights_list)

        # Determine re-auction status
        is_reauction = prop.auction_round > 1
        reauction_text = "재매각" if is_reauction else "신건"

        # Bid deposit info
        bid_deposit = int(prop.minimum_bid * prop.bid_deposit_percent)
        bid_deposit_text = format_korean_price_simple(bid_deposit)

        return {
            # Channel/Intro
            "channel_name": self.channel_name,

            # Basic Info
            "court": prop.court,
            "case_number": prop.case_number,
            "address": prop.address,
            "address_detail": prop.address_detail or "",
            "full_address": f"{prop.address} {prop.address_detail or ''}".strip(),
            "asset_type_name": prop.asset_type_name,

            # Area
            "land_area": land_area_str,
            "building_area": building_area_str,
            "floor": prop.floor or "",

            # Price
            "appraisal_value": format_korean_price_simple(prop.appraisal_value),
            "minimum_bid": format_korean_price_simple(prop.minimum_bid),
            "minimum_bid_percent": format_percent(prop.minimum_bid_percent),
            "bid_deposit": bid_deposit_text,
            "bid_deposit_percent": format_percent(prop.bid_deposit_percent),

            # Date
            "auction_date": format_date_korean(prop.auction_date),
            "auction_round": prop.auction_round,
            "reauction_text": reauction_text,

            # Property Details
            "build_year": str(prop.build_year) if prop.build_year else "",
            "structure": prop.structure or "",
            "roof_type": prop.roof_type or "",
            "current_use": prop.current_use or "",

            # Location
            "region": prop.region or "",
            "district": prop.district or "",
            "zoning": prop.zoning or "",
            "terrain": prop.terrain or "",
            "road_access": prop.road_access or "",

            # Legal/Lease
            "has_occupant": "있음" if prop.has_occupant else "없음",
            "has_lease": "있음" if prop.has_lease else "없음",
            "lease_info": lease_info,
            "rights_info": rights_info,
            "risk_level": prop.risk_level.value,
        }

    def get_full_script(self, filled_sections: Dict[str, str]) -> str:
        """Combine all sections into a single script"""
        section_order = [
            ScriptSection.INTRO.value,
            ScriptSection.CASE_OVERVIEW.value,
            ScriptSection.PRICE_INFO.value,
            ScriptSection.LOCATION_ANALYSIS.value,
            ScriptSection.PROPERTY_DETAILS.value,
            ScriptSection.LEGAL_NOTES.value,
            ScriptSection.CLOSING.value,
        ]

        parts = []
        for section in section_order:
            if section in filled_sections:
                parts.append(filled_sections[section])

        return "\n\n".join(parts)

    def estimate_duration(self, text: str, words_per_minute: float = 130) -> float:
        """
        Estimate speech duration for Korean text.
        Korean typically spoken at 130-150 words per minute.

        Args:
            text: The script text
            words_per_minute: Speaking rate

        Returns:
            Estimated duration in seconds
        """
        # For Korean, count characters rather than words
        # Average Korean speaking rate is about 300-400 syllables per minute
        char_count = len(text.replace(" ", "").replace("\n", ""))
        syllables_per_minute = 350  # Conservative estimate
        duration_minutes = char_count / syllables_per_minute
        return duration_minutes * 60


def get_default_sections() -> Dict[ScriptSection, str]:
    """Get default Korean script templates for each section"""
    return {
        ScriptSection.INTRO: (
            "안녕하세요. {channel_name}입니다."
        ),

        ScriptSection.CASE_OVERVIEW: (
            "오늘은 {court} {case_number} "
            "{full_address} "
            "토지면적 {land_area}, 건물면적 {building_area}의 "
            "{asset_type_name}에 대한 경매 사건을 소개하겠습니다."
        ),

        ScriptSection.PRICE_INFO: (
            "본 건의 감정가는 {appraisal_value}이고, "
            "도래하는 {auction_date}자 매각기일에서의 "
            "최저매각금액은 감정가의 {minimum_bid_percent}인 "
            "{minimum_bid}입니다."
        ),

        ScriptSection.LOCATION_ANALYSIS: (
            "본 건은 {region} {district} 인근에 위치하며, "
            "부근은 {zoning} 내 {terrain} 토지로 형성되어 있습니다. "
            "본 건은 {road_access}에 접하여 차량의 진출입이 가능합니다."
        ),

        ScriptSection.PROPERTY_DETAILS: (
            "본 건은 {structure} {roof_type}의 {floor} {asset_type_name}이며, "
            "현재 {current_use}로 사용 중입니다."
        ),

        ScriptSection.LEGAL_NOTES: (
            "본 건은 {reauction_text}으로 입찰보증금은 최저매각금액의 {bid_deposit_percent}인 "
            "{bid_deposit}이며, 점유자 {has_occupant}, 임차인 {has_lease}입니다."
        ),

        ScriptSection.CLOSING: (
            "입찰 이전에 현장을 방문하시어 경락 후 활용방안 등 "
            "제반사항을 확인 바라오며, 검토 중 궁금하신 사항은 "
            "{channel_name}에 문의 바랍니다. "
            "위 매각기일에 경락, 유찰 또는 변경될 수 있음도 참고 바랍니다. "
            "감사합니다."
        ),
    }


def get_default_template() -> ScriptTemplate:
    """Get the default script template"""
    return ScriptTemplate()
