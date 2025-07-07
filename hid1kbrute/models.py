#!/usr/bin/env python3
"""
Data models for RFID card analysis
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


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
    card_name: str

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
    """Represents a facility code candidate"""

    fc_value: int
    matches: List[Match]
    consistency_score: float
    matched_format: Optional[str] = None

    @property
    def unique_patterns(self) -> List[Tuple]:
        """Get all unique bit patterns for this FC"""
        return list(set(match.get_signature() for match in self.matches))

    @property
    def card_count(self) -> int:
        """Number of cards with this FC"""
        return len(set(match.card_name for match in self.matches))
