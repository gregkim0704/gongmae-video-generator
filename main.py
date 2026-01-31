#!/usr/bin/env python3
"""
Real Estate Auction Video Generator
CLI entry point for generating auction property videos

Usage:
    python main.py --case 2024타경12345 [--mock] [--output video.mp4]
    python main.py --case data/input/property.json --input json  # JSON file input
    python main.py --template  # Generate JSON template
    python main.py --list  # List available properties
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import VideoGenerationPipeline
from src.scraper import MockScraper, JsonFileScraper, create_template_file
from src.config import settings


def print_banner():
    """Print application banner"""
    print("""
================================================================
    Real Estate Auction Video Generator
    v0.1.0
================================================================
    """)


async def list_properties(input_mode: str = "mock"):
    """List all available properties"""
    if input_mode == "json":
        scraper = JsonFileScraper()
        source_name = "JSON Files"
        source_dir = settings.data_dir / "input"
    else:
        scraper = MockScraper()
        source_name = "Mock Data"
        source_dir = settings.mock_dir

    properties = await scraper.search_properties(limit=100)

    if not properties:
        print(f"No properties found in {source_name}.")
        if input_mode == "json":
            print(f"\nJSON files should be placed in: {source_dir}")
            print("Use --template to generate a template file.")
        else:
            print("Check data/mock/sample_properties.json")
        return

    print(f"\n[LIST] Available Properties ({source_name}):\n")
    print("-" * 80)

    for prop in properties:
        from src.utils.korean import format_korean_price_simple
        print(f"  Case: {prop.case_number}")
        print(f"  Court: {prop.court}")
        print(f"  Type: {prop.asset_type_name}")
        print(f"  Address: {prop.address}")
        print(f"  Appraisal: {format_korean_price_simple(prop.appraisal_value)}")
        print(f"  Min Bid: {format_korean_price_simple(prop.minimum_bid)}")
        print(f"  Date: {prop.auction_date}")
        print("-" * 80)

    print(f"\nTotal: {len(properties)} properties")
    if input_mode == "json":
        print("\nUsage: python main.py --case <case_number_or_file.json> --input json")
    else:
        print("\nUsage: python main.py --case <case_number> --mock")


async def generate_video(
    case_number: str,
    mock_mode: bool = True,
    input_mode: str = "auto",
    output_filename: str = None
):
    """Generate auction video"""
    mode_names = {
        "mock": "Mock Data",
        "json": "JSON File",
        "crawl": "Web Crawling",
        "auto": "Auto (Mock)" if mock_mode else "Auto (JSON)"
    }

    print(f"\n[START] Starting video generation for: {case_number}")
    print(f"   Input Mode: {mode_names.get(input_mode, input_mode)}")
    print(f"   Mock TTS/LLM: {'Yes' if mock_mode else 'No'}")
    print()

    try:
        # Validate API keys if not in mock mode
        if not mock_mode:
            settings.validate_api_keys(mock_mode=False)

        # Create pipeline and generate
        pipeline = VideoGenerationPipeline(
            mock_mode=mock_mode,
            input_mode=input_mode
        )
        video_path = await pipeline.generate_video(
            case_number=case_number,
            output_filename=output_filename
        )

        print(f"\n[SUCCESS] Video generated successfully!")
        print(f"   Output: {video_path}")
        print()

        return video_path

    except ValueError as e:
        print(f"\n[ERROR] Error: {e}")
        if input_mode == "json":
            print("\nTip: Use --template to generate a JSON template file")
            print(f"     Place JSON files in: {settings.data_dir / 'input'}")
        else:
            print("\nTip: Use --list to see available properties")
        sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] Generation failed: {e}")
        import traceback
        if settings.debug:
            traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate auction property videos from case numbers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --list                             # List mock properties
  python main.py --list --input json                # List JSON file properties
  python main.py --case 2024타경12345 --mock        # Generate with mock data
  python main.py --case 2024타경12345 --input json  # Generate from JSON file
  python main.py --case property.json --input json  # Generate from specific JSON
  python main.py --template                         # Create JSON template file
        """
    )

    parser.add_argument(
        "--case", "-c",
        type=str,
        help="Auction case number (e.g., 2024타경12345) or JSON file path"
    )

    parser.add_argument(
        "--input", "-i",
        type=str,
        choices=["auto", "mock", "json", "crawl"],
        default="auto",
        help="Input mode: auto (default), mock, json, or crawl"
    )

    parser.add_argument(
        "--mock", "-m",
        action="store_true",
        default=True,
        help="Use mock TTS and LLM (default: True)"
    )

    parser.add_argument(
        "--no-mock",
        action="store_true",
        help="Disable mock mode (requires API keys)"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output filename (default: auto-generated)"
    )

    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available properties"
    )

    parser.add_argument(
        "--template", "-t",
        action="store_true",
        help="Generate JSON template file"
    )

    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug output"
    )

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Handle debug mode
    if args.debug:
        settings.debug = True

    # Determine mock mode
    mock_mode = not args.no_mock

    # Handle template generation
    if args.template:
        template_path = create_template_file()
        print(f"\n[SUCCESS] Template file created!")
        print(f"   Location: {template_path}")
        print(f"\n   Copy this file to: {settings.data_dir / 'input'}")
        print("   Fill in the auction property details and run:")
        print("   python main.py --case <filename>.json --input json")
        return

    # Handle list command
    if args.list:
        input_mode = args.input if args.input != "auto" else ("json" if not mock_mode else "mock")
        asyncio.run(list_properties(input_mode=input_mode))
        return

    # Require case number for generation
    if not args.case:
        parser.print_help()
        print("\n[ERROR] --case is required for video generation")
        print("   Use --list to see available properties")
        print("   Use --template to generate a JSON template")
        sys.exit(1)

    # Generate video
    asyncio.run(generate_video(
        case_number=args.case,
        mock_mode=mock_mode,
        input_mode=args.input,
        output_filename=args.output
    ))


if __name__ == "__main__":
    main()
