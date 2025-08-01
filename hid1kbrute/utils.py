#!/usr/bin/env python3
"""
Enhanced utilities for RFID card analysis with unknown CN support
"""

import json
import os
from typing import Dict, List, Optional


def hex_to_binary(hex_string: str) -> str:
    """Convert hex string to binary string"""
    # Remove any spaces or non-hex characters
    hex_clean = "".join(c for c in hex_string if c in "0123456789abcdefABCDEF")

    # Convert to binary
    binary = bin(int(hex_clean, 16))[2:]

    # Pad to ensure we have full bytes
    while len(binary) % 8 != 0:
        binary = "0" + binary

    return binary


def load_cards_from_file(filename: str) -> List[Dict]:
    """Load cards from JSON file with support for optional CN values"""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File not found: {filename}")

    with open(filename, "r") as f:
        data = json.load(f)

    cards = []

    if isinstance(data, list):
        # List of cards
        for i, card in enumerate(data):
            if isinstance(card, dict):
                if "hex_data" not in card:
                    raise ValueError(
                        f"Card {i} missing required 'hex_data' field"
                    )

                cards.append(
                    {
                        "hex_data": card["hex_data"],
                        "known_cn": card.get("known_cn"),  # None if not present
                        "name": card.get("name", f"Card_{i+1:03d}"),
                    }
                )
            elif isinstance(card, str):
                # Just hex data
                cards.append(
                    {
                        "hex_data": card,
                        "known_cn": None,
                        "name": f"Card_{i+1:03d}",
                    }
                )
            else:
                raise ValueError(f"Invalid card format at index {i}")

    elif isinstance(data, dict):
        # Single card or dictionary format
        if "cards" in data:
            # Format: {"cards": [...]}
            return load_cards_from_file_content(data["cards"])
        else:
            # Single card
            cards.append(
                {
                    "hex_data": data["hex_data"],
                    "known_cn": data.get("known_cn"),
                    "name": data.get("name", "Card_001"),
                }
            )

    else:
        raise ValueError("Invalid file format")

    return cards


def load_cards_from_file_content(card_list: List) -> List[Dict]:
    """Helper function to process card list from file content"""
    cards = []

    for i, card in enumerate(card_list):
        if isinstance(card, dict):
            if "hex_data" not in card:
                raise ValueError(f"Card {i} missing required 'hex_data' field")

            cards.append(
                {
                    "hex_data": card["hex_data"],
                    "known_cn": card.get("known_cn"),
                    "name": card.get("name", f"Card_{i+1:03d}"),
                }
            )
        elif isinstance(card, str):
            # Just hex data
            cards.append(
                {"hex_data": card, "known_cn": None, "name": f"Card_{i+1:03d}"}
            )
        else:
            raise ValueError(f"Invalid card format at index {i}")

    return cards


def create_sample_card_files():
    """Create sample card files for testing"""

    # Sample file with known CNs
    known_cn_cards = [
        {"hex_data": "27bafc0864", "known_cn": 32443, "name": "Employee_001"},
        {"hex_data": "1a2b3c4d5e", "known_cn": 12345, "name": "Employee_002"},
        {"hex_data": "deadbeef01", "known_cn": 54321, "name": "Employee_003"},
    ]

    # Sample file with unknown CNs
    unknown_cn_cards = [
        {"hex_data": "27bafc0864", "name": "Card_A"},
        {"hex_data": "1a2b3c4d5e", "name": "Card_B"},
        {"hex_data": "deadbeef01", "name": "Card_C"},
        {"hex_data": "cafebabe99", "name": "Card_D"},
    ]

    # Mixed mode cards
    mixed_cards = [
        {"hex_data": "27bafc0864", "known_cn": 32443, "name": "Known_001"},
        {"hex_data": "1a2b3c4d5e", "name": "Unknown_001"},
        {"hex_data": "deadbeef01", "name": "Unknown_002"},
    ]

    # Save sample files
    with open("cards_known_cn.json", "w") as f:
        json.dump(known_cn_cards, f, indent=2)

    with open("cards_unknown_cn.json", "w") as f:
        json.dump(unknown_cn_cards, f, indent=2)

    with open("cards_mixed.json", "w") as f:
        json.dump(mixed_cards, f, indent=2)

    print("Created sample card files:")
    print("  - cards_known_cn.json (all cards have known CNs)")
    print("  - cards_unknown_cn.json (no cards have known CNs)")
    print("  - cards_mixed.json (some cards have known CNs)")


