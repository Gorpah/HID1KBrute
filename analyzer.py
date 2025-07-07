#!/usr/bin/env python3
"""
Enhanced RFID card analysis logic with support for unknown CN values
"""

import itertools
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from models import CardData, FCCandidate, Match
from utils import hex_to_binary, load_hid_patterns


class RFIDAnalyzer:
    """Enhanced RFID card analyzer supporting unknown CN values"""

    def __init__(
        self,
        min_bits: int = 32,
        max_bits: int = 35,
        known_fc: Optional[int] = None,
        unknown_cn_mode: bool = False,
    ):
        self.min_bits = min_bits
        self.max_bits = max_bits
        self.known_fc = known_fc
        self.unknown_cn_mode = unknown_cn_mode
        self.cards: List[CardData] = []
        self._card_counter = 0
        self.hid_patterns = load_hid_patterns()

    def add_card(
        self,
        hex_data: str,
        known_cn: Optional[int] = None,
        name: Optional[str] = None,
    ):
        """Add a card to analyze (CN can be None for unknown CN mode)"""
        if name is None:
            self._card_counter += 1
            name = f"Card_{self._card_counter:03d}"

        # Use -1 as sentinel for unknown CN
        cn_value = known_cn if known_cn is not None else -1
        self.cards.append(CardData(hex_data, cn_value, name))
        return self

    def add_cards(self, cards: List[Dict]):
        """Add multiple cards from a list of dictionaries"""
        for card in cards:
            self.add_card(
                card["hex_data"], card.get("known_cn"), card.get("name")
            )
        return self

    def find_matches_single_card(self, card: CardData) -> List[Match]:
        """Find all possible FC/CN combinations for a single card"""
        raw_bits = hex_to_binary(card.hex_data)
        matches = []

        for reverse in [False, True]:
            bitstream = raw_bits[::-1] if reverse else raw_bits

            for window_len in range(
                self.min_bits, min(self.max_bits + 1, len(bitstream) + 1)
            ):
                for offset in range(len(bitstream) - window_len + 1):
                    window = bitstream[offset : offset + window_len]
                    matches.extend(
                        self._find_fc_cn_combinations(
                            window, card, reverse, offset, window_len
                        )
                    )

        return matches

    def _find_fc_cn_combinations(
        self,
        window: str,
        card: CardData,
        reverse: bool,
        offset: int,
        window_len: int,
    ) -> List[Match]:
        """Find all FC/CN combinations in a window"""
        matches = []

        for fc_start in range(window_len):
            for fc_len in range(1, window_len - fc_start):
                fc_bits = window[fc_start : fc_start + fc_len]
                fc_val = int(fc_bits, 2)

                if self.known_fc is not None and fc_val != self.known_fc:
                    continue

                for cn_start in range(window_len):
                    for cn_len in range(1, window_len - cn_start):
                        # Skip overlapping regions
                        if not (
                            fc_start + fc_len <= cn_start
                            or cn_start + cn_len <= fc_start
                        ):
                            continue

                        cn_bits = window[cn_start : cn_start + cn_len]
                        cn_val = int(cn_bits, 2)

                        # For unknown CN mode, accept any CN value
                        # For known CN mode, only accept matching CNs
                        if card.known_cn == -1 or cn_val == card.known_cn:
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

        # Check if we have unknown CNs
        has_unknown_cn = any(card.known_cn == -1 for card in self.cards)

        if has_unknown_cn:
            return self._find_fc_candidates_unknown_cn()
        else:
            return self._find_fc_candidates_known_cn()

    def _find_fc_candidates_known_cn(self) -> List[FCCandidate]:
        """Original method for when CNs are known"""
        all_matches = []
        for card in self.cards:
            all_matches.extend(self.find_matches_single_card(card))

        fc_groups = defaultdict(list)
        for match in all_matches:
            fc_groups[match.fc_value].append(match)

        candidates = []
        for fc_value, matches in fc_groups.items():
            if len(self.cards) == 1:
                candidate = FCCandidate(fc_value, matches, 1.0)
                self._apply_format_matching(candidate)
                candidates.append(candidate)
            else:
                valid_matches = self._filter_consistent_matches(matches)
                if valid_matches:
                    card_count = len(
                        set(match.card_name for match in valid_matches)
                    )
                    consistency = card_count / len(self.cards)
                    if consistency == 1.0:
                        candidate = FCCandidate(
                            fc_value, valid_matches, consistency
                        )
                        self._apply_format_matching(candidate)
                        candidates.append(candidate)

        return candidates

    def _find_fc_candidates_unknown_cn(self) -> List[FCCandidate]:
        """Find FC candidates when CNs are unknown"""
        # Get all possible matches for each card
        card_matches = {}
        for card in self.cards:
            card_matches[card.name] = self.find_matches_single_card(card)

        # Collect all matches by FC value first
        fc_all_matches = defaultdict(list)
        for card_name, matches in card_matches.items():
            for match in matches:
                if self.known_fc is None or match.fc_value == self.known_fc:
                    fc_all_matches[match.fc_value].append(match)

        # Build candidates by consolidating matches for each FC value
        candidates = []

        for fc_value, all_matches in fc_all_matches.items():
            if not self._is_reasonable_fc_value(fc_value):
                continue

            # Get unique cards that have this FC value
            card_names_with_fc = set(match.card_name for match in all_matches)

            # Only consider FCs that appear in multiple cards or meet minimum threshold
            min_card_threshold = max(
                2, len(self.cards) * 0.5
            )  # At least 50% of cards or 2 cards minimum

            if len(card_names_with_fc) >= min_card_threshold:
                # Try to find the best pattern(s) for this FC
                best_matches = self._find_best_pattern_for_fc(
                    all_matches, card_names_with_fc
                )

                if best_matches:
                    consistency_score = len(card_names_with_fc) / len(
                        self.cards
                    )
                    candidate = FCCandidate(
                        fc_value, best_matches, consistency_score
                    )
                    self._apply_format_matching(candidate)
                    candidates.append(candidate)

        return candidates

    def _find_best_pattern_for_fc(
        self, all_matches: List[Match], card_names: Set[str]
    ) -> List[Match]:
        """Find the best pattern for a given FC value across multiple cards"""
        # Group matches by pattern signature (excluding CN value)
        pattern_groups = defaultdict(list)

        for match in all_matches:
            pattern_sig = (
                match.reverse,
                match.window_offset,
                match.window_length,
                match.fc_start,
                match.fc_length,
                match.cn_start,
                match.cn_length,
            )
            pattern_groups[pattern_sig].append(match)

        # Find the pattern that covers the most cards
        best_pattern = None
        best_coverage = 0
        best_matches = []

        for pattern_sig, pattern_matches in pattern_groups.items():
            pattern_cards = set(match.card_name for match in pattern_matches)
            coverage = len(pattern_cards)

            if coverage > best_coverage:
                best_coverage = coverage
                best_pattern = pattern_sig
                best_matches = pattern_matches

        # If we found a good pattern, return its matches
        if best_coverage >= max(
            2, len(card_names) * 0.8
        ):  # At least 80% of cards with this FC
            return best_matches

        # Otherwise, return the most representative matches (one per card)
        representative_matches = []
        for card_name in card_names:
            card_matches = [m for m in all_matches if m.card_name == card_name]
            if card_matches:
                # Pick the match with the most common pattern characteristics
                best_match = max(
                    card_matches,
                    key=lambda m: (
                        # Prefer standard bit lengths
                        1 if 8 <= m.fc_length <= 16 else 0,
                        1 if 8 <= m.cn_length <= 24 else 0,
                        # Prefer non-reversed
                        0 if m.reverse else 1,
                        # Prefer reasonable window sizes
                        1 if 26 <= m.window_length <= 37 else 0,
                    ),
                )
                representative_matches.append(best_match)

        return representative_matches

    def _is_reasonable_fc_value(self, fc_value: int) -> bool:
        """Check if FC value is in a reasonable range"""
        # Most facility codes are between 1 and 65535 (16-bit)
        # Very large values are less likely to be correct
        return 1 <= fc_value <= 65535

    def _apply_format_matching(self, candidate: FCCandidate):
        """Apply HID format matching to candidate"""
        if not self.hid_patterns.get("formats"):
            return

        tolerance = self.hid_patterns["tolerance"]

        for match in candidate.matches:
            for fmt in self.hid_patterns["formats"]:
                if self._matches_format(match, fmt, tolerance):
                    candidate.matched_format = fmt["name"]
                    return

    def _matches_format(self, match: Match, fmt: Dict, tolerance: Dict) -> bool:
        """Check if match corresponds to a HID format"""
        return (
            abs(match.window_length - fmt["total_bits"])
            <= tolerance["bit_length"]
            and abs(match.fc_length - fmt["fc_bits"]) <= tolerance["bit_length"]
            and abs(match.cn_length - fmt["cn_bits"]) <= tolerance["bit_length"]
            and abs(match.fc_start - fmt["fc_position"])
            <= tolerance["position"]
            and abs(match.cn_start - fmt["cn_position"])
            <= tolerance["position"]
        )

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
                valid_matches.extend(pattern_matches)

        return valid_matches

    def get_best_candidates(self, max_candidates: int = 5) -> List[FCCandidate]:
        """Get the most likely FC candidates"""
        candidates = self.find_fc_candidates()

        if self.known_fc is not None:
            candidates = [c for c in candidates if c.fc_value == self.known_fc]

        candidates.sort(key=self._score_candidate, reverse=True)
        return candidates[:max_candidates]

    def _score_candidate(self, candidate: FCCandidate) -> float:
        """Score a candidate based on various factors"""
        score = candidate.consistency_score * 100
        score += candidate.card_count * 50

        if candidate.matched_format:
            score += 100

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

        # Bonus for unknown CN mode candidates that appear across multiple cards
        has_unknown_cn = any(
            match.cn_value != -1
            for match in candidate.matches
            if hasattr(match, "cn_value")
        )
        if not has_unknown_cn and candidate.card_count > 1:
            score += 25

        return score

    def analyze_unknown_cn_patterns(self) -> Dict:
        """Analyze patterns when CNs are unknown to provide insights"""
        if not any(card.known_cn == -1 for card in self.cards):
            return {}

        analysis = {
            "total_cards": len(self.cards),
            "cards_with_unknown_cn": sum(
                1 for card in self.cards if card.known_cn == -1
            ),
            "potential_fc_values": set(),
            "pattern_analysis": defaultdict(int),
        }

        # Get all matches for cards with unknown CNs
        unknown_cn_matches = []
        for card in self.cards:
            if card.known_cn == -1:
                unknown_cn_matches.extend(self.find_matches_single_card(card))

        # Analyze FC value distribution
        fc_distribution = defaultdict(int)
        for match in unknown_cn_matches:
            fc_distribution[match.fc_value] += 1
            analysis["potential_fc_values"].add(match.fc_value)

        # Find most common FC values
        analysis["most_common_fc_values"] = sorted(
            fc_distribution.items(), key=lambda x: x[1], reverse=True
        )[:10]

        # Analyze bit patterns
        pattern_distribution = defaultdict(int)
        for match in unknown_cn_matches:
            pattern_key = f"{match.window_length}b_FC{match.fc_length}@{match.fc_start}_CN{match.cn_length}@{match.cn_start}"
            pattern_distribution[pattern_key] += 1

        analysis["common_patterns"] = sorted(
            pattern_distribution.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return analysis
