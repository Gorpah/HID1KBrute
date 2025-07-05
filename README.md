# HID1KBrute

# RFID Card Analysis Toolkit

A comprehensive Python toolkit for analyzing RFID/HID card data and generating badge patterns. This toolkit consists of two main components: an **RFID Card Analyzer** for discovering facility codes and card number patterns, and a **Badge Designer** for generating hex data from known patterns.

## 🔧 Features

### RFID Card Analyzer (`main.py`)
- **Pattern Discovery**: Automatically discovers facility codes (FC) and card number (CN) patterns from hex data
- **Multiple Card Analysis**: Analyze multiple cards simultaneously to find consistent patterns
- **Real-world Format Detection**: Matches against known HID card formats with confidence scoring
- **Interactive Mode**: Browse and explore discovered patterns interactively
- **Flexible Input**: Support for command-line arguments or JSON file input
- **Comprehensive Output**: Detailed analysis with bit positions, window offsets, and pattern confidence

### Badge Designer (`badge_designer.py`)
- **Pattern-based Generation**: Generate hex data using predefined or custom patterns
- **HID Format Support**: Built-in support for common HID formats (26-bit, 34-bit, 35-bit, etc.)
- **Batch Generation**: Generate multiple badges with sequential card numbers
- **Custom Patterns**: Create and test custom bit patterns
- **Hex Padding**: Configurable hex output padding for different reader requirements
- **Interactive Design**: Step-by-step badge creation with validation

## 📦 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/rfid-toolkit.git
cd rfid-toolkit
```

2. Ensure you have Python 3.6+ installed:
```bash
python3 --version
```

3. No additional dependencies required - uses only Python standard library!

## 🚀 Quick Start

### Analyzing Cards

**Single Card Analysis:**
```bash
python3 main.py -c 27bafc0864 32443
```

**Multiple Cards:**
```bash
python3 main.py -c 27bafc0864 32443 -c 1a2b3c4d5e 12345
```

**With Known Facility Code:**
```bash
python3 main.py --known-fc 2436 -c 27bafc0864 32443
```

### Generating Badges

**Interactive Mode:**
```bash
python3 badge_designer.py -i
```

**Generate Single Badge:**
```bash
python3 badge_designer.py --pattern hid_26bit --fc 123 --cn 45678
```

**Generate Badge Range:**
```bash
python3 badge_designer.py --pattern hid_26bit --fc 123 --cn-range 1000 1010
```

## 📋 Usage Examples

### 1. Discover Facility Code from Unknown Cards

```bash
# Analyze multiple cards to find the facility code
python3 main.py \
  -c 27bafc0864 32443 "Alice's Card" \
  -c 1a2b3c4d5e 12345 "Bob's Card" \
  -c 3f4e5d6c7b 67890 "Charlie's Card"
```

### 2. Load Cards from JSON File

Create a `cards.json` file:
```json
[
  {
    "hex_data": "27bafc0864",
    "known_cn": 32443,
    "name": "Alice's Card"
  },
  {
    "hex_data": "1a2b3c4d5e",
    "known_cn": 12345,
    "name": "Bob's Card"
  }
]
```

Then analyze:
```bash
python3 main.py --file cards.json
```

### 3. Generate Badges for New Employees

```bash
# Generate a range of badges for new employees
python3 badge_designer.py \
  --pattern hid_26bit \
  --fc 2436 \
  --cn-range 50000 50010 \
  --hex-padding 10