def load_hid_patterns() -> Dict:
    """Load HID card format patterns"""
    # Common HID card formats
    patterns = {
        "formats": [
            {
                "name": "H10301 (26-bit)",
                "total_bits": 26,
                "fc_bits": 8,
                "fc_position": 1,
                "cn_bits": 16,
                "cn_position": 9,
                "description": "Standard 26-bit format",
            },
            {
                "name": "H10304 (37-bit)",
                "total_bits": 37,
                "fc_bits": 16,
                "fc_position": 1,
                "cn_bits": 19,
                "cn_position": 17,
                "description": "37-bit format with large FC",
            },
            {
                "name": "H10320 (36-bit)",
                "total_bits": 36,
                "fc_bits": 16,
                "fc_position": 1,
                "cn_bits": 18,
                "cn_position": 17,
                "description": "36-bit format",
            },
            {
                "name": "H10302 (34-bit)",
                "total_bits": 34,
                "fc_bits": 16,
                "fc_position": 1,
                "cn_bits": 16,
                "cn_position": 17,
                "description": "34-bit format",
            },
            {
                "name": "Corporate 1000 (35-bit)",
                "total_bits": 35,
                "fc_bits": 12,
                "fc_position": 2,
                "cn_bits": 20,
                "cn_position": 14,
                "description": "Corporate 1000 format",
            },
        ],
        "tolerance": {"bit_length": 2, "position": 2},
    }

    return patterns


def validate_hex_data(hex_data: str) -> bool:
    """Validate hex data format"""
    try:
        # Remove any spaces or separators
        hex_clean = "".join(
            c for c in hex_data if c in "0123456789abcdefABCDEF"
        )

        # Must have even number of characters (complete bytes)
        if len(hex_clean) % 2 != 0:
            return False

        # Must be at least 4 bytes (32 bits)
        if len(hex_clean) < 8:
            return False

        # Try to convert to verify it's valid hex
        int(hex_clean, 16)
        return True

    except ValueError:
        return False


def format_bit_pattern(
    binary_string: str, window_start: int = 0, window_length: int = None
) -> str:
    """Format binary string for display with optional window highlighting"""
    if window_length is None:
        window_length = len(binary_string)

    # Add spaces every 8 bits for readability
    formatted = ""
    for i, bit in enumerate(binary_string):
        if i > 0 and i % 8 == 0:
            formatted += " "
        formatted += bit

    return formatted


def analyze_bit_distribution(hex_data: str) -> Dict:
    """Analyze bit distribution in hex data"""
    binary = hex_to_binary(hex_data)

    analysis = {
        "total_bits": len(binary),
        "ones": binary.count("1"),
        "zeros": binary.count("0"),
        "density": binary.count("1") / len(binary),
        "transitions": 0,
        "longest_run_ones": 0,
        "longest_run_zeros": 0,
    }

    # Count transitions (bit changes)
    for i in range(1, len(binary)):
        if binary[i] != binary[i - 1]:
            analysis["transitions"] += 1

    # Find longest runs
    current_run = 1
    current_bit = binary[0]
    longest_ones = 0
    longest_zeros = 0

    for i in range(1, len(binary)):
        if binary[i] == current_bit:
            current_run += 1
        else:
            if current_bit == "1":
                longest_ones = max(longest_ones, current_run)
            else:
                longest_zeros = max(longest_zeros, current_run)
            current_run = 1
            current_bit = binary[i]

    # Handle final run
    if current_bit == "1":
        longest_ones = max(longest_ones, current_run)
    else:
        longest_zeros = max(longest_zeros, current_run)

    analysis["longest_run_ones"] = longest_ones
    analysis["longest_run_zeros"] = longest_zeros

    return analysis


if __name__ == "__main__":
    # Create sample files when run directly
    create_sample_card_files()
