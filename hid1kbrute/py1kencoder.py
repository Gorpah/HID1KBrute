#!/usr/bin/env python3
"""
RFID Badge Designer - Generate hex data from FC/CN patterns
Enhanced version with hex padding support and streamlined interface
"""

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


class Colors:
    """ANSI color codes for terminal output"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"

    @classmethod
    def disable(cls):
        """Disable all colors for non-TTY output"""
        for attr in ["RESET", "BOLD", "RED", "GREEN", "YELLOW", "BLUE", "CYAN"]:
            setattr(cls, attr, "")


@dataclass
class CardPattern:
    """Represents a card encoding pattern"""
    name: str
    total_bits: int
    window_offset: int
    fc_start: int
    fc_length: int
    cn_start: int
    cn_length: int
    issue_start: int = 0
    issue_length: int = 0
    extended_start: int = 0
    extended_length: int = 0
    reversed: bool = False

    @property
    def padding_bits(self) -> int:
        """Calculate padding bits for hex alignment"""
        used_bits = max(self.window_offset + self.total_bits, self.total_bits)
        return ((used_bits + 3) // 4) * 4


@dataclass
class Badge:
    """Represents a generated badge"""
    fc: int
    cn: int
    issue_code: int
    extended_id: int
    hex_data: str
    pattern_name: str
    fc_bits: str
    cn_bits: str
    issue_bits: str
    extended_bits: str
    raw_hex: str = ""


class BadgeDesigner:
    """Enhanced RFID badge designer with proper padding support"""

    def __init__(self, patterns_file: str = "hid_patterns.json"):
        self.patterns: Dict[str, CardPattern] = {}
        self.hex_padding = 0
        self.load_patterns(patterns_file)

    def set_hex_padding(self, hex_digits: int):
        """Set the number of hex digits to pad to"""
        self.hex_padding = max(0, hex_digits)

    def load_patterns(self, patterns_file: str):
        """Load patterns from JSON file and add built-in patterns"""
        # Try to load HID patterns
        try:
            with open(patterns_file, "r") as f:
                data = json.load(f)
            
            for fmt in data["formats"]:
                pattern = CardPattern(
                    name=f"HID {fmt['name']}",
                    total_bits=fmt["total_bits"],
                    window_offset=0,
                    fc_start=fmt["fc_position"] - 1,
                    fc_length=fmt["fc_bits"],
                    cn_start=fmt["cn_position"] - 1,
                    cn_length=fmt["cn_bits"],
                    issue_start=fmt.get("issue_position", 1) - 1 if fmt.get("issue_position") else 0,
                    issue_length=fmt.get("issue_bits", 0),
                    extended_start=fmt.get("extended_position", 1) - 1 if fmt.get("extended_position") else 0,
                    extended_length=fmt.get("extended_bits", 0),
                    reversed=False,
                )
                
                short_name = fmt["name"].lower().replace(" ", "_").replace("(", "").replace(")", "")
                self.patterns[short_name] = pattern
        
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"{Colors.YELLOW}⚠️  HID patterns file issue: {e}{Colors.RESET}")
        
        # Add built-in patterns
        builtin = {
            "hid_26bit": CardPattern(
                name="HID 26-bit Standard",
                total_bits=26,
                window_offset=0,
                fc_start=1,
                fc_length=8,
                cn_start=9,
                cn_length=16,
            ),
            "hid_34bit": CardPattern(
                name="HID 34-bit iCLASS",
                total_bits=34,
                window_offset=0,
                fc_start=1,
                fc_length=10,
                cn_start=11,
                cn_length=20,
            ),
            "hid_35bit": CardPattern(
                name="HID 35-bit Corporate",
                total_bits=35,
                window_offset=0,
                fc_start=1,
                fc_length=12,
                cn_start=13,
                cn_length=20,
            ),
        }
        
        self.patterns.update(builtin)

    def validate_values(self, fc: int, cn: int, issue_code: int, extended_id: int, pattern: CardPattern) -> bool:
        """Validate all values against pattern constraints"""
        checks = [
            (fc, pattern.fc_length, "FC"),
            (cn, pattern.cn_length, "CN"),
        ]
        
        if pattern.issue_length > 0:
            checks.append((issue_code, pattern.issue_length, "Issue"))
        if pattern.extended_length > 0:
            checks.append((extended_id, pattern.extended_length, "Extended"))
        
        for value, bits, name in checks:
            max_val = (1 << bits) - 1
            if not (0 <= value <= max_val):
                print(f"{Colors.RED}❌ {name} {value} out of range (0-{max_val}){Colors.RESET}")
                return False
        
        return True

    def create_badge(self, fc: int, cn: int, pattern: CardPattern, issue_code: int = 0, extended_id: int = 0) -> Optional[Badge]:
        """Create a badge with the given values using the specified pattern"""
        if not self.validate_values(fc, cn, issue_code, extended_id, pattern):
            return None

        # Convert to binary strings
        fc_bits = format(fc, f"0{pattern.fc_length}b")
        cn_bits = format(cn, f"0{pattern.cn_length}b")
        issue_bits = format(issue_code, f"0{pattern.issue_length}b") if pattern.issue_length > 0 else ""
        extended_bits = format(extended_id, f"0{pattern.extended_length}b") if pattern.extended_length > 0 else ""

        # Create data window
        data_window = ["0"] * pattern.total_bits

        # Place all bits
        bit_placements = [
            (fc_bits, pattern.fc_start),
            (cn_bits, pattern.cn_start),
        ]
        
        if pattern.issue_length > 0:
            bit_placements.append((issue_bits, pattern.issue_start))
        if pattern.extended_length > 0:
            bit_placements.append((extended_bits, pattern.extended_start))

        for bits, start_pos in bit_placements:
            for i, bit in enumerate(bits):
                if start_pos + i < len(data_window):
                    data_window[start_pos + i] = bit

        data_bits = "".join(data_window)

        # Create full bit string with padding
        full_bits = ["0"] * pattern.padding_bits
        for i, bit in enumerate(data_bits):
            if pattern.window_offset + i < len(full_bits):
                full_bits[pattern.window_offset + i] = bit
        
        if pattern.reversed:
            full_bits = full_bits[::-1]

        # Convert to hex
        bit_string = "".join(full_bits)
        hex_length = len(bit_string) // 4
        raw_hex = format(int(bit_string, 2), f"0{hex_length}X")
        
        # Apply padding - respecting polarity
        if self.hex_padding > len(raw_hex):
            padding_needed = self.hex_padding - len(raw_hex)
            if pattern.reversed:
                # For reversed patterns, pad at the beginning
                padded_hex = "0" * padding_needed + raw_hex
            else:
                # For normal patterns, pad at the end
                padded_hex = raw_hex + "0" * padding_needed
        else:
            padded_hex = raw_hex

        return Badge(
            fc=fc,
            cn=cn,
            issue_code=issue_code,
            extended_id=extended_id,
            hex_data=padded_hex,
            pattern_name=pattern.name,
            fc_bits=fc_bits,
            cn_bits=cn_bits,
            issue_bits=issue_bits,
            extended_bits=extended_bits,
            raw_hex=raw_hex,
        )

    def print_badge(self, badge: Badge, show_binary: bool = False):
        """Print badge information"""
        parts = [f"FC={badge.fc}", f"CN={badge.cn}"]
        
        if badge.issue_code > 0:
            parts.append(f"Issue={badge.issue_code}")
        if badge.extended_id > 0:
            parts.append(f"Extended={badge.extended_id}")
        
        parts.append(f"HEX={badge.hex_data}")
        print(f"    └─ {', '.join(parts)}")

        if badge.raw_hex != badge.hex_data:
            print(f"       Raw: {badge.raw_hex} → Padded: {badge.hex_data}")

        if show_binary:
            binary_parts = [f"FC={badge.fc_bits}", f"CN={badge.cn_bits}"]
            if badge.issue_bits:
                binary_parts.append(f"Issue={badge.issue_bits}")
            if badge.extended_bits:
                binary_parts.append(f"Extended={badge.extended_bits}")
            print(f"       Binary: {', '.join(binary_parts)}")

    def list_patterns(self):
        """List available patterns"""
        print(f"\n{Colors.BOLD}📋 Available Patterns:{Colors.RESET}")
        for name, pattern in sorted(self.patterns.items()):
            print(f"  {Colors.GREEN}{name}{Colors.RESET}: {pattern.name}")
            parts = [f"FC: {pattern.fc_length}b", f"CN: {pattern.cn_length}b"]
            if pattern.issue_length > 0:
                parts.append(f"Issue: {pattern.issue_length}b")
            if pattern.extended_length > 0:
                parts.append(f"Extended: {pattern.extended_length}b")
            if pattern.reversed:
                parts.append("Reversed")
            print(f"    └─ {', '.join(parts)}")

    def _get_int_input(self, prompt: str, default: int = None, min_val: int = 0, max_val: int = None) -> int:
        """Helper to get integer input with validation"""
        while True:
            try:
                default_text = f" (default {default})" if default is not None else ""
                max_text = f"-{max_val}" if max_val else ""
                range_text = f" ({min_val}{max_text})" if max_val else ""
                
                user_input = input(f"{Colors.YELLOW}{prompt}{default_text}{range_text}: {Colors.RESET}")
                
                if not user_input and default is not None:
                    return default
                
                value = int(user_input)
                if value < min_val or (max_val is not None and value > max_val):
                    print(f"{Colors.RED}❌ Value must be between {min_val} and {max_val}{Colors.RESET}")
                    continue
                
                return value
            except ValueError:
                print(f"{Colors.RED}❌ Please enter a valid number{Colors.RESET}")

    def _get_bool_input(self, prompt: str, default: bool = False) -> bool:
        """Helper to get boolean input"""
        default_text = "Y/n" if default else "y/N"
        user_input = input(f"{Colors.YELLOW}{prompt} ({default_text}): {Colors.RESET}").lower()
        
        if not user_input:
            return default
        
        return user_input in ["y", "yes", "1", "true"]

    def _get_range_or_single(self, prompt: str, max_val: int) -> Tuple[int, int]:
        """Get either a single value or range"""
        while True:
            user_input = input(f"{Colors.YELLOW}{prompt} (e.g., 123 or 123-125): {Colors.RESET}")
            
            if "-" in user_input:
                try:
                    start, end = map(int, user_input.split("-"))
                    if 0 <= start <= end <= max_val:
                        return start, end
                    else:
                        print(f"{Colors.RED}❌ Range must be between 0 and {max_val}{Colors.RESET}")
                except ValueError:
                    print(f"{Colors.RED}❌ Invalid range format{Colors.RESET}")
            else:
                try:
                    value = int(user_input)
                    if 0 <= value <= max_val:
                        return value, value
                    else:
                        print(f"{Colors.RED}❌ Value must be between 0 and {max_val}{Colors.RESET}")
                except ValueError:
                    print(f"{Colors.RED}❌ Please enter a valid number{Colors.RESET}")

    def interactive_mode(self):
        """Interactive badge creation mode"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}🎯 Interactive Badge Designer{Colors.RESET}")
        print(f"{Colors.CYAN}{'='*50}{Colors.RESET}")

        while True:
            try:
                print(f"\n{Colors.BOLD}Options:{Colors.RESET}")
                print("1. Create badge with existing pattern")
                print("2. Create badge with custom pattern")
                print("3. List available patterns")
                print("4. Set hex padding")
                print("5. Exit")

                choice = input(f"\n{Colors.YELLOW}Select option (1-5): {Colors.RESET}").strip()

                if choice == "1":
                    self._interactive_existing_pattern()
                elif choice == "2":
                    self._interactive_custom_pattern()
                elif choice == "3":
                    self.list_patterns()
                elif choice == "4":
                    self._set_padding()
                elif choice == "5":
                    print(f"{Colors.GREEN}👋 Goodbye!{Colors.RESET}")
                    break
                else:
                    print(f"{Colors.RED}❌ Invalid option{Colors.RESET}")

            except KeyboardInterrupt:
                print(f"\n{Colors.GREEN}👋 Goodbye!{Colors.RESET}")
                break
            except Exception as e:
                print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")

    def _set_padding(self):
        """Set hex padding in interactive mode"""
        current = f" (current: {self.hex_padding})" if self.hex_padding > 0 else ""
        padding = self._get_int_input(f"Enter hex digits to pad to{current}", self.hex_padding)
        self.set_hex_padding(padding)
        print(f"{Colors.GREEN}✅ Padding set to {self.hex_padding} hex digits{Colors.RESET}")

    def _interactive_existing_pattern(self):
        """Interactive mode for existing patterns"""
        print(f"\n{Colors.BOLD}Available patterns:{Colors.RESET}")
        pattern_names = list(self.patterns.keys())
        
        for i, name in enumerate(pattern_names, 1):
            print(f"{i}. {name}")

        choice = self._get_int_input(f"Select pattern", min_val=1, max_val=len(pattern_names))
        pattern_name = pattern_names[choice - 1]
        pattern = self.patterns[pattern_name]

        print(f"\n{Colors.BOLD}Pattern: {pattern.name}{Colors.RESET}")
        print(f"  FC: {pattern.fc_length} bits, CN: {pattern.cn_length} bits")
        if pattern.reversed:
            print(f"  {Colors.YELLOW}⚠️  Reversed bit order{Colors.RESET}")

        # Get inputs
        fc = self._get_int_input("Enter FC", max_val=(1 << pattern.fc_length) - 1)
        
        issue_code = 0
        if pattern.issue_length > 0:
            issue_code = self._get_int_input("Enter Issue Code", 0, max_val=(1 << pattern.issue_length) - 1)
        
        extended_id = 0
        if pattern.extended_length > 0:
            extended_id = self._get_int_input("Enter Extended ID", 0, max_val=(1 << pattern.extended_length) - 1)
        
        # Get CN range
        cn_start, cn_end = self._get_range_or_single("Enter CN", (1 << pattern.cn_length) - 1)

        # Generate badges
        if cn_start == cn_end:
            badge = self.create_badge(fc, cn_start, pattern, issue_code, extended_id)
            if badge:
                print(f"\n{Colors.GREEN}✅ Generated badge:{Colors.RESET}")
                self.print_badge(badge)
        else:
            print(f"\n{Colors.GREEN}✅ Generated {cn_end - cn_start + 1} badges:{Colors.RESET}")
            for cn in range(cn_start, cn_end + 1):
                badge = self.create_badge(fc, cn, pattern, issue_code, extended_id)
                if badge:
                    print(f"    └─ CN_{cn}: {badge.hex_data}")

    def _interactive_custom_pattern(self):
        """Interactive mode for custom patterns"""
        print(f"\n{Colors.BOLD}🛠️  Custom Pattern Builder{Colors.RESET}")

        # Pattern definition
        name = input(f"{Colors.YELLOW}Pattern name: {Colors.RESET}") or "Custom Pattern"
        total_bits = self._get_int_input("Total bits", min_val=1)
        window_offset = self._get_int_input("Window offset", 0)
        
        # Field definitions
        fc_start = self._get_int_input("FC start position")
        fc_length = self._get_int_input("FC length (bits)", min_val=1)
        cn_start = self._get_int_input("CN start position")
        cn_length = self._get_int_input("CN length (bits)", min_val=1)
        
        # Optional fields
        issue_start = self._get_int_input("Issue start position (0 to skip)", 0)
        issue_length = self._get_int_input("Issue length in bits (0 to skip)", 0) if issue_start > 0 else 0
        extended_start = self._get_int_input("Extended start position (0 to skip)", 0)
        extended_length = self._get_int_input("Extended length in bits (0 to skip)", 0) if extended_start > 0 else 0
        
        # Pattern options
        reversed = self._get_bool_input("Reversed bit order?", False)
        
        # Hex padding option
        set_padding = self._get_bool_input("Set hex padding for this pattern?", False)
        if set_padding:
            padding = self._get_int_input("Hex digits to pad to", self.hex_padding)
            self.set_hex_padding(padding)
            print(f"{Colors.GREEN}✅ Padding set to {self.hex_padding} hex digits{Colors.RESET}")

        # Create pattern
        pattern = CardPattern(
            name=name,
            total_bits=total_bits,
            window_offset=window_offset,
            fc_start=fc_start,
            fc_length=fc_length,
            cn_start=cn_start,
            cn_length=cn_length,
            issue_start=issue_start,
            issue_length=issue_length,
            extended_start=extended_start,
            extended_length=extended_length,
            reversed=reversed,
        )

        print(f"\n{Colors.BOLD}Pattern created - generating test badge:{Colors.RESET}")
        
        # Get test values
        fc = self._get_int_input("Enter FC", max_val=(1 << pattern.fc_length) - 1)
        cn = self._get_int_input("Enter CN", max_val=(1 << pattern.cn_length) - 1)
        
        issue_code = 0
        if pattern.issue_length > 0:
            issue_code = self._get_int_input("Enter Issue Code", 0, max_val=(1 << pattern.issue_length) - 1)
        
        extended_id = 0
        if pattern.extended_length > 0:
            extended_id = self._get_int_input("Enter Extended ID", 0, max_val=(1 << pattern.extended_length) - 1)

        # Generate test badge
        badge = self.create_badge(fc, cn, pattern, issue_code, extended_id)
        if badge:
            print(f"\n{Colors.GREEN}✅ Generated badge:{Colors.RESET}")
            self.print_badge(badge, show_binary=True)


