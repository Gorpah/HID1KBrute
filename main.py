#!/usr/bin/env python3
"""
Enhanced RFID Card Analyzer - Refactored Version
Analyzes RFID/HID card data to find facility codes and card numbers
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


class Colors:
    """ANSI color codes for terminal output"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"

    @classmethod
    def disable(cls):
        """Disable all colors"""
        cls.RESET = cls.BOLD = cls.RED = cls.GREEN = cls.YELLOW = ""
        cls.BLUE = cls.MAGENTA = cls.CYAN = ""


@dataclass
class CardData:
    """Holds card information"""

    hex_data: str
    known_cn: int
    name: str


@dataclass
class Match:
    """Represents a potential FC/CN match"""

    reverse: bool
    window_offset: int
    window_length: int
    fc_value: int
    fc_bits: str
    fc_start: int
    fc_length: int
    cn_value: int
    cn_bits: str
    cn_start: int
    cn_length: int
    card_name: Optional[str] = None

    def get_signature(self) -> Tuple:
        """Get unique signature for this bit pattern"""
        return (
            self.reverse,
            self.window_offset,
            self.window_length,
            self.fc_start,
            self.fc_length,
            self.cn_start,
            self.cn_length,
        )


@dataclass
class FCCandidate:
    """Represents a facility code candidate with all its permutations"""

    fc_value: int
    matches: List[Match]
    consistency_score: float
    real_world_boost: float = 0.0
    matched_format: Optional[str] = None

    @property
    def unique_patterns(self) -> List[Tuple]:
        """Get all unique bit patterns for this FC"""
        return list(set(match.get_signature() for match in self.matches))

    @property
    def card_count(self) -> int:
        """Number of cards with this FC"""
        return len(set(match.card_name for match in self.matches))

    @property
    def total_score(self) -> float:
        """Total confidence score including real-world pattern boost"""
        return self.consistency_score + self.real_world_boost


