#!/usr/bin/env python3
"""
Enhanced RFID Card Analyzer with CLI support and interactive selection
Analyzes HID/RFID card data to find facility codes and card numbers
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# Color constants for terminal output
class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    
    @classmethod
    def disable(cls):
        """Disable colors (useful for non-terminal output)"""
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = ''
        cls.MAGENTA = cls.CYAN = cls.WHITE = cls.BOLD = cls.UNDERLINE = cls.RESET = ''


@dataclass
class CardData:
    """Represents a single card's data"""
    hex_data: str
    known_cn: int
    name: Optional[str] = None
    
    def __post_init__(self):
        # Validate hex string
        if not all(c in '0123456789abcdefABCDEF' for c in self.hex_data):
            raise ValueError(f"Invalid hex string: {self.hex_data}")
        self.hex_data = self.hex_data.lower()

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

class RFIDAnalyzer:
    """Streamlined RFID card analyzer with multi-card support"""
    
    def __init__(self, min_bits: int = 32, max_bits: int = 35, known_fc: Optional[int] = None):
        self.min_bits = min_bits
        self.max_bits = max_bits
        self.known_fc = known_fc
        self.cards: List[CardData] = []
        self._card_counter = 0
        
    def add_card(self, hex_data: str, known_cn: int, name: Optional[str] = None):
        """Add a card to analyze"""
        if name is None:
            self._card_counter += 1
            name = f"Card_{self._card_counter:03d}"
        
        card = CardData(hex_data, known_cn, name)
        self.cards.append(card)
        return self
    
    def add_cards(self, cards: List[Dict]):
        """Add multiple cards from a list of dictionaries"""
        for card_info in cards:
            self.add_card(
                card_info['hex_data'],
                card_info['known_cn'],
                card_info.get('name')
            )
        return self
    
    @staticmethod
    def hex_to_binary(hex_str: str) -> str:
        """Convert hex to binary string, padded to full byte length"""
        return bin(int(hex_str, 16))[2:].zfill(len(hex_str) * 4)
    
    @staticmethod
    def binary_to_decimal(bin_str: str) -> int:
        """Convert binary string to decimal"""
        return int(bin_str, 2)
    
    def find_matches_single_card(self, card: CardData, target_fc: Optional[int] = None) -> List[Match]:
        """Find all possible FC/CN combinations for a single card"""
        # Use known FC if provided, otherwise use target_fc parameter
        search_fc = self.known_fc if self.known_fc is not None else target_fc
        
        raw_bits = self.hex_to_binary(card.hex_data)
        stream_len = len(raw_bits)
        matches = []
        
        # Try both bit orders (normal and reversed)
        for reverse in [False, True]:
            bitstream = raw_bits[::-1] if reverse else raw_bits
            
            # Try different window sizes
            for window_len in range(self.min_bits, min(self.max_bits + 1, stream_len + 1)):
                # Try different window positions
                for offset in range(stream_len - window_len + 1):
                    window = bitstream[offset:offset + window_len]
                    
                    # Try all possible FC positions and lengths
                    for fc_start in range(window_len):
                        for fc_len in range(1, window_len - fc_start):
                            fc_bits = window[fc_start:fc_start + fc_len]
                            fc_val = self.binary_to_decimal(fc_bits)
                            
                            # Skip if we have a target FC and this doesn't match
                            if search_fc is not None and fc_val != search_fc:
                                continue
                            
                            # Try all possible CN positions and lengths
                            for cn_start in range(window_len):
                                for cn_len in range(1, window_len - cn_start):
                                    # Skip overlapping regions
                                    if self._regions_overlap(fc_start, fc_len, cn_start, cn_len):
                                        continue
                                    
                                    cn_bits = window[cn_start:cn_start + cn_len]
                                    cn_val = self.binary_to_decimal(cn_bits)
                                    
                                    # Check if CN matches the known value
                                    if cn_val == card.known_cn:
                                        matches.append(Match(
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
                                            card_name=card.name
                                        ))
        
        return matches
    
    @staticmethod
    def _regions_overlap(start1: int, len1: int, start2: int, len2: int) -> bool:
        """Check if two regions overlap"""
        end1 = start1 + len1
        end2 = start2 + len2
        return start1 < end2 and start2 < end1
    
    def find_common_fc(self) -> Dict[int, List[Match]]:
        """
        Find FC values that work across all cards.
        Returns dict mapping FC values to lists of matches.
        """
        if not self.cards:
            return {}
        
        # If we have a known FC, only search for that
        if self.known_fc is not None:
            matches = []
            for card in self.cards:
                card_matches = self.find_matches_single_card(card)
                matches.extend(card_matches)
            return {self.known_fc: matches} if matches else {}
        
        # Find all possible matches for each card
        all_matches = {}
        fc_counts = Counter()
        
        for card in self.cards:
            card_matches = self.find_matches_single_card(card)
            all_matches[card.name or card.hex_data] = card_matches
            
            # Count how many cards each FC appears in
            unique_fcs_for_card = set()
            for match in card_matches:
                unique_fcs_for_card.add(match.fc_value)
            
            # Only count each FC once per card (avoid double counting)
            for fc in unique_fcs_for_card:
                fc_counts[fc] += 1
        
        # Find FCs that appear in ALL cards (this is the key constraint)
        num_cards = len(self.cards)
        common_fcs = {fc: count for fc, count in fc_counts.items() if count == num_cards}
        
        # Group matches by FC value
        fc_matches = defaultdict(list)
        for card_name, matches in all_matches.items():
            for match in matches:
                if match.fc_value in common_fcs:
                    fc_matches[match.fc_value].append(match)
        
        return dict(fc_matches)
    
    def get_best_fc_candidates(self, max_candidates: int = 5) -> List[Tuple[int, List[Match]]]:
        """
        Get the most likely FC candidates based on consistency across cards.
        Returns sorted list of (fc_value, matches) tuples.
        """
        common_fcs = self.find_common_fc()
        
        # If we have a known FC, just return it
        if self.known_fc is not None:
            if self.known_fc in common_fcs:
                return [(self.known_fc, common_fcs[self.known_fc])]
            else:
                return []
        
        # Score each FC based on how consistently it appears
        scored_fcs = []
        for fc_value, matches in common_fcs.items():
            # Group matches by card
            cards_with_fc = defaultdict(list)
            for match in matches:
                card_key = match.card_name or "unnamed"
                cards_with_fc[card_key].append(match)
            
            # Score based on number of cards and consistency of parameters
            score = len(cards_with_fc)
            
            # Bonus for consistent bit patterns
            if len(cards_with_fc) > 1:
                # Check if window length is consistent
                window_lengths = [match.window_length for match in matches]
                if len(set(window_lengths)) == 1:
                    score += 0.5
                
                # Check if FC bit length is consistent
                fc_lengths = [match.fc_length for match in matches]
                if len(set(fc_lengths)) == 1:
                    score += 0.5
            
            scored_fcs.append((score, fc_value, matches))
        
        # Sort by score (descending) and return top candidates
        scored_fcs.sort(reverse=True)
        return [(fc_val, matches) for _, fc_val, matches in scored_fcs[:max_candidates]]
    
    def _get_candidate_summary(self, fc_value: int, matches: List[Match]) -> str:
        """Generate a one-line summary for a candidate"""
        # Group matches by card
        cards_with_matches = defaultdict(list)
        for match in matches:
            card_key = match.card_name or "unnamed"
            cards_with_matches[card_key].append(match)
        
        total_matches = len(matches)
        num_cards = len(cards_with_matches)
        
        # Get most common window length and FC bit length for summary
        window_lengths = [match.window_length for match in matches]
        fc_lengths = [match.fc_length for match in matches]
        
        common_window = max(set(window_lengths), key=window_lengths.count)
        common_fc_bits = max(set(fc_lengths), key=fc_lengths.count)
        
        # Calculate confidence based on consistency
        window_consistency = window_lengths.count(common_window) / len(window_lengths)
        fc_consistency = fc_lengths.count(common_fc_bits) / len(fc_lengths)
        
        consistency_score = (window_consistency + fc_consistency) / 2
        if consistency_score > 0.8:
            confidence = f"{Colors.GREEN}HIGH{Colors.RESET}"
        elif consistency_score > 0.6:
            confidence = f"{Colors.YELLOW}MED{Colors.RESET}"
        else:
            confidence = f"{Colors.RED}LOW{Colors.RESET}"
        
        return (f"FC {Colors.BOLD}{fc_value}{Colors.RESET} | "
                f"{Colors.CYAN}{total_matches}{Colors.RESET} matches | "
                f"{Colors.BLUE}{num_cards}{Colors.RESET} cards | "
                f"{common_window}bit/{common_fc_bits}fcb | "
                f"Conf: {confidence}")
    
    def _print_detailed_candidate(self, fc_value: int, matches: List[Match], verbose: bool = False):
        """Print detailed information about a specific candidate"""
        print(f"\n{Colors.BOLD}{Colors.GREEN}📊 Detailed Analysis for FC {fc_value}{Colors.RESET}")
        print(f"{Colors.CYAN}{'='*60}{Colors.RESET}")
        
        # Group matches by card
        cards_with_matches = defaultdict(list)
        for match in matches:
            card_key = match.card_name or "unnamed"
            cards_with_matches[card_key].append(match)
        
        # Show statistics
        total_matches = sum(len(card_matches) for card_matches in cards_with_matches.values())
        print(f"📈 Total matches: {Colors.BOLD}{total_matches}{Colors.RESET} across {Colors.BOLD}{len(cards_with_matches)}{Colors.RESET} cards")
        
        for card_name, card_matches in cards_with_matches.items():
            print(f"\n{Colors.YELLOW}📱 {card_name}{Colors.RESET}: {len(card_matches)} matches")
            display_count = len(card_matches) if verbose else min(3, len(card_matches))
            
            for i, match in enumerate(card_matches[:display_count]):
                prefix = "  ├─" if i < display_count - 1 else "  └─"
                print(f"{prefix} {Colors.MAGENTA}{match.window_length}bit{Colors.RESET} window, "
                      f"FC: {Colors.BOLD}{match.fc_bits}{Colors.RESET}({match.fc_length}b), "
                      f"CN: {Colors.BOLD}{match.cn_bits}{Colors.RESET}({match.cn_length}b), "
                      f"Rev: {Colors.CYAN}{match.reverse}{Colors.RESET}")
            
            if not verbose and len(card_matches) > 3:
                print(f"     {Colors.YELLOW}... +{len(card_matches) - 3} more{Colors.RESET}")
    
    def _interactive_candidate_selection(self, candidates: List[Tuple[int, List[Match]]], verbose: bool = False):
        """Interactive selection of candidates for detailed view"""
        if not candidates:
            return
        
        print(f"\n{Colors.BOLD}{Colors.BLUE}🔍 Found {len(candidates)} FC candidates:{Colors.RESET}")
        print(f"{Colors.CYAN}{'─'*60}{Colors.RESET}")
        
        # Print candidate list with numbers
        for i, (fc_value, matches) in enumerate(candidates, 1):
            summary = self._get_candidate_summary(fc_value, matches)
            print(f"{Colors.BOLD}[{i}]{Colors.RESET} {summary}")
        
        # Interactive selection loop
        while True:
            try:
                print(f"\n{Colors.YELLOW}💡 Options:{Colors.RESET}")
                print(f"  • Enter number (1-{len(candidates)}) to view details")
                print(f"  • Enter '{Colors.GREEN}a{Colors.RESET}' or '{Colors.GREEN}all{Colors.RESET}' to show all candidates")
                print(f"  • Enter '{Colors.RED}q{Colors.RESET}' or '{Colors.RED}quit{Colors.RESET}' to exit")
                
                choice = input(f"\n{Colors.BOLD}Select option: {Colors.RESET}").strip().lower()
                
                if choice in ['q', 'quit', 'exit']:
                    print(f"{Colors.YELLOW}👋 Goodbye!{Colors.RESET}")
                    break
                elif choice in ['a', 'all']:
                    # Show all candidates in detail
                    for fc_value, matches in candidates:
                        self._print_detailed_candidate(fc_value, matches, verbose)
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(candidates):
                        fc_value, matches = candidates[idx]
                        self._print_detailed_candidate(fc_value, matches, verbose)
                        
                        # Ask if they want to see more details
                        if not verbose:
                            more = input(f"\n{Colors.YELLOW}Show all matches? (y/n): {Colors.RESET}").strip().lower()
                            if more in ['y', 'yes']:
                                self._print_detailed_candidate(fc_value, matches, verbose=True)
                    else:
                        print(f"{Colors.RED}❌ Invalid selection. Please enter 1-{len(candidates)}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}❌ Invalid input. Please try again.{Colors.RESET}")
                
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}👋 Goodbye!{Colors.RESET}")
                break
            except EOFError:
                print(f"\n{Colors.YELLOW}👋 Goodbye!{Colors.RESET}")
                break
    
    def print_results(self, max_candidates: int = 5, verbose: bool = False, interactive: bool = True):
        """Print analysis results in a nice format"""
        if not self.cards:
            print(f"{Colors.RED}❌ No cards added for analysis{Colors.RESET}")
            return
        
        print(f"{Colors.BOLD}{Colors.GREEN}🔍 Analyzing {len(self.cards)} cards...{Colors.RESET}")
        if len(self.cards) > 1:
            print(f"{Colors.CYAN}🎯 Assuming all cards share the same FC (common system){Colors.RESET}")
        
        if self.known_fc is not None:
            print(f"{Colors.YELLOW}🔒 Searching for known FC: {self.known_fc}{Colors.RESET}")
        
        print(f"\n{Colors.BOLD}📊 Card data:{Colors.RESET}")
        for card in self.cards:
            print(f"  {Colors.CYAN}{card.name}{Colors.RESET}: {Colors.BOLD}{card.hex_data.upper()}{Colors.RESET} (CN: {Colors.MAGENTA}{card.known_cn}{Colors.RESET})")
        
        print(f"\n{Colors.BOLD}🔍 Search parameters:{Colors.RESET}")
        print(f"  Bit range: {Colors.CYAN}{self.min_bits}-{self.max_bits}{Colors.RESET}")
        print(f"  Known FC: {Colors.CYAN}{self.known_fc or 'None - searching all'}{Colors.RESET}")
        if len(self.cards) > 1:
            print(f"  Constraint: FC must work for ALL {Colors.BOLD}{len(self.cards)}{Colors.RESET} cards")
        
        candidates = self.get_best_fc_candidates(max_candidates)
        
        if not candidates:
            if self.known_fc is not None:
                print(f"{Colors.RED}❌ No matches found for FC {self.known_fc}{Colors.RESET}")
            else:
                print(f"{Colors.RED}❌ No common FC values found across all cards{Colors.RESET}")
                print(f"{Colors.YELLOW}💡 Try:{Colors.RESET}")
                print(f"   - Adjusting bit range with --min-bits/--max-bits")
                print(f"   - Checking if cards are from the same system")
                print(f"   - Verifying hex data and card numbers")
            return
        
        # Show the power of multiple cards
        if len(self.cards) > 1 and self.known_fc is None:
            print(f"{Colors.GREEN}✅ Multi-card analysis found {len(candidates)} FC candidate(s){Colors.RESET}")
            print(f"{Colors.BOLD}🎉 {len(self.cards)} cards reduced possibilities significantly!{Colors.RESET}")
        elif self.known_fc is not None:
            print(f"{Colors.GREEN}✅ Confirmed FC {self.known_fc} works for all cards{Colors.RESET}")
        else:
            print(f"{Colors.GREEN}✅ Found {len(candidates)} FC candidate(s){Colors.RESET}")
        
        # For single card or when we have a known FC, show details immediately
        if len(self.cards) == 1 or self.known_fc is not None or not interactive:
            for rank, (fc_value, matches) in enumerate(candidates, 1):
                if self.known_fc is None and len(candidates) > 1:
                    print(f"\n{Colors.BOLD}🏆 Candidate #{rank}: FC = {fc_value}{Colors.RESET}")
                    # Show confidence based on number of cards
                    confidence = "HIGH" if len(self.cards) >= 3 else "MEDIUM" if len(self.cards) >= 2 else "LOW"
                    print(f"  Confidence: {Colors.GREEN if confidence == 'HIGH' else Colors.YELLOW if confidence == 'MEDIUM' else Colors.RED}{confidence}{Colors.RESET} ({len(self.cards)} cards analyzed)")
                else:
                    print(f"\n{Colors.BOLD}🎯 FC = {fc_value}{Colors.RESET}")
                
                self._print_detailed_candidate(fc_value, matches, verbose)
                
                if len(candidates) > 1 and rank < len(candidates):
                    print()
        else:
            # Multi-card interactive mode
            self._interactive_candidate_selection(candidates, verbose)
        
        # Give helpful next steps
        if len(candidates) == 1:
            fc_value = candidates[0][0]
            print(f"\n{Colors.BOLD}{Colors.GREEN}🎉 SUCCESS! Most likely FC is: {fc_value}{Colors.RESET}")
            if len(self.cards) >= 2:
                print(f"{Colors.GREEN}✅ Confirmed by {len(self.cards)} cards - high confidence!{Colors.RESET}")
        elif len(candidates) > 1 and len(self.cards) > 1:
            print(f"\n{Colors.YELLOW}💡 Next steps:{Colors.RESET}")
            print(f"   - Add more cards from the same system to narrow down")
            print(f"   - Try the top candidate FC: {Colors.BOLD}{candidates[0][0]}{Colors.RESET}")
            print(f"   - Use --known-fc {candidates[0][0]} to verify")