def main():
    parser = argparse.ArgumentParser(description="RFID Badge Designer")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--fc", type=int, help="Facility code")
    parser.add_argument("--cn", type=int, help="Card number")
    parser.add_argument("--issue", type=int, default=0, help="Issue code")
    parser.add_argument("--extended", type=int, default=0, help="Extended ID")
    parser.add_argument("--cn-range", nargs=2, type=int, metavar=("START", "END"), help="CN range")
    parser.add_argument("--pattern", help="Pattern name")
    parser.add_argument("--list-patterns", action="store_true", help="List patterns")
    parser.add_argument("--patterns-file", default="hid_patterns.json", help="Patterns file")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    parser.add_argument("--show-binary", action="store_true", help="Show binary")
    parser.add_argument("--hex-padding", type=int, default=0, help="Hex digits to pad to")

    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    designer = BadgeDesigner(args.patterns_file)
    
    if args.hex_padding > 0:
        designer.set_hex_padding(args.hex_padding)

    if args.interactive:
        designer.interactive_mode()
        return

    if args.list_patterns:
        designer.list_patterns()
        return

    if args.pattern and args.fc is not None:
        if args.pattern not in designer.patterns:
            print(f"{Colors.RED}❌ Unknown pattern: {args.pattern}{Colors.RESET}")
            designer.list_patterns()
            return

        pattern = designer.patterns[args.pattern]

        if args.cn_range:
            print(f"\n{Colors.GREEN}✅ Generated badges:{Colors.RESET}")
            for cn in range(args.cn_range[0], args.cn_range[1] + 1):
                badge = designer.create_badge(args.fc, cn, pattern, args.issue, args.extended)
                if badge:
                    print(f"    └─ CN_{cn}: {badge.hex_data}")
        elif args.cn is not None:
            badge = designer.create_badge(args.fc, args.cn, pattern, args.issue, args.extended)
            if badge:
                print(f"\n{Colors.GREEN}✅ Generated badge:{Colors.RESET}")
                designer.print_badge(badge, args.show_binary)
        else:
            print(f"{Colors.RED}❌ Must specify --cn or --cn-range{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}💡 Use --interactive or -i for interactive mode{Colors.RESET}")
        print(f"{Colors.YELLOW}💡 Use --list-patterns to see available patterns{Colors.RESET}")


if __name__ == "__main__":
    main()