class RFIDAnalyzer:
    """Enhanced RFID card analyzer"""

    def __init__(
        self,
        min_bits: int = 32,
        max_bits: int = 35,
        known_fc: Optional[int] = None,
    ):
        self.min_bits = min_bits
        self.max_bits = max_bits
        self.known_fc = known_fc
        self.cards: List[CardData] = []
        self._card_counter = 0
        self.hid_patterns = self._load_hid_patterns()

    def add_card(
        self, hex_data: str, known_cn: int, name: Optional[str] = None
    ):
        """Add a card to analyze"""
        if name is None:
            self._card_counter += 1
            name = f"Card_{self._card_counter:03d}"

        self.cards.append(CardData(hex_data, known_cn, name))
        return self

    def add_cards(self, cards: List[Dict]):
        """Add multiple cards from a list of dictionaries"""
        for card in cards:
            self.add_card(card["hex_data"], card["known_cn"], card.get("name"))
        return self

    def _load_hid_patterns(self) -> Dict:
        """Load HID card patterns from JSON file"""
        try:
            # Try to load from same directory as script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            patterns_file = os.path.join(script_dir, "hid_patterns.json")

            if os.path.exists(patterns_file):
                with open(patterns_file, "r") as f:
                    return json.load(f)
            else:
                # Return empty structure if file doesn't exist
                return {
                    "formats": [],
                    "tolerance": {"bit_length": 2, "position": 3},
                }
        except Exception:
            return {
                "formats": [],
                "tolerance": {"bit_length": 2, "position": 3},
            }

    def _check_real_world_pattern(
        self, match: Match
    ) -> Tuple[float, Optional[str]]:
        """Check if match corresponds to a real HID card format"""
        best_boost = 0.0
        best_format = None

        if not self.hid_patterns.get("formats"):
            return best_boost, best_format

        tolerance = self.hid_patterns["tolerance"]

        for fmt in self.hid_patterns["formats"]:
            # Check if window length matches format (with tolerance)
            if (
                abs(match.window_length - fmt["total_bits"])
                <= tolerance["bit_length"]
            ):
                # Check FC bit length
                if (
                    abs(match.fc_length - fmt["fc_bits"])
                    <= tolerance["bit_length"]
                ):
                    # Check CN bit length
                    if (
                        abs(match.cn_length - fmt["cn_bits"])
                        <= tolerance["bit_length"]
                    ):
                        # Check positions (with tolerance)
                        if (
                            abs(match.fc_start - fmt["fc_position"])
                            <= tolerance["position"]
                            and abs(match.cn_start - fmt["cn_position"])
                            <= tolerance["position"]
                        ):

                            boost = fmt["confidence_boost"]
                            if boost > best_boost:
                                best_boost = boost
                                best_format = fmt["name"]

        return best_boost, best_format

    @staticmethod
    def hex_to_binary(hex_str: str) -> str:
        """Convert hex to binary string"""
        return bin(int(hex_str, 16))[2:].zfill(len(hex_str) * 4)

    def find_matches_single_card(self, card: CardData) -> List[Match]:
        """Find all possible FC/CN combinations for a single card"""
        raw_bits = self.hex_to_binary(card.hex_data)
        matches = []

        # Try both bit orders and all window configurations
        for reverse in [False, True]:
            bitstream = raw_bits[::-1] if reverse else raw_bits

            for window_len in range(
                self.min_bits, min(self.max_bits + 1, len(bitstream) + 1)
            ):
                for offset in range(len(bitstream) - window_len + 1):
                    window = bitstream[offset : offset + window_len]

                    # Try all FC/CN position combinations
                    for fc_start in range(window_len):
                        for fc_len in range(1, window_len - fc_start):
                            fc_bits = window[fc_start : fc_start + fc_len]
                            fc_val = int(fc_bits, 2)

                            # Skip if we have a target FC and this doesn't match
                            if (
                                self.known_fc is not None
                                and fc_val != self.known_fc
                            ):
                                continue

                            for cn_start in range(window_len):
                                for cn_len in range(1, window_len - cn_start):
                                    # Skip overlapping regions
                                    if not (
                                        fc_start + fc_len <= cn_start
                                        or cn_start + cn_len <= fc_start
                                    ):
                                        continue

                                    cn_bits = window[
                                        cn_start : cn_start + cn_len
                                    ]
                                    cn_val = int(cn_bits, 2)

                                    # Check if CN matches known value
                                    if cn_val == card.known_cn:
                                        matches.append(
                                            Match(
                                                reverse=reverse,
                                                window_offset=offset,
                                                window_length=window_len,
                                                fc_value=fc_val,
                                                fc_bits=fc_bits,
                                                fc_start=fc_start,
                                                fc_length=fc_len,
                                                cn_value=cn_val,
                                                cn_bits=cn_bits,
                                                cn_start=cn_start,
                                                cn_length=cn_len,
                                                card_name=card.name,
                                            )
                                        )
        return matches

    def find_fc_candidates(self) -> List[FCCandidate]:
        """Find FC candidates"""
        if not self.cards:
            return []

        # Get all matches for all cards
        all_matches = []
        for card in self.cards:
            all_matches.extend(self.find_matches_single_card(card))

        # Group by FC value
        fc_groups = defaultdict(list)
        for match in all_matches:
            fc_groups[match.fc_value].append(match)

        candidates = []
        for fc_value, matches in fc_groups.items():
            if len(self.cards) == 1:
                # Single card: include all matches
                candidate = FCCandidate(fc_value, matches, 1.0)
                # Apply real-world pattern boost
                self._apply_real_world_boost(candidate)
                candidates.append(candidate)
            else:
                # Multiple cards: only include patterns that work across ALL cards
                valid_matches = self._filter_consistent_matches(matches)
                if valid_matches:
                    card_count = len(
                        set(match.card_name for match in valid_matches)
                    )
                    consistency = card_count / len(self.cards)
                    if consistency == 1.0:  # Must work across all cards
                        candidate = FCCandidate(
                            fc_value, valid_matches, consistency
                        )
                        self._apply_real_world_boost(candidate)
                        candidates.append(candidate)

        return candidates

    def _apply_real_world_boost(self, candidate: FCCandidate):
        """Apply real-world pattern boost to candidate"""
        best_boost = 0.0
        best_format = None

        for match in candidate.matches:
            boost, format_name = self._check_real_world_pattern(match)
            if boost > best_boost:
                best_boost = boost
                best_format = format_name

        candidate.real_world_boost = best_boost
        candidate.matched_format = best_format

    def _filter_consistent_matches(self, matches: List[Match]) -> List[Match]:
        """Filter matches to only include patterns that work across all cards"""
        card_matches = defaultdict(list)
        for match in matches:
            card_matches[match.card_name].append(match)

        valid_matches = []
        first_card = next(iter(card_matches.keys()))

        for first_match in card_matches[first_card]:
            pattern_sig = first_match.get_signature()
            pattern_matches = [first_match]

            # Check if this pattern exists in ALL other cards
            for card_name, card_match_list in card_matches.items():
                if card_name == first_card:
                    continue

                matching_pattern = next(
                    (
                        m
                        for m in card_match_list
                        if m.get_signature() == pattern_sig
                    ),
                    None,
                )
                if matching_pattern:
                    pattern_matches.append(matching_pattern)
                else:
                    break
            else:
                # Pattern found in all cards
                valid_matches.extend(pattern_matches)

        return valid_matches

    def get_best_fc_candidates(
        self, max_candidates: int = 5
    ) -> List[FCCandidate]:
        """Get the most likely FC candidates"""
        candidates = self.find_fc_candidates()

        if self.known_fc is not None:
            candidates = [c for c in candidates if c.fc_value == self.known_fc]

        # Score and sort candidates
        def score_candidate(candidate: FCCandidate) -> float:
            score = candidate.consistency_score * 100
            score += candidate.card_count * 50
            score += candidate.real_world_boost  # Add real-world pattern boost

            if candidate.matches:
                fc_len = candidate.matches[0].fc_length
                cn_len = candidate.matches[0].cn_length
                if 8 <= fc_len <= 16:
                    score += 20
                elif 4 <= fc_len <= 20:
                    score += 10
                if 8 <= cn_len <= 24:
                    score += 10
                elif 4 <= cn_len <= 32:
                    score += 5

            if candidate.fc_value > 65535 or candidate.fc_value < 1:
                score -= 50

            return score

        candidates.sort(key=score_candidate, reverse=True)
        return candidates[:max_candidates]

    def _print_candidate_summary(self, candidate: FCCandidate) -> str:
        """Generate summary line for a candidate"""
        pattern_count = len(candidate.unique_patterns)

        if candidate.card_count > 1:
            confidence = f"{Colors.GREEN}HIGH{Colors.RESET}"
        elif candidate.matched_format:
            confidence = f"{Colors.CYAN}KNOWN{Colors.RESET}"
        else:
            confidence = f"{Colors.YELLOW}SINGLE{Colors.RESET}"

        format_info = (
            f" ({candidate.matched_format})" if candidate.matched_format else ""
        )

        return (
            f"FC {Colors.BOLD}{candidate.fc_value}{Colors.RESET} | "
            f"{Colors.CYAN}{len(candidate.matches)}{Colors.RESET} matches | "
            f"{Colors.BLUE}{candidate.card_count}{Colors.RESET} cards | "
            f"{Colors.MAGENTA}{pattern_count}{Colors.RESET} patterns | "
            f"Conf: {confidence}{format_info}"
        )

    def _print_candidate_details(self, candidate: FCCandidate):
        """Print detailed information about a candidate"""
        print(
            f"\n{Colors.BOLD}{Colors.GREEN}📊 FC {candidate.fc_value} - All Permutations{Colors.RESET}"
        )
        print(f"{Colors.CYAN}{'='*60}{Colors.RESET}")

        print(
            f"📊 Summary: {Colors.BOLD}{len(candidate.matches)}{Colors.RESET} matches, "
            f"{Colors.BOLD}{candidate.card_count}{Colors.RESET} cards, "
            f"{Colors.BOLD}{len(candidate.unique_patterns)}{Colors.RESET} patterns"
        )

        if candidate.matched_format:
            print(
                f"🎯 Matched Format: {Colors.GREEN}{candidate.matched_format}{Colors.RESET} "
                f"(+{candidate.real_world_boost} confidence)"
            )
        elif candidate.real_world_boost > 0:
            print(
                f"🎯 Pattern Boost: {Colors.CYAN}+{candidate.real_world_boost}{Colors.RESET}"
            )
        else:
            print(f"⚠️  No known format match")

        # Group matches by pattern
        pattern_groups = defaultdict(list)
        for match in candidate.matches:
            pattern_groups[match.get_signature()].append(match)

        for i, (pattern_sig, pattern_matches) in enumerate(
            pattern_groups.items(), 1
        ):
            pattern = pattern_matches[0]
            cards_in_pattern = {match.card_name for match in pattern_matches}

            print(f"\n{Colors.YELLOW}🔍 Pattern #{i}:{Colors.RESET}")
            print(
                f"  📐 Window: {Colors.BOLD}{pattern.window_length}{Colors.RESET} bits at offset {pattern.window_offset}"
            )
            print(
                f"  🎯 FC: {Colors.BOLD}{pattern.fc_length}{Colors.RESET} bits at pos {pattern.fc_start}"
            )
            print(
                f"  🎯 CN: {Colors.BOLD}{pattern.cn_length}{Colors.RESET} bits at pos {pattern.cn_start}"
            )
            print(
                f"  🔄 Reversed: {Colors.CYAN}{pattern.reverse}{Colors.RESET}"
            )
            print(
                f"  📱 Cards: {Colors.CYAN}{len(cards_in_pattern)}{Colors.RESET}"
            )

            for card_name in sorted(cards_in_pattern):
                match = next(
                    m for m in pattern_matches if m.card_name == card_name
                )
                print(
                    f"    └─ {Colors.YELLOW}{card_name}{Colors.RESET}: "
                    f"FC={Colors.BOLD}{match.fc_bits}{Colors.RESET}, "
                    f"CN={Colors.BOLD}{match.cn_bits}{Colors.RESET}"
                )

    def _interactive_selection(self, candidates: List[FCCandidate]):
        """Interactive candidate selection"""
        print(
            f"\n{Colors.BOLD}{Colors.BLUE}🔍 Found {len(candidates)} FC candidates:{Colors.RESET}"
        )
        print(f"{Colors.CYAN}{'─'*60}{Colors.RESET}")

        for i, candidate in enumerate(candidates, 1):
            print(
                f"{Colors.BOLD}[{i}]{Colors.RESET} {self._print_candidate_summary(candidate)}"
            )

        while True:
            try:
                print(f"\n{Colors.YELLOW}Options:{Colors.RESET}")
                print(f"  • 1-{len(candidates)}: view details")
                print(f"  • '{Colors.GREEN}a{Colors.RESET}': show all")
                print(f"  • '{Colors.RED}q{Colors.RESET}': quit")

                choice = (
                    input(f"\n{Colors.BOLD}Select: {Colors.RESET}")
                    .strip()
                    .lower()
                )

                if choice in ["q", "quit"]:
                    break
                elif choice in ["a", "all"]:
                    for candidate in candidates:
                        self._print_candidate_details(candidate)
                elif choice.isdigit() and 1 <= int(choice) <= len(candidates):
                    self._print_candidate_details(candidates[int(choice) - 1])
                else:
                    print(f"{Colors.RED}❌ Invalid selection{Colors.RESET}")
            except (KeyboardInterrupt, EOFError):
                break

    def print_results(self, max_candidates: int = 5, interactive: bool = True):
        """Print analysis results"""
        if not self.cards:
            print(f"{Colors.RED}❌ No cards added{Colors.RESET}")
            return

        print(
            f"{Colors.BOLD}{Colors.GREEN}🔍 Analyzing {len(self.cards)} cards...{Colors.RESET}"
        )

        if self.known_fc is not None:
            print(
                f"{Colors.YELLOW}🔒 Searching for FC: {self.known_fc}{Colors.RESET}"
            )

        print(f"\n{Colors.BOLD}📊 Cards:{Colors.RESET}")
        for card in self.cards:
            print(
                f"  {Colors.CYAN}{card.name}{Colors.RESET}: "
                f"{Colors.BOLD}{card.hex_data.upper()}{Colors.RESET} "
                f"(CN: {Colors.MAGENTA}{card.known_cn}{Colors.RESET})"
            )

        candidates = self.get_best_fc_candidates(max_candidates)

        if not candidates:
            print(f"{Colors.RED}❌ No consistent patterns found{Colors.RESET}")
            return

        print(
            f"{Colors.GREEN}✅ Found {len(candidates)} FC candidate(s){Colors.RESET}"
        )

        if len(candidates) == 1 or not interactive:
            for candidate in candidates:
                self._print_candidate_details(candidate)
        else:
            self._interactive_selection(candidates)

        # Success message
        if len(candidates) == 1:
            print(
                f"\n{Colors.BOLD}{Colors.GREEN}🎉 Most likely FC: {candidates[0].fc_value}{Colors.RESET}"
            )


