#!/usr/bin/env python3
"""
Multithreaded RFID card analysis logic with reduced code complexity
"""

import itertools
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set, Tuple

from .models import CardData, FCCandidate, Match
from .utils import hex_to_binary, load_hid_patterns


class ProgressBar:
    """Thread-safe progress bar"""

    def __init__(self, total: int, desc: str = "Processing"):
        self.total = total
        self.current = 0
        self.desc = desc
        self.start_time = time.time()
        self.lock = threading.Lock()

    def update(self, increment: int = 1):
        with self.lock:
            self.current += increment
            percent = (self.current / self.total) * 100
            elapsed = time.time() - self.start_time
            eta = (elapsed / max(self.current, 1)) * (self.total - self.current)

            bar = "█" * int(50 * self.current // self.total) + "-" * (
                50 - int(50 * self.current // self.total)
            )
            sys.stdout.write(
                f"\r{self.desc}: |{bar}| {percent:.1f}% ETA: {eta:.1f}s"
            )
            sys.stdout.flush()

            if self.current >= self.total:
                print()

    def close(self):
        """Ensure progress bar is complete"""
        if self.current < self.total:
            self.current = self.total
            self._display()


class RFIDAnalyzer:
    """Multithreaded RFID card analyzer"""

    def __init__(
        self,
        min_bits: int = 32,
        max_bits: int = 35,
        known_fc: Optional[int] = None,
        unknown_cn_mode: bool = False,
        max_threads: int = 4,
        show_progress: bool = True,
    ):
        self.min_bits = min_bits
        self.max_bits = max_bits
        self.known_fc = known_fc
        self.unknown_cn_mode = unknown_cn_mode
        self.max_threads = max_threads
        self.show_progress = show_progress
        self.cards: List[CardData] = []
        self._card_counter = 0
        self.hid_patterns = load_hid_patterns()

    def add_card(
        self,
        hex_data: str,
        known_cn: Optional[int] = None,
        name: Optional[str] = None,
    ):
        """Add a card to analyze"""
        if name is None:
            self._card_counter += 1
            name = f"Card_{self._card_counter:03d}"

        cn_value = known_cn if known_cn is not None else -1
        self.cards.append(CardData(hex_data, cn_value, name))
        return self

    def add_cards(self, cards: List[Dict]):
        """Add multiple cards"""
        for card in cards:
            self.add_card(
                card["hex_data"], card.get("known_cn"), card.get("name")
            )
        return self

    def _analyze_card_worker(self, card: CardData) -> List[Match]:
        """Worker function for analyzing a single card"""
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
                        self._find_fc_cn_in_window(
                            window, card, reverse, offset, window_len
                        )
                    )

        return matches

    def _find_fc_cn_in_window(
        self,
        window: str,
        card: CardData,
        reverse: bool,
        offset: int,
        window_len: int,
    ) -> List[Match]:
        """Find FC/CN combinations in a window"""
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

                        # Check CN matching
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

    def _analyze_cards_threaded(self) -> List[Match]:
        """Analyze all cards using multiple threads"""
        all_matches = []

        if self.show_progress:
            progress = ProgressBar(len(self.cards), "Analyzing cards")

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            # Submit all card analysis tasks
            future_to_card = {
                executor.submit(self._analyze_card_worker, card): card
                for card in self.cards
            }

            # Collect results as they complete
            for future in as_completed(future_to_card):
                matches = future.result()
                all_matches.extend(matches)

                if self.show_progress:
                    progress.update()

        if self.show_progress:
            progress.close()

        return all_matches

    def find_fc_candidates(self) -> List[FCCandidate]:
        """Find FC candidates with multithreading"""
        if not self.cards:
            return []

        # Get all matches using threading
        all_matches = self._analyze_cards_threaded()

        # Group matches by FC value
        fc_groups = defaultdict(list)
        for match in all_matches:
            fc_groups[match.fc_value].append(match)

        candidates = []
        has_unknown_cn = any(card.known_cn == -1 for card in self.cards)

        if self.show_progress and len(fc_groups) > 1:
            progress = ProgressBar(len(fc_groups), "Processing FC candidates")

        for i, (fc_value, matches) in enumerate(fc_groups.items()):
            if not self._is_reasonable_fc_value(fc_value):
                if self.show_progress and len(fc_groups) > 1:
                    progress.update()
                continue

            if has_unknown_cn:
                candidate = self._process_unknown_cn_candidate(
                    fc_value, matches
                )
            else:
                candidate = self._process_known_cn_candidate(fc_value, matches)

            if candidate:
                self._apply_format_matching(candidate)
                candidates.append(candidate)

            if self.show_progress and len(fc_groups) > 1:
                progress.update()

        if self.show_progress and len(fc_groups) > 1:
            progress.close()

        return candidates

    def _process_known_cn_candidate(
        self, fc_value: int, matches: List[Match]
    ) -> Optional[FCCandidate]:
        """Process candidate when CNs are known"""
        if len(self.cards) == 1:
            return FCCandidate(fc_value, matches, 1.0)

        valid_matches = self._filter_consistent_matches(matches)
        if valid_matches:
            card_count = len(set(match.card_name for match in valid_matches))
            consistency = card_count / len(self.cards)
            if consistency == 1.0:
                return FCCandidate(fc_value, valid_matches, consistency)

        return None

    def _process_unknown_cn_candidate(
        self, fc_value: int, matches: List[Match]
    ) -> Optional[FCCandidate]:
        """Process candidate when CNs are unknown"""
        card_names_with_fc = set(match.card_name for match in matches)
        min_threshold = max(2, len(self.cards) * 0.5)

        if len(card_names_with_fc) >= min_threshold:
            best_matches = self._find_best_pattern_for_fc(
                matches, card_names_with_fc
            )
            if best_matches:
                consistency = len(card_names_with_fc) / len(self.cards)
                return FCCandidate(fc_value, best_matches, consistency)

        return None

    def _find_best_pattern_for_fc(
        self, matches: List[Match], card_names: Set[str]
    ) -> List[Match]:
        """Find the best pattern for an FC value"""
        # Group by pattern signature
        pattern_groups = defaultdict(list)
        for match in matches:
            sig = (
                match.reverse,
                match.window_offset,
                match.window_length,
                match.fc_start,
                match.fc_length,
                match.cn_start,
                match.cn_length,
            )
            pattern_groups[sig].append(match)

        # Find pattern with best coverage
        best_matches = []
        best_coverage = 0

        for pattern_matches in pattern_groups.values():
            pattern_cards = set(match.card_name for match in pattern_matches)
            coverage = len(pattern_cards)

            if coverage > best_coverage:
                best_coverage = coverage
                best_matches = pattern_matches

        # Return if good coverage, otherwise return representative matches
        if best_coverage >= max(2, len(card_names) * 0.8):
            return best_matches

        # One match per card
        representative = []
        for card_name in card_names:
            card_matches = [m for m in matches if m.card_name == card_name]
            if card_matches:
                # Pick best match based on standard characteristics
                best = max(
                    card_matches,
                    key=lambda m: (
                        1 if 8 <= m.fc_length <= 16 else 0,
                        1 if 8 <= m.cn_length <= 24 else 0,
                        0 if m.reverse else 1,
                        1 if 26 <= m.window_length <= 37 else 0,
                    ),
                )
                representative.append(best)

        return representative

    def _filter_consistent_matches(self, matches: List[Match]) -> List[Match]:
        """Filter matches for consistent patterns across cards"""
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

                matching = next(
                    (
                        m
                        for m in card_match_list
                        if m.get_signature() == pattern_sig
                    ),
                    None,
                )
                if matching:
                    pattern_matches.append(matching)
                else:
                    break
            else:
                valid_matches.extend(pattern_matches)

        return valid_matches

    def _is_reasonable_fc_value(self, fc_value: int) -> bool:
        """Check if FC value is reasonable"""
        return 1 <= fc_value <= 65535

    def _apply_format_matching(self, candidate: FCCandidate):
        """Apply HID format matching"""
        if not self.hid_patterns.get("formats"):
            return

        tolerance = self.hid_patterns["tolerance"]
        for match in candidate.matches:
            for fmt in self.hid_patterns["formats"]:
                if (
                    abs(match.window_length - fmt["total_bits"])
                    <= tolerance["bit_length"]
                    and abs(match.fc_length - fmt["fc_bits"])
                    <= tolerance["bit_length"]
                    and abs(match.cn_length - fmt["cn_bits"])
                    <= tolerance["bit_length"]
                    and abs(match.fc_start - fmt["fc_position"])
                    <= tolerance["position"]
                    and abs(match.cn_start - fmt["cn_position"])
                    <= tolerance["position"]
                ):
                    candidate.matched_format = fmt["name"]
                    return

    def get_best_candidates(self, max_candidates: int = 5) -> List[FCCandidate]:
        """Get the most likely FC candidates"""
        candidates = self.find_fc_candidates()

        if self.known_fc is not None:
            candidates = [c for c in candidates if c.fc_value == self.known_fc]

        candidates.sort(key=self._score_candidate, reverse=True)
        return candidates[:max_candidates]

    def _score_candidate(self, candidate: FCCandidate) -> float:
        """Score a candidate"""
        score = candidate.consistency_score * 100 + candidate.card_count * 50

        if candidate.matched_format:
            score += 100

        if candidate.matches:
            fc_len, cn_len = (
                candidate.matches[0].fc_length,
                candidate.matches[0].cn_length,
            )
            score += (
                20 if 8 <= fc_len <= 16 else (10 if 4 <= fc_len <= 20 else 0)
            )
            score += (
                10 if 8 <= cn_len <= 24 else (5 if 4 <= cn_len <= 32 else 0)
            )

        if not (1 <= candidate.fc_value <= 65535):
            score -= 50

        return score

    def analyze_unknown_cn_patterns(self) -> Dict:
        """Analyze unknown CN patterns"""
        unknown_cards = [card for card in self.cards if card.known_cn == -1]
        if not unknown_cards:
            return {}

        # Get matches for unknown CN cards using threading
        all_matches = []

        if self.show_progress:
            progress = ProgressBar(
                len(unknown_cards), "Analyzing unknown CN patterns"
            )

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            future_to_card = {
                executor.submit(self._analyze_card_worker, card): card
                for card in unknown_cards
            }

            for future in as_completed(future_to_card):
                all_matches.extend(future.result())
                if self.show_progress:
                    progress.update()

        if self.show_progress:
            progress.close()

        # Analyze patterns
        fc_dist = defaultdict(int)
        pattern_dist = defaultdict(int)

        for match in all_matches:
            fc_dist[match.fc_value] += 1
            pattern_key = f"{match.window_length}b_FC{match.fc_length}@{match.fc_start}_CN{match.cn_length}@{match.cn_start}"
            pattern_dist[pattern_key] += 1

        return {
            "total_cards": len(self.cards),
            "cards_with_unknown_cn": len(unknown_cards),
            "potential_fc_values": set(fc_dist.keys()),
            "most_common_fc_values": sorted(
                fc_dist.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "common_patterns": sorted(
                pattern_dist.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }
