"""
PDF Appraisal Document Scraper
Extracts property information from appraisal PDF documents
"""
import os
import base64
import asyncio
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

from src.models import AuctionProperty, AssetType, RiskLevel
from src.config import settings
from .base import BaseScraper


class PdfAppraisalScraper(BaseScraper):
    """
    Scraper that extracts auction property info from PDF appraisal documents.

    Process:
    1. Convert PDF pages to images
    2. Use Claude Vision API to extract text from each page
    3. Combine extracted text into property info
    """

    def __init__(self):
        self.pdf_path: Optional[Path] = None
        self.page_images: List[Path] = []
        self.extracted_texts: List[str] = []
        self.combined_summary: str = ""

    def set_pdf(self, pdf_path: str):
        """Set the PDF file to process"""
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

    async def convert_pdf_to_images(self, output_dir: Path) -> List[Path]:
        """
        Convert PDF pages to images.

        Args:
            output_dir: Directory to save images

        Returns:
            List of image paths
        """
        if not self.pdf_path:
            raise ValueError("PDF path not set. Call set_pdf() first.")

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from pdf2image import convert_from_path

            # Convert PDF to images (150 DPI for balance of quality and size)
            images = await asyncio.to_thread(
                convert_from_path,
                str(self.pdf_path),
                dpi=150,
                fmt='jpeg'
            )

            image_paths = []
            for i, image in enumerate(images):
                image_path = output_dir / f"page_{i+1:03d}.jpg"
                await asyncio.to_thread(
                    image.save,
                    str(image_path),
                    'JPEG',
                    quality=85
                )
                image_paths.append(image_path)

            self.page_images = image_paths
            print(f"Converted PDF to {len(image_paths)} images")
            return image_paths

        except ImportError:
            raise ImportError(
                "pdf2image is required. Install it with: pip install pdf2image\n"
                "Also ensure poppler is installed on your system."
            )
        except Exception as e:
            raise Exception(f"Failed to convert PDF to images: {str(e)}")

    async def extract_text_from_images(self) -> List[str]:
        """
        Extract text from page images using Claude Vision API.

        Returns:
            List of extracted texts for each page
        """
        if not self.page_images:
            raise ValueError("No images available. Call convert_pdf_to_images() first.")

        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        extracted_texts = []

        for i, image_path in enumerate(self.page_images):
            print(f"Extracting text from page {i+1}/{len(self.page_images)}...")

            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Call Claude Vision API
            try:
                response = await asyncio.to_thread(
                    client.messages.create,
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": """이 감정평가서 페이지의 내용을 읽고 중요한 정보를 요약해주세요.

다음 정보가 있다면 추출해주세요:
- 물건 종류 (아파트, 토지, 상가 등)
- 주소
- 면적 (토지면적, 건물면적)
- 감정가격
- 법원 및 사건번호
- 기타 중요 정보

페이지에 해당 정보가 없으면 있는 내용만 요약해주세요."""
                            }
                        ]
                    }]
                )

                text = response.content[0].text
                extracted_texts.append(text)

            except Exception as e:
                print(f"Warning: Failed to extract text from page {i+1}: {str(e)}")
                extracted_texts.append(f"[페이지 {i+1} - 텍스트 추출 실패]")

        self.extracted_texts = extracted_texts
        return extracted_texts

    async def generate_summary(self) -> str:
        """
        Generate a combined summary from all extracted texts.

        Returns:
            Combined summary text
        """
        if not self.extracted_texts:
            raise ValueError("No extracted texts available. Call extract_text_from_images() first.")

        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        combined_text = "\n\n---\n\n".join([
            f"[페이지 {i+1}]\n{text}"
            for i, text in enumerate(self.extracted_texts)
        ])

        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{
                "role": "user",
                "content": f"""다음은 감정평가서의 각 페이지에서 추출한 내용입니다.
이 내용을 바탕으로 경매 물건 소개 영상의 나레이션 대본을 작성해주세요.

중요: 이 대본은 TTS(음성 합성)로 읽힐 예정이므로 다음 규칙을 반드시 지켜주세요:
- 마크다운 형식(#, ##, **, ``` 등)을 절대 사용하지 마세요
- 섹션 제목도 자연스러운 문장으로 연결하세요
- 기호나 특수문자 없이 순수 텍스트만 사용하세요

대본 구성:
1. 도입부 (물건 소개)
2. 물건 개요 (위치, 종류, 면적)
3. 가격 정보 (감정가, 최저가)
4. 위치 분석 (주변 환경, 교통)
5. 물건 상세 (건물 상태, 특징)
6. 주의사항 (권리관계, 유의점)
7. 마무리

각 섹션은 자연스럽게 연결되도록 작성해주세요.
말하기 편한 구어체로 작성하고, 읽기 쉽게 문단을 나눠주세요.

---
추출된 내용:
{combined_text}"""
            }]
        )

        self.combined_summary = response.content[0].text
        return self.combined_summary

    async def get_property(self, case_number: str) -> Optional[AuctionProperty]:
        """
        Get property information from the PDF.

        For PDF scraper, case_number is used as identifier for the property.
        The actual data comes from the PDF content.
        """
        if not self.combined_summary and self.extracted_texts:
            await self.generate_summary()

        # Create a basic property object with extracted info
        # The real data will come from the extracted text summary
        auction_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        property_data = AuctionProperty(
            case_number=case_number,
            court="PDF 감정평가서",
            asset_type=AssetType.OTHER,
            asset_type_name="감정평가물건",
            address=self._extract_address() or "주소 정보 없음",
            appraisal_value=self._extract_price() or 100000000,
            minimum_bid=int((self._extract_price() or 100000000) * 0.8),
            minimum_bid_percent=0.8,
            auction_date=auction_date,
            auction_round=1,
            risk_level=RiskLevel.CAUTION,
            image_urls=[]  # Will use page images directly
        )

        return property_data

    def _extract_address(self) -> Optional[str]:
        """Try to extract address from combined summary"""
        # Simple extraction - look for common address patterns
        if not self.extracted_texts:
            return None

        for text in self.extracted_texts:
            # Look for Korean address patterns
            import re
            patterns = [
                r'([가-힣]+(?:시|도)\s*[가-힣]+(?:구|군|시)\s*[가-힣0-9\s\-]+)',
                r'주소[:\s]*([^\n]+)',
                r'소재지[:\s]*([^\n]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1).strip()
        return None

    def _extract_price(self) -> Optional[int]:
        """Try to extract price from combined summary"""
        if not self.extracted_texts:
            return None

        import re
        for text in self.extracted_texts:
            # Look for price patterns (Korean won)
            patterns = [
                r'감정가[:\s]*([\d,]+)\s*원',
                r'감정평가액[:\s]*([\d,]+)\s*원',
                r'([\d,]+)\s*원',
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    price_str = match.group(1).replace(',', '')
                    try:
                        return int(price_str)
                    except ValueError:
                        continue
        return None

    async def search_properties(
        self,
        court: Optional[str] = None,
        asset_type: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 10
    ) -> List[AuctionProperty]:
        """
        PDF scraper doesn't support search.
        Returns empty list or single property if PDF is loaded.
        """
        if self.pdf_path:
            prop = await self.get_property(self.pdf_path.stem)
            return [prop] if prop else []
        return []

    async def download_images(
        self,
        property_data: AuctionProperty,
        output_dir: Path
    ) -> List[Path]:
        """
        Return the page images from PDF conversion.
        For PDF scraper, images are the PDF pages themselves.
        """
        if self.page_images:
            return self.page_images

        # If no images yet, try to convert PDF
        if self.pdf_path:
            return await self.convert_pdf_to_images(output_dir)

        return []

    def get_narration_script(self) -> str:
        """Get the generated narration script"""
        return self.combined_summary or ""


async def process_pdf_appraisal(
    pdf_path: str,
    output_dir: Optional[Path] = None
) -> tuple[AuctionProperty, List[Path], str]:
    """
    Convenience function to process a PDF appraisal document.

    Args:
        pdf_path: Path to PDF file
        output_dir: Directory for output images

    Returns:
        Tuple of (property_data, image_paths, narration_script)
    """
    scraper = PdfAppraisalScraper()
    scraper.set_pdf(pdf_path)

    if output_dir is None:
        output_dir = settings.temp_dir / "pdf_images"

    # Convert PDF to images
    image_paths = await scraper.convert_pdf_to_images(output_dir)

    # Extract text from images
    await scraper.extract_text_from_images()

    # Generate summary/script
    script = await scraper.generate_summary()

    # Get property data
    case_number = Path(pdf_path).stem
    property_data = await scraper.get_property(case_number)

    return property_data, image_paths, script
