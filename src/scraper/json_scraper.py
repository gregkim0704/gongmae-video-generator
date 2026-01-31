"""
JSON 파일 기반 스크래퍼
사용자가 직접 작성한 JSON 파일에서 경매 물건 정보를 읽어옴
"""
import json
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from src.models import AuctionProperty, RightIssue, AssetType, RiskLevel
from src.config import settings
from .base import BaseScraper


class JsonFileScraper(BaseScraper):
    """
    JSON 파일에서 경매 물건 정보를 읽어오는 스크래퍼

    사용자가 대법원 경매 사이트에서 정보를 확인하고
    JSON 파일로 작성하면 이를 읽어서 영상 생성에 사용
    """

    def __init__(self, json_path: Optional[Path] = None):
        """
        Args:
            json_path: JSON 파일 경로 (없으면 사건번호로 자동 탐색)
        """
        self.json_path = json_path
        self.input_dir = settings.data_dir / "input"
        self.input_dir.mkdir(parents=True, exist_ok=True)

    async def get_property(self, case_number: str) -> Optional[AuctionProperty]:
        """
        사건번호로 JSON 파일 찾아서 물건 정보 반환

        Args:
            case_number: 사건번호 (예: "2024타경12345")
                        또는 JSON 파일 경로

        Returns:
            AuctionProperty 또는 None
        """
        # case_number가 파일 경로인 경우
        if case_number.endswith('.json'):
            json_file = Path(case_number)
        else:
            # 사건번호로 파일 찾기
            safe_case = case_number.replace("/", "_").replace("\\", "_").replace(" ", "")
            json_file = self.input_dir / f"{safe_case}.json"

        if not json_file.exists():
            print(f"JSON 파일을 찾을 수 없습니다: {json_file}")
            print(f"\n다음 경로에 JSON 파일을 생성해주세요:")
            print(f"  {json_file}")
            print(f"\n템플릿 파일 참조: {settings.data_dir / 'templates' / 'property_template.json'}")
            return None

        return self._load_from_json(json_file)

    def _load_from_json(self, json_path: Path) -> Optional[AuctionProperty]:
        """JSON 파일에서 AuctionProperty 로드"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 권리관계 파싱
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

        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            return None
        except Exception as e:
            print(f"파일 로드 오류: {e}")
            return None

    async def search_properties(
        self,
        court: Optional[str] = None,
        asset_type: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 10
    ) -> List[AuctionProperty]:
        """input 디렉토리의 모든 JSON 파일 목록 반환"""
        properties = []

        for json_file in self.input_dir.glob("*.json"):
            prop = self._load_from_json(json_file)
            if prop:
                # 필터 적용
                if court and prop.court != court:
                    continue
                if region and prop.region != region:
                    continue
                properties.append(prop)

            if len(properties) >= limit:
                break

        return properties

    async def download_images(
        self,
        property_data: AuctionProperty,
        output_dir: Path
    ) -> List[Path]:
        """이미지 다운로드 또는 플레이스홀더 생성"""
        import httpx

        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []

        # 로컬 이미지 파일 확인 (input/images 디렉토리)
        images_dir = self.input_dir / "images"
        safe_case = property_data.case_number.replace("/", "_").replace("\\", "_")

        for i, url in enumerate(property_data.image_urls):
            # 로컬 파일인 경우
            if not url.startswith("http"):
                local_path = images_dir / url
                if local_path.exists():
                    import shutil
                    dest = output_dir / f"{safe_case}_image_{i}{local_path.suffix}"
                    shutil.copy2(local_path, dest)
                    downloaded.append(dest)
                    continue

            # URL인 경우 다운로드 시도
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=30)
                    if response.status_code == 200:
                        ext = url.split('.')[-1].lower()
                        if ext not in ['jpg', 'jpeg', 'png', 'gif']:
                            ext = 'jpg'
                        filepath = output_dir / f"{safe_case}_image_{i}.{ext}"
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        downloaded.append(filepath)
            except Exception as e:
                print(f"이미지 다운로드 실패: {e}")

        # 이미지가 없으면 플레이스홀더 생성
        if not downloaded:
            placeholder = output_dir / f"{safe_case}_placeholder.png"
            self._generate_placeholder_image(
                placeholder,
                property_data.address,
                property_data.asset_type_name
            )
            downloaded.append(placeholder)

        return downloaded

    def _generate_placeholder_image(
        self,
        output_path: Path,
        address: str,
        label: str,
        color: tuple = (100, 120, 140),
        size: tuple = (1920, 1080)
    ):
        """플레이스홀더 이미지 생성"""
        img = Image.new("RGB", size, color)
        draw = ImageDraw.Draw(img)

        try:
            font_large = ImageFont.truetype("malgun.ttf", 72)
            font_small = ImageFont.truetype("malgun.ttf", 36)
        except OSError:
            try:
                font_large = ImageFont.truetype("arial.ttf", 72)
                font_small = ImageFont.truetype("arial.ttf", 36)
            except OSError:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

        # 라벨
        label_bbox = draw.textbbox((0, 0), label, font=font_large)
        label_width = label_bbox[2] - label_bbox[0]
        label_x = (size[0] - label_width) // 2
        label_y = size[1] // 2 - 50
        draw.text((label_x, label_y), label, fill="white", font=font_large)

        # 주소
        display_address = address[:50] + "..." if len(address) > 50 else address
        addr_bbox = draw.textbbox((0, 0), display_address, font=font_small)
        addr_width = addr_bbox[2] - addr_bbox[0]
        addr_x = (size[0] - addr_width) // 2
        addr_y = label_y + 100
        draw.text((addr_x, addr_y), display_address, fill="white", font=font_small)

        # 테두리
        draw.rectangle([(20, 20), (size[0]-20, size[1]-20)], outline="white", width=3)

        img.save(output_path)


def create_template_file():
    """JSON 템플릿 파일 생성"""
    template = {
        "_설명": "대법원 경매정보를 참고하여 아래 항목을 채워주세요",
        "_참고사이트": "https://www.courtauction.go.kr",

        "case_number": "2024타경12345",
        "court": "수원지방법원",
        "asset_type": "HOUSE",
        "asset_type_name": "단독주택",

        "address": "경기도 수원시 영통구 매탄동 123-45",
        "address_detail": "매탄마을 1단지",
        "region": "경기",
        "district": "수원시 영통구",

        "land_area": 85.5,
        "building_area": 132.0,
        "land_area_sqm": 282.6,
        "building_area_sqm": 436.4,
        "floor": "지상2층",
        "build_year": 2005,
        "structure": "철근콘크리트조",
        "roof_type": "슬라브지붕",
        "current_use": "주거용",

        "appraisal_value": 850000000,
        "minimum_bid": 544000000,
        "minimum_bid_percent": 0.64,
        "auction_date": "2024-03-15",
        "auction_round": 2,
        "bid_deposit_percent": 0.1,

        "risk_level": "caution",
        "has_occupant": True,
        "has_lease": True,
        "lease_deposit": 200000000,
        "monthly_rent": 0,

        "zoning": "제1종일반주거지역",
        "terrain": "평지",
        "road_access": "노폭 약 6m 내외 아스팔트도로",

        "rights_issues": [
            {
                "type": "lease",
                "type_name": "임차권",
                "description": "보증금 2억원의 주택임대차",
                "risk_level": "caution",
                "survives_auction": False,
                "amount": 200000000,
                "priority": 2
            }
        ],

        "image_urls": [],
        "map_image_url": None
    }

    template_dir = settings.data_dir / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    template_path = template_dir / "property_template.json"

    with open(template_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    print(f"템플릿 파일 생성됨: {template_path}")
    return template_path
