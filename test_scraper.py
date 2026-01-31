#!/usr/bin/env python3
"""
대법원 경매 크롤러 테스트 스크립트
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.scraper import CourtAuctionScraper


async def test_scraper():
    """크롤러 테스트"""
    print("=" * 60)
    print("대법원 경매정보 크롤러 테스트")
    print("=" * 60)

    # headless=False로 설정하면 브라우저 창을 볼 수 있음
    scraper = CourtAuctionScraper(headless=False)

    # 테스트할 사건번호 (실제 존재하는 사건번호로 변경 필요)
    # 대법원 경매사이트에서 현재 진행 중인 사건번호를 찾아서 테스트
    test_case = "2024타경12345"

    print(f"\n검색할 사건번호: {test_case}")
    print("-" * 60)

    try:
        property_data = await scraper.get_property(test_case)

        if property_data:
            print("\n[성공] 물건 정보를 가져왔습니다!")
            print("-" * 60)
            print(f"사건번호: {property_data.case_number}")
            print(f"법원: {property_data.court}")
            print(f"주소: {property_data.address}")
            print(f"물건종류: {property_data.asset_type_name}")
            print(f"감정가: {property_data.appraisal_value:,}원")
            print(f"최저가: {property_data.minimum_bid:,}원")
            print(f"최저가율: {property_data.minimum_bid_percent:.1%}")
            print(f"매각기일: {property_data.auction_date}")
            print(f"토지면적: {property_data.land_area}평" if property_data.land_area else "")
            print(f"건물면적: {property_data.building_area}평" if property_data.building_area else "")
            print(f"이미지 URL: {len(property_data.image_urls)}개")
        else:
            print("\n[실패] 물건 정보를 찾을 수 없습니다.")
            print("- 사건번호가 올바른지 확인하세요")
            print("- 현재 진행 중인 경매 사건인지 확인하세요")

    except Exception as e:
        print(f"\n[오류] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_scraper())
