"""
Script writer using LLM for enhanced script generation
"""
import asyncio
from typing import Optional, Dict

from src.models import AuctionProperty, AuctionScript, ScriptSection
from src.config import settings
from .template import ScriptTemplate, get_default_template


class ScriptWriter:
    """
    Generates auction video scripts using templates and optional LLM enhancement.

    In mock mode, uses pure template filling without API calls.
    With API enabled, can enhance scripts with more natural language.
    """

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.template = get_default_template()
        self._client = None

    def _init_client(self):
        """Initialize Anthropic client if needed"""
        if self._client is None and not self.mock_mode:
            try:
                import anthropic
                self._client = anthropic.Anthropic(
                    api_key=settings.anthropic_api_key
                )
            except ImportError:
                print("Warning: anthropic package not installed, using template mode")
                self.mock_mode = True

    async def generate_script(
        self,
        property_data: AuctionProperty,
        enhance_with_llm: bool = False
    ) -> AuctionScript:
        """
        Generate a complete script for an auction property video.

        Args:
            property_data: The auction property information
            enhance_with_llm: Whether to enhance the script using LLM (requires API key)

        Returns:
            AuctionScript with all sections filled
        """
        # Start with template-filled sections
        filled_sections = self.template.fill(property_data)

        # Optionally enhance with LLM
        if enhance_with_llm and not self.mock_mode:
            filled_sections = await self._enhance_with_llm(property_data, filled_sections)

        # Combine into full script
        full_script = self.template.get_full_script(filled_sections)

        # Estimate duration
        duration = self.template.estimate_duration(full_script)

        # Count words (for Korean, count characters)
        word_count = len(full_script.replace(" ", "").replace("\n", ""))

        return AuctionScript(
            property=property_data,
            sections=filled_sections,
            full_script=full_script,
            estimated_duration=duration,
            word_count=word_count
        )

    async def _enhance_with_llm(
        self,
        property_data: AuctionProperty,
        base_sections: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Enhance script sections using Claude API for more natural language.
        """
        self._init_client()

        if self._client is None:
            return base_sections

        # Prepare the prompt
        system_prompt = """당신은 전문적인 부동산 경매 영상 스크립트 작성자입니다.
주어진 경매 물건 정보를 바탕으로 자연스럽고 전문적인 한국어 나레이션 스크립트를 작성합니다.
다음 규칙을 따르세요:
1. 전문적이고 신뢰감 있는 톤을 유지합니다
2. 숫자는 한국어 단위로 자연스럽게 읽습니다 (예: 8억 5천만원)
3. 과장이나 주관적 평가는 피합니다
4. 법적 면책 조항을 포함합니다"""

        user_prompt = f"""다음 경매 물건 정보를 바탕으로 더 자연스러운 스크립트로 다듬어주세요.
각 섹션별로 내용을 유지하면서 더 자연스러운 문장으로 개선해주세요.

물건 정보:
- 법원: {property_data.court}
- 사건번호: {property_data.case_number}
- 주소: {property_data.address}
- 물건종류: {property_data.asset_type_name}
- 감정가: {property_data.appraisal_value}원
- 최저가: {property_data.minimum_bid}원
- 매각기일: {property_data.auction_date}

기본 스크립트:
{base_sections}

각 섹션을 더 자연스럽게 다듬어서 JSON 형식으로 반환해주세요."""

        try:
            # Run in thread executor to not block
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=2000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
            )

            # Parse response (simplified - would need proper JSON parsing)
            enhanced_text = response.content[0].text

            # For now, just return the base sections if parsing fails
            # In production, would parse the JSON response
            return base_sections

        except Exception as e:
            print(f"LLM enhancement failed: {e}")
            return base_sections

    def get_section_durations(
        self,
        script: AuctionScript
    ) -> Dict[str, float]:
        """
        Calculate duration for each section based on text length.

        Args:
            script: The generated script

        Returns:
            Dictionary of section name to duration in seconds
        """
        total_chars = sum(
            len(text.replace(" ", ""))
            for text in script.sections.values()
        )

        if total_chars == 0:
            return {}

        durations = {}
        for section, text in script.sections.items():
            section_chars = len(text.replace(" ", ""))
            proportion = section_chars / total_chars
            durations[section] = proportion * script.estimated_duration

        return durations
