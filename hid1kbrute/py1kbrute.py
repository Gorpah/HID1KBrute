#!/usr/bin/env python3
"""
Enhanced RFID Card Analyzer - Main Application with Unknown CN Support
"""

import argparse
import json
import sys

from .analyzer import RFIDAnalyzer
from .display import ResultDisplay
from .utils import load_cards_from_file


def main():
    parser = argparse.ArgumentParser(
        description="Analyze RFID/HID card data to find facility codes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Known CN mode (original functionality)
  python -m py1kbrute -c 27bafc0864 32443
  python -m py1kbrute -c 27bafc0864 32443 -c 1a2b3c4d5e 12345
  python -m py1kbrute --known-fc 2436 -c 27bafc0864 32443
  
  # Unknown CN mode (new functionality)
  python -m py1kbrute --unknown-cn -c 27bafc0864 -c 1a2b3c4d5e
  python -m py1kbrute --unknown-cn --known-fc 2436 -c 27bafc0864 -c 1a2b3c4d5e
  python -m py1kbrute --unknown-cn --file cards_no_cn.json
  
  # Mixed mode (some cards with known CN, some without)
  python -m py1kbrute -c 27bafc0864 32443 -c 1a2b3c4d5e
        """,
    )

    parser.add_argument(
        "-c",
        "--card",
        nargs="+",
        action="append",
        metavar="HEX_DATA [KNOWN_CN] [NAME]",
        help="Add card (hex_data [known_cn] [name]). CN is optional in --unknown-cn mode.",
    )
    parser.add_argument("-f", "--file", help="Load cards from JSON file")
    parser.add_argument(
        "--known-fc", type=int, help="Known facility code to search for"
    )
    parser.add_argument(
        "--unknown-cn",
        action="store_true",
        help="Enable unknown CN mode - analyze cards without known card numbers",
    )
    parser.add_argument(
        "--min-bits", type=int, default=32, help="Min bit window (default: 32)"
    )
    parser.add_argument(
        "--max-bits", type=int, default=35, help="Max bit window (default: 35)"
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=5,
        help="Max candidates (default: 5)",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Show all details immediately",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colors"
    )
    parser.add_argument(
        "--analyze-patterns",
        action="store_true",
        help="Show detailed pattern analysis for unknown CN mode",
    )

    args = parser.parse_args()

    if not args.card and not args.file:
        print("Error: Must specify --card or --file")
        sys.exit(1)

    try:
        analyzer = RFIDAnalyzer(
            args.min_bits, args.max_bits, args.known_fc, args.unknown_cn
        )
        display = ResultDisplay(use_colors=not args.no_color)

        if args.file:
            analyzer.add_cards(load_cards_from_file(args.file))

        if args.card:
            for card_args in args.card:
                if len(card_args) < 1:
                    print("Error: Card requires at least HEX_DATA")
                    sys.exit(1)

                hex_data = card_args[0]

                # Parse CN - it's optional in unknown CN mode
                known_cn = None
                name = None

                if len(card_args) >= 2:
                    try:
                        known_cn = int(card_args[1])
                        if len(card_args) >= 3:
                            name = card_args[2]
                    except ValueError:
                        # If second arg is not a number, treat it as name
                        name = card_args[1]

                # In unknown CN mode, CN is optional
                if not args.unknown_cn and known_cn is None:
                    print(
                        "Error: Card requires KNOWN_CN when not in --unknown-cn mode"
                    )
                    sys.exit(1)

                analyzer.add_card(hex_data, known_cn, name)

        # Validate that we have enough cards for unknown CN mode
        if args.unknown_cn:
            unknown_cn_cards = sum(
                1 for card in analyzer.cards if card.known_cn == -1
            )
            if unknown_cn_cards < 2:
                print(
                    "Warning: Unknown CN mode works best with at least 2 cards without known CNs"
                )

        # Show pattern analysis if requested
        if args.analyze_patterns and args.unknown_cn:
            pattern_analysis = analyzer.analyze_unknown_cn_patterns()
            display.print_pattern_analysis(pattern_analysis)

        display.print_results(
            analyzer, args.max_candidates, not args.no_interactive
        )

    except (ValueError, KeyboardInterrupt) as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