def load_cards_from_file(filename: str) -> List[Dict]:
    """Load cards from JSON file"""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Support both array of cards and single card
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            raise ValueError("File must contain a JSON array or object")
    except Exception as e:
        print(f"{Colors.RED}Error loading file {filename}: {e}{Colors.RESET}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Analyze RFID/HID card data to find facility codes and card numbers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single card analysis (shows all possible FCs)
  python rfid_analyzer.py -c 27bafc0864 32443
  
  # Multiple cards from same system (finds common FC - much more accurate!)
  python rfid_analyzer.py -c 27bafc0864 32443 "Card A" -c 1a2b3c4d5e 12345 "Card B"
  
  # Three cards = high confidence results
  python rfid_analyzer.py -c 27bafc0864 32443 -c 1a2b3c4d5e 12345 -c fedcba9876 54321
  
  # Verify suspected facility code across all cards
  python rfid_analyzer.py --known-fc 2436 -c 27bafc0864 32443 -c 1a2b3c4d5e 12345
  
  # Load batch of cards from same system
  python rfid_analyzer.py --file cards.json
  
  # Custom bit range for different card formats
  python rfid_analyzer.py --min-bits 30 --max-bits 40 -c 27bafc0864 32443
  
  # Non-interactive mode (show all details immediately)
  python rfid_analyzer.py --no-interactive -c 27bafc0864 32443 -c 1a2b3c4d5e 12345
  
JSON file format:
  [
    {"hex_data": "27bafc0864", "known_cn": 32443, "name": "Card A"},
    {"hex_data": "1a2b3c4d5e", "known_cn": 12345, "name": "Card B"}
  ]
        """)
    
    parser.add_argument('-c', '--card', nargs='+', action='append', 
                        metavar='HEX_DATA KNOWN_CN [NAME]',
                        help='Add a card: HEX_DATA KNOWN_CN [NAME]')
    parser.add_argument('-f', '--file', type=str,
                        help='Load cards from JSON file')
    parser.add_argument('--known-fc', type=int,
                        help='Known facility code to search for')
    parser.add_argument('--min-bits', type=int, default=32,
                        help='Minimum bit window size (default: 32)')
    parser.add_argument('--max-bits', type=int, default=35,
                        help='Maximum bit window size (default: 35)')
    parser.add_argument('--max-candidates', type=int, default=5,
                        help='Maximum FC candidates to show (default: 5)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show all matches (not just top 3 per card)')
    parser.add_argument('--no-interactive', action='store_true',
                        help='Disable interactive mode (show all details immediately)')
    parser.add_argument('--no-color', action='store_true',
                        help='Disable colored output')
    
    args = parser.parse_args()
    
    # Disable colors if requested or if not outputting to terminal
    if args.no_color or not sys.stdout.isatty():
        Colors.disable()
    
    # Validate arguments
    if not args.card and not args.file:
        print(f"{Colors.RED}❌ Error: Must specify either --card or --file{Colors.RESET}")
        parser.print_help()
        sys.exit(1)
    
    if args.min_bits >= args.max_bits:
        print(f"{Colors.RED}❌ Error: min-bits must be less than max-bits{Colors.RESET}")
        sys.exit(1)
    
    try:
        # Create analyzer
        analyzer = RFIDAnalyzer(
            min_bits=args.min_bits,
            max_bits=args.max_bits,
            known_fc=args.known_fc
        )
        
        # Add cards from file
        if args.file:
            cards_data = load_cards_from_file(args.file)
            analyzer.add_cards(cards_data)
        
        # Add cards from command line
        if args.card:
            for card_args in args.card:
                if len(card_args) < 2:
                    print(f"{Colors.RED}❌ Error: Card requires at least HEX_DATA and KNOWN_CN{Colors.RESET}")
                    sys.exit(1)
                
                hex_data = card_args[0]
                try:
                    known_cn = int(card_args[1])
                except ValueError:
                    print(f"{Colors.RED}❌ Error: KNOWN_CN must be an integer, got: {card_args[1]}{Colors.RESET}")
                    sys.exit(1)
                
                name = card_args[2] if len(card_args) > 2 else None
                analyzer.add_card(hex_data, known_cn, name)
        
        # Print results
        analyzer.print_results(
            max_candidates=args.max_candidates,
            verbose=args.verbose,
            interactive=not args.no_interactive
        )
        
    except ValueError as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Analysis interrupted by user{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