```

### 4. Interactive Pattern Discovery

```bash
# Start interactive mode for detailed analysis
python3 main.py -c 27bafc0864 32443 --no-interactive
```

### 5. Custom Pattern Creation

```bash
# Create badges with custom patterns
python3 badge_designer.py -i
# Then select option 2 for custom pattern creation
```

## 🎛️ Command Line Options

### RFID Analyzer (`main.py`)

| Option | Description |
|--------|-------------|
| `-c, --card` | Add card: `HEX_DATA KNOWN_CN [NAME]` |
| `-f, --file` | Load cards from JSON file |
| `--known-fc` | Search for specific facility code |
| `--min-bits` | Minimum bit window (default: 32) |
| `--max-bits` | Maximum bit window (default: 35) |
| `--max-candidates` | Maximum candidates to show (default: 5) |
| `--no-interactive` | Show all details immediately |
| `--no-color` | Disable colored output |

### Badge Designer (`badge_designer.py`)

| Option | Description |
|--------|-------------|
| `-i, --interactive` | Interactive mode |
| `--fc` | Facility code |
| `--cn` | Card number |
| `--cn-range` | Card number range: `START END` |
| `--pattern` | Pattern name |
| `--list-patterns` | List available patterns |
| `--hex-padding` | Hex digits to pad to |
| `--show-binary` | Show binary representation |
| `--no-color` | Disable colored output |

## 📊 Pattern Configuration

### HID Patterns File (`hid_patterns.json`)

The toolkit supports loading HID patterns from a JSON configuration file:

```json
{
  "formats": [
    {
      "name": "26-bit Standard",
      "total_bits": 26,
      "fc_position": 2,
      "fc_bits": 8,
      "cn_position": 10,
      "cn_bits": 16,
      "confidence_boost": 50
    }
  ],
  "tolerance": {
    "bit_length": 2,
    "position": 3
  }
}
```

### Built-in Patterns

The Badge Designer includes these built-in patterns:

- **HID 26-bit Standard**: FC=8bits, CN=16bits
- **HID 34-bit iCLASS**: FC=10bits, CN=20bits  
- **HID 35-bit Corporate**: FC=12bits, CN=20bits

## 🔍 Understanding the Output

### Analyzer Output

When analyzing cards, you'll see:

```
📊 FC 2436 - All Permutations
============================================================
📊 Summary: 3 matches, 3 cards, 1 patterns
🎯 Matched Format: 26-bit Standard (+50 confidence)

🔍 Pattern #1:
  📐 Window: 26 bits at offset 5
  🎯 FC: 8 bits at pos 1
  🎯 CN: 16 bits at pos 9
  🔄 Reversed: False
  📱 Cards: 3
    └─ Alice's Card: FC=10011000, CN=0111111010101011
    └─ Bob's Card: FC=10011000, CN=0011000000111001
    └─ Charlie's Card: FC=10011000, CN=1010010001101010
```

### Badge Designer Output

When generating badges:

```
✅ Generated badge:
    └─ FC=123, CN=45678, HEX=06F2372E0
       Binary: FC=01111011, CN=1011001001001110
```

## 🎨 Interactive Mode

Both tools offer interactive modes for easier use:

- **Analyzer Interactive**: Browse multiple FC candidates, view detailed patterns
- **Designer Interactive**: Step-by-step badge creation with validation

## 🔧 Advanced Features

### Hex Padding

Control output format with padding:
```bash
python3 badge_designer.py --hex-padding 12 --pattern hid_26bit --fc 123 --cn 456
```

### Custom Bit Windows

Analyze specific bit ranges:
```bash
python3 main.py --min-bits 24 --max-bits 40 -c 27bafc0864 32443
```

### Pattern Validation

The toolkit validates:
- Value ranges against bit lengths
- Pattern consistency across multiple cards
- Real-world format matching

## 🛠️ Troubleshooting

### Common Issues

1. **No patterns found**: Try expanding bit window range with `--min-bits` and `--max-bits`
2. **Multiple candidates**: Use `--known-fc` to filter results
3. **Hex padding issues**: Ensure padding value accommodates your data length

### Debug Tips

- Use `--show-binary` to see bit-level representations
- Try `--no-interactive` for full output
- Check that card numbers are correct in input data

## 📈 Use Cases

- **Security Research**: Analyze badge systems and understand encoding
- **Badge Administration**: Generate new badges for existing systems
- **System Migration**: Understand old badge formats for new system setup
- **Penetration Testing**: Generate test badges for security assessments
- **Badge Cloning**: Understand card structure for duplication

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This toolkit is intended for educational, research, and legitimate security testing purposes only. Users are responsible for ensuring compliance with all applicable laws and regulations. The authors assume no responsibility for misuse of this software.

## 🙏 Acknowledgments

- HID Global for their comprehensive card format documentation
- The security research community for RFID/HID analysis techniques
- Contributors and testers who helped improve this toolkit
