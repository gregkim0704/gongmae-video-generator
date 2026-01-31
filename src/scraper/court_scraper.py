"""
대법원 경매정보 크롤러 (courtauction.go.kr)
Selenium 기반으로 실제 경매 물건 정보를 수집
"""
import asyncio
import re
import time
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import httpx

from src.models import AuctionProperty, RightIssue, AssetType, RiskLevel
from src.config import settings
from .base import BaseScraper


class CourtAuctionScraper(BaseScraper):
    """
    대법원 경매정보 사이트 크롤러
    https://www.courtauction.go.kr
    """

    BASE_URL = "https://www.courtauction.go.kr"
    SEARCH_URL = f"{BASE_URL}/pgj/index.on"

    def __init__(self, headless: bool = True):
        """
        Args:
            headless: 브라우저를 숨김 모드로 실행할지 여부
        """
        self.headless = headless
        self.driver = None

    def _setup_driver(self):
        """Selenium WebDriver 설정"""
        if self.driver is not None:
            return

        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--lang=ko_KR")

        # 자동화 탐지 방지
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def _close_driver(self):
        """WebDriver 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    async def get_property(self, case_number: str) -> Optional[AuctionProperty]:
        """
        사건번호로 경매 물건 정보 조회

        Args:
            case_number: 사건번호 (예: "2024타경12345" 또는 "2024 타경 12345")

        Returns:
            AuctionProperty 또는 None
        """
        # 사건번호 파싱
        parsed = self._parse_case_number(case_number)
        if not parsed:
            print(f"잘못된 사건번호 형식: {case_number}")
            return None

        year, case_type, number = parsed
        print(f"검색 중: {year}년 {case_type} {number}")

        try:
            self._setup_driver()

            # 검색 페이지로 이동
            self.driver.get(self.SEARCH_URL)
            await asyncio.sleep(2)

            # iframe 전환 (대법원 사이트는 iframe 구조)
            try:
                self.driver.switch_to.frame("indexFrame")
            except NoSuchElementException:
                # iframe이 없을 수 있음
                pass

            # 물건 상세검색 페이지로 이동
            wait = WebDriverWait(self.driver, 10)

            # 상세검색 버튼 클릭
            try:
                search_btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(text(), '물건상세검색')]")
                ))
                search_btn.click()
                await asyncio.sleep(1)
            except TimeoutException:
                print("검색 페이지 로딩 실패")
                return None

            # 사건번호 입력
            await self._input_case_number(year, case_type, number)

            # 검색 실행
            search_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@onclick, 'search') or contains(text(), '검색')]")
            ))
            search_button.click()
            await asyncio.sleep(2)

            # 결과 파싱
            property_data = await self._parse_search_results()

            return property_data

        except Exception as e:
            print(f"크롤링 오류: {e}")
            import traceback
            traceback.print_exc()
            return None

        finally:
            self._close_driver()

    def _parse_case_number(self, case_number: str) -> Optional[tuple]:
        """
        사건번호 파싱

        Args:
            case_number: "2024타경12345" 또는 "2024 타경 12345"

        Returns:
            (년도, 사건유형, 번호) 튜플 또는 None
        """
        # 공백 제거
        case_number = case_number.replace(" ", "")

        # 패턴 매칭: 년도(4자리) + 사건유형(타경/타채 등) + 번호
        pattern = r"(\d{4})(타경|타채|카경|카합|가경|가합)(\d+)"
        match = re.match(pattern, case_number)

        if match:
            return match.group(1), match.group(2), match.group(3)

        return None

    async def _input_case_number(self, year: str, case_type: str, number: str):
        """사건번호 입력 필드에 값 입력"""
        wait = WebDriverWait(self.driver, 10)

        try:
            # 사건년도 입력
            year_input = wait.until(EC.presence_of_element_located(
                (By.ID, "idSaYear")
            ))
            year_input.clear()
            year_input.send_keys(year)

            # 사건구분 선택 (타경, 타채 등)
            case_type_select = Select(self.driver.find_element(By.ID, "idSaGubun"))
            case_type_select.select_by_visible_text(case_type)

            # 사건번호 입력
            number_input = self.driver.find_element(By.ID, "idSaSeq")
            number_input.clear()
            number_input.send_keys(number)

        except NoSuchElementException as e:
            print(f"입력 필드를 찾을 수 없음: {e}")
            raise

    async def _parse_search_results(self) -> Optional[AuctionProperty]:
        """검색 결과 페이지에서 물건 정보 추출"""
        await asyncio.sleep(1)

        # 검색 결과 테이블에서 첫 번째 물건 클릭
        try:
            wait = WebDriverWait(self.driver, 10)
            first_result = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//table[@class='Ltbl_list']//tr[2]/td[2]/a")
            ))
            first_result.click()
            await asyncio.sleep(2)
        except TimeoutException:
            print("검색 결과가 없습니다")
            return None

        # 상세 페이지 파싱
        return await self._parse_detail_page()

    async def _parse_detail_page(self) -> Optional[AuctionProperty]:
        """물건 상세 페이지 파싱"""
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        try:
            # 기본 정보 추출
            info_table = soup.find('table', class_='Ltbl_dt')
            if not info_table:
                return None

            rows = info_table.find_all('tr')
            data = {}

            for row in rows:
                ths = row.find_all('th')
                tds = row.find_all('td')
                for th, td in zip(ths, tds):
                    key = th.get_text(strip=True)
                    value = td.get_text(strip=True)
                    data[key] = value

            # 데이터 추출
            case_number = data.get('사건번호', '')
            court = data.get('관할법원', '')
            address = data.get('소재지', '')

            # 감정가 파싱
            appraisal_str = data.get('감정가', '0')
            appraisal_value = self._parse_price(appraisal_str)

            # 최저가 파싱
            min_bid_str = data.get('최저매각가격', data.get('최저가', '0'))
            minimum_bid = self._parse_price(min_bid_str)

            # 매각기일
            auction_date_str = data.get('매각기일', '')
            auction_date = self._parse_date(auction_date_str)

            # 물건종류
            asset_type_str = data.get('물건종류', data.get('용도', '기타'))
            asset_type = self._map_asset_type(asset_type_str)

            # 면적 파싱
            land_area = self._parse_area(data.get('토지면적', data.get('대지면적', '')))
            building_area = self._parse_area(data.get('건물면적', data.get('연면적', '')))

            # 최저가율 계산
            min_bid_percent = minimum_bid / appraisal_value if appraisal_value > 0 else 0

            # 이미지 URL 추출
            image_urls = self._extract_image_urls(soup)

            return AuctionProperty(
                case_number=case_number,
                court=court,
                asset_type=asset_type,
                asset_type_name=asset_type_str,
                address=address,
                land_area=land_area,
                building_area=building_area,
                appraisal_value=appraisal_value,
                minimum_bid=minimum_bid,
                minimum_bid_percent=min_bid_percent,
                auction_date=auction_date,
                auction_round=1,
                risk_level=RiskLevel.CAUTION,
                image_urls=image_urls
            )

        except Exception as e:
            print(f"상세 페이지 파싱 오류: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_price(self, price_str: str) -> int:
        """가격 문자열을 정수로 변환 (예: "850,000,000원" -> 850000000)"""
        if not price_str:
            return 0
        # 숫자만 추출
        numbers = re.findall(r'\d+', price_str.replace(',', ''))
        if numbers:
            return int(''.join(numbers))
        return 0

    def _parse_area(self, area_str: str) -> Optional[float]:
        """면적 문자열을 평으로 변환"""
        if not area_str:
            return None

        # m² 단위인 경우
        sqm_match = re.search(r'([\d,.]+)\s*(?:m²|㎡|제곱미터)', area_str)
        if sqm_match:
            sqm = float(sqm_match.group(1).replace(',', ''))
            return sqm / 3.3058  # 평으로 변환

        # 평 단위인 경우
        pyeong_match = re.search(r'([\d,.]+)\s*평', area_str)
        if pyeong_match:
            return float(pyeong_match.group(1).replace(',', ''))

        return None

    def _parse_date(self, date_str: str) -> str:
        """날짜 문자열을 YYYY-MM-DD 형식으로 변환"""
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")

        # 다양한 날짜 형식 처리
        patterns = [
            r'(\d{4})[.-/](\d{1,2})[.-/](\d{1,2})',  # 2024-03-15, 2024.03.15
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',  # 2024년 3월 15일
        ]

        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                year, month, day = match.groups()
                return f"{year}-{int(month):02d}-{int(day):02d}"

        return datetime.now().strftime("%Y-%m-%d")

    def _map_asset_type(self, type_str: str) -> AssetType:
        """물건종류 문자열을 AssetType으로 매핑"""
        type_map = {
            '아파트': AssetType.APT,
            '오피스텔': AssetType.APT,
            '주택': AssetType.HOUSE,
            '단독주택': AssetType.HOUSE,
            '다가구': AssetType.HOUSE,
            '다세대': AssetType.HOUSE,
            '빌라': AssetType.HOUSE,
            '토지': AssetType.LAND,
            '대지': AssetType.LAND,
            '임야': AssetType.LAND,
            '상가': AssetType.COMMERCIAL,
            '근린생활': AssetType.COMMERCIAL,
            '사무실': AssetType.OFFICE,
            '오피스': AssetType.OFFICE,
            '공장': AssetType.FACTORY,
            '창고': AssetType.FACTORY,
        }

        for key, value in type_map.items():
            if key in type_str:
                return value

        return AssetType.OTHER

    def _extract_image_urls(self, soup: BeautifulSoup) -> List[str]:
        """페이지에서 물건 이미지 URL 추출"""
        image_urls = []

        # 이미지 태그에서 URL 추출
        img_tags = soup.find_all('img', src=True)
        for img in img_tags:
            src = img['src']
            # 물건 이미지로 보이는 URL만 필터링
            if 'photo' in src.lower() or 'image' in src.lower() or 'picture' in src.lower():
                if src.startswith('/'):
                    src = self.BASE_URL + src
                image_urls.append(src)

        return image_urls[:5]  # 최대 5개

    async def search_properties(
        self,
        court: Optional[str] = None,
        asset_type: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 10
    ) -> List[AuctionProperty]:
        """
        조건으로 경매 물건 검색 (미구현)
        """
        print("search_properties는 아직 구현되지 않았습니다. get_property를 사용해주세요.")
        return []

    async def download_images(
        self,
        property_data: AuctionProperty,
        output_dir: Path
    ) -> List[Path]:
        """물건 이미지 다운로드"""
        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []

        async with httpx.AsyncClient() as client:
            for i, url in enumerate(property_data.image_urls):
                try:
                    response = await client.get(url, timeout=30)
                    if response.status_code == 200:
                        # 확장자 추출
                        ext = url.split('.')[-1].lower()
                        if ext not in ['jpg', 'jpeg', 'png', 'gif']:
                            ext = 'jpg'

                        filename = f"{property_data.case_number}_image_{i}.{ext}"
                        filepath = output_dir / filename

                        with open(filepath, 'wb') as f:
                            f.write(response.content)

                        downloaded.append(filepath)
                        print(f"이미지 다운로드 완료: {filename}")

                except Exception as e:
                    print(f"이미지 다운로드 실패 ({url}): {e}")

        # 이미지가 없으면 플레이스홀더 생성
        if not downloaded:
            from .mock_scraper import MockScraper
            mock = MockScraper()
            placeholder = output_dir / f"{property_data.case_number}_placeholder.png"
            mock._generate_placeholder_image(
                placeholder,
                property_data.address,
                property_data.asset_type_name
            )
            downloaded.append(placeholder)

        return downloaded
