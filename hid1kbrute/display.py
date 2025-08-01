#!/usr/bin/env python3
"""
Display and formatting utilities for RFID analysis results
"""

import sys
from collections import defaultdict
from typing import List

from .models import CardData, FCCandidate


class Colors:
    """ANSI color codes"""

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
        for attr in [
            "RESET",
            "BOLD",
            "RED",
            "GREEN",
            "YELLOW",
            "BLUE",
            "MAGENTA",
            "CYAN",
        ]:
            setattr(cls, attr, "")


class ResultDisplay:
    """Handles display of analysis results"""

    def __init__(self, use_colors: bool = True):
        if not use_colors or not sys.stdout.isatty():
            Colors.disable()

    def print_cards(self, cards: List[CardData]):
        """Print card information"""
        print(f"\n{Colors.BOLD}Cards:{Colors.RESET}")
        for card in cards:
            print(
                f"  {Colors.CYAN}{card.name}{Colors.RESET}: "
                f"{Colors.BOLD}{card.hex_data.upper()}{Colors.RESET} "
                f"(CN: {Colors.MAGENTA}{card.known_cn}{Colors.RESET})"
            )

    def print_candidate_summary(self, candidates: List[FCCandidate]):
        """Print summary of candidates"""
        print(
            f"\n{Colors.BOLD}{Colors.BLUE}Found {len(candidates)} FC candidates:{Colors.RESET}"
        )
        print(f"{Colors.CYAN}{'='*30}{Colors.RESET}")

        for i, candidate in enumerate(candidates, 1):
            confidence = self._get_confidence_level(candidate)
            format_info = (
                f" ({candidate.matched_format})"
                if candidate.matched_format
                else ""
            )

            print(
                f"{Colors.BOLD}[{i}]{Colors.RESET} "
                f"FC {Colors.BOLD}{candidate.fc_value}{Colors.RESET} | "
                f"{Colors.CYAN}{len(candidate.matches)}{Colors.RESET} matches | "
                f"{Colors.BLUE}{candidate.card_count}{Colors.RESET} cards | "
                f"{Colors.MAGENTA}{len(candidate.unique_patterns)}{Colors.RESET} patterns | "
                f"Conf: {confidence}{format_info}"
            )

    def print_candidate_details(self, candidate: FCCandidate):
        """Print detailed information about a candidate"""
        print(
            f"\n{Colors.BOLD}{Colors.GREEN}FC {candidate.fc_value} - Details{Colors.RESET}"
        )
        print(f"{Colors.CYAN}{'='*60}{Colors.RESET}")

        print(
            f"Summary: {Colors.BOLD}{len(candidate.matches)}{Colors.RESET} matches, "
            f"{Colors.BOLD}{candidate.card_count}{Colors.RESET} cards, "
            f"{Colors.BOLD}{len(candidate.unique_patterns)}{Colors.RESET} patterns"
        )

        if candidate.matched_format:
            print(
                f"Matched Format: {Colors.GREEN}{candidate.matched_format}{Colors.RESET}"
            )

        # Group matches by pattern
        pattern_groups = defaultdict(list)
        for match in candidate.matches:
            pattern_groups[match.get_signature()].append(match)

        for i, (pattern_sig, pattern_matches) in enumerate(
            pattern_groups.items(), 1
        ):
            self._print_pattern_details(i, pattern_matches)

    def _print_pattern_details(self, pattern_num: int, pattern_matches: List):
        """Print details for a specific pattern"""
        pattern = pattern_matches[0]
        cards_in_pattern = {match.card_name for match in pattern_matches}

        print(f"\n{Colors.YELLOW}Pattern #{pattern_num}:{Colors.RESET}")
        print(
            f"  Window: {Colors.BOLD}{pattern.window_length}{Colors.RESET} bits at offset {pattern.window_offset}"
        )
        print(
            f"  FC: {Colors.BOLD}{pattern.fc_length}{Colors.RESET} bits at pos {pattern.fc_start}"
        )
        print(
            f"  CN: {Colors.BOLD}{pattern.cn_length}{Colors.RESET} bits at pos {pattern.cn_start}"
        )
        print(f"  Reversed: {Colors.CYAN}{pattern.reverse}{Colors.RESET}")
        print(f"  Cards: {Colors.CYAN}{len(cards_in_pattern)}{Colors.RESET}")

        for card_name in sorted(cards_in_pattern):
            match = next(m for m in pattern_matches if m.card_name == card_name)
            print(
                f"#{Colors.YELLOW}{card_name}{Colors.RESET}: "
                f"FC={Colors.BOLD}{match.fc_bits}{Colors.RESET}, "
                f"CN={Colors.BOLD}{match.cn_bits}{Colors.RESET}"
            )

    def interactive_selection(self, candidates: List[FCCandidate]):
        """Interactive candidate selection"""
        self.print_candidate_summary(candidates)

        while True:
            try:
                print(f"\n{Colors.YELLOW}Options:{Colors.RESET}")
                print(f" 1-{len(candidates)}: view details")
                print(f" 'a': show all")
                print(f" 'q': quit")

                choice = (
                    input(f"\n{Colors.BOLD}Select: {Colors.RESET}")
                    .strip()
                    .lower()
                )

                if choice in ["q", "quit"]:
                    break
                elif choice in ["a", "all"]:
                    for candidate in candidates:
                        self.print_candidate_details(candidate)
                elif choice.isdigit() and 1 <= int(choice) <= len(candidates):
                    self.print_candidate_details(candidates[int(choice) - 1])
                else:
                    print(f"{Colors.RED}Invalid selection{Colors.RESET}")
            except (KeyboardInterrupt, EOFError):
                break

    def _get_confidence_level(self, candidate: FCCandidate) -> str:
        """Get confidence level description"""
        if candidate.card_count > 1:
            return f"{Colors.GREEN}HIGH{Colors.RESET}"
        elif candidate.matched_format:
            return f"{Colors.CYAN}KNOWN{Colors.RESET}"
        else:
            return f"{Colors.YELLOW}SINGLE{Colors.RESET}"

    def print_results(
        self, analyzer, max_candidates: int = 5, interactive: bool = True
    ):
        """Print complete analysis results"""
        if not analyzer.cards:
            print(f"{Colors.RED}No cards added{Colors.RESET}")
            return

        print(
            f"{Colors.BOLD}{Colors.GREEN}Analyzing {len(analyzer.cards)} cards...{Colors.RESET}"
        )

        if analyzer.known_fc is not None:
            print(
                f"{Colors.YELLOW}Searching for FC: {analyzer.known_fc}{Colors.RESET}"
            )

        self.print_cards(analyzer.cards)

        candidates = analyzer.get_best_candidates(max_candidates)

        if not candidates:
            print(f"{Colors.RED}No consistent patterns found{Colors.RESET}")
            return

        print(
            f"{Colors.GREEN}Found {len(candidates)} FC candidate(s){Colors.RESET}"
        )

        if len(candidates) == 1 or not interactive:
            for candidate in candidates:
                self.print_candidate_details(candidate)
        else:
            self.interactive_selection(candidates)

        if len(candidates) == 1:
            print(
                f"\n{Colors.BOLD}{Colors.GREEN}Most likely FC: {candidates[0].fc_value}{Colors.RESET}"
            )