def load_cards_from_file(filename: str) -> List[Dict]:
    """Load cards from JSON file"""
    try:
        with open(filename, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]
    except Exception as e:
        print(f"{Colors.RED}Error loading {filename}: {e}{Colors.RESET}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze RFID/HID card data to find facility codes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rfid_analyzer.py -c 27bafc0864 32443
  python rfid_analyzer.py -c 27bafc0864 32443 -c 1a2b3c4d5e 12345
  python rfid_analyzer.py --known-fc 2436 -c 27bafc0864 32443
  python rfid_analyzer.py --file cards.json
        """,
    )

    parser.add_argument(
        "-c",
        "--card",
        nargs="+",
        action="append",
        metavar="HEX_DATA KNOWN_CN [NAME]",
        help="Add card",
    )
    parser.add_argument("-f", "--file", help="Load cards from JSON file")
    parser.add_argument(
        "--known-fc", type=int, help="Known facility code to search for"
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

    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    if not args.card and not args.file:
        print(f"{Colors.RED}❌ Must specify --card or --file{Colors.RESET}")
        sys.exit(1)

    try:
        analyzer = RFIDAnalyzer(args.min_bits, args.max_bits, args.known_fc)

        if args.file:
            analyzer.add_cards(load_cards_from_file(args.file))

        if args.card:
            for card_args in args.card:
                if len(card_args) < 2:
                    print(
                        f"{Colors.RED}❌ Card requires HEX_DATA and KNOWN_CN{Colors.RESET}"
                    )
                    sys.exit(1)

                hex_data, known_cn = card_args[0], int(card_args[1])
                name = card_args[2] if len(card_args) > 2 else None
                analyzer.add_card(hex_data, known_cn, name)

        analyzer.print_results(args.max_candidates, not args.no_interactive)

    except (ValueError, KeyboardInterrupt) as e:
        print(f"{Colors.RED}❌ {e}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
