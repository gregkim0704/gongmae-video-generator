"""
Korean language utilities for formatting numbers and text
"""
from typing import Optional


def format_korean_price(amount: int, include_won: bool = True) -> str:
    """
    Format a price in Korean style (억, 천만, 만, 원)

    Examples:
        850000000 -> "8억 5천만원"
        1234567890 -> "12억 3천4백5십6만 7천8백9십원"
        45000000 -> "4천5백만원"
        3000000 -> "3백만원"

    Args:
        amount: Price in Korean Won
        include_won: Whether to append 원 at the end

    Returns:
        Formatted Korean price string
    """
    if amount == 0:
        return "0원" if include_won else "0"

    result = []

    # 억 (100 million)
    eok = amount // 100000000
    remainder = amount % 100000000

    if eok > 0:
        result.append(f"{eok}억")

    # 천만 (10 million)
    cheonman = remainder // 10000000
    remainder = remainder % 10000000

    if cheonman > 0:
        result.append(f"{cheonman}천")

    # 백만 (1 million)
    baekman = remainder // 1000000
    remainder = remainder % 1000000

    if baekman > 0:
        # If we already have 천, combine them
        if cheonman > 0 and result:
            result[-1] = f"{cheonman}천{baekman}백"
        else:
            result.append(f"{baekman}백")

    # 만 (10 thousand) - simplified for readability
    man = remainder // 10000
    remainder = remainder % 10000

    if man > 0:
        # Append 만 to previous if exists
        if result:
            result.append(f"{man}만")
        else:
            result.append(f"{man}만")
    elif result and (cheonman > 0 or baekman > 0):
        # Add 만 suffix to 천/백 numbers
        result[-1] += "만"

    # Below 만 (usually ignored for large amounts, but include for small)
    if remainder > 0 and amount < 100000000:
        # Only show details for smaller amounts
        if remainder >= 1000:
            result.append(f"{remainder // 1000}천")
            remainder = remainder % 1000
        if remainder >= 100:
            result.append(f"{remainder // 100}백")
            remainder = remainder % 100
        if remainder > 0:
            result.append(f"{remainder}")

    formatted = " ".join(result) if len(result) > 1 else "".join(result)

    if include_won:
        formatted += "원"

    return formatted


def format_korean_price_simple(amount: int) -> str:
    """
    Simplified Korean price formatting for scripts.

    Examples:
        850000000 -> "8억 5천만원"
        544000000 -> "5억 4천4백만원"
        45000000 -> "4천5백만원"
    """
    if amount == 0:
        return "0원"

    parts = []

    # 억 (100 million)
    eok = amount // 100000000
    remainder = amount % 100000000

    if eok > 0:
        parts.append(f"{eok}억")

    # 천만/백만/십만/만 (simplified)
    man = remainder // 10000
    if man > 0:
        # Format the 만 unit part
        man_str = ""
        if man >= 1000:
            man_str += f"{man // 1000}천"
            man = man % 1000
        if man >= 100:
            man_str += f"{man // 100}백"
            man = man % 100
        if man >= 10:
            man_str += f"{man // 10}십"
            man = man % 10
        if man > 0:
            man_str += str(man)
        man_str += "만"
        parts.append(man_str)

    result = " ".join(parts) if len(parts) > 1 else "".join(parts)
    return result + "원" if result else "0원"


def format_korean_area(area_sqm: Optional[float] = None, area_pyeong: Optional[float] = None) -> str:
    """
    Format area in Korean style (평 with optional sqm)

    Args:
        area_sqm: Area in square meters
        area_pyeong: Area in pyeong (Korean unit)

    Returns:
        Formatted area string like "85.5평" or "85.5평 (282.6m²)"
    """
    if area_pyeong is not None:
        pyeong = area_pyeong
    elif area_sqm is not None:
        # Convert sqm to pyeong (1평 = 3.3058 sqm)
        pyeong = area_sqm / 3.3058
    else:
        return ""

    # Round to 1 decimal place
    pyeong = round(pyeong, 1)

    # Format with optional sqm
    if area_sqm is not None:
        return f"{pyeong}평 ({round(area_sqm, 1)}m²)"
    else:
        return f"{pyeong}평"


def format_percent(value: float) -> str:
    """
    Format percentage in Korean style

    Args:
        value: Decimal value (e.g., 0.64 for 64%)

    Returns:
        Formatted percentage string like "64%"
    """
    return f"{int(value * 100)}%"


def format_date_korean(date_str: str) -> str:
    """
    Format date in Korean style

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Formatted date like "2024년 3월 15일"
    """
    try:
        parts = date_str.split("-")
        year, month, day = parts[0], parts[1].lstrip("0"), parts[2].lstrip("0")
        return f"{year}년 {month}월 {day}일"
    except (ValueError, IndexError):
        return date_str


def sqm_to_pyeong(sqm: float) -> float:
    """Convert square meters to pyeong"""
    return sqm / 3.3058


def pyeong_to_sqm(pyeong: float) -> float:
    """Convert pyeong to square meters"""
    return pyeong * 3.3058
