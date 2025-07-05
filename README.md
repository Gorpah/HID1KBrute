# HID1KBrute

# 🔍 RFID Card Analyzer

**Ever wondered what's hidden in your RFID/HID card's hex data?** This tool cracks the code and reveals the facility codes and card numbers buried in the binary bits.

## 🎯 What Does It Do?

Got a stack of RFID cards with their hex dumps and card numbers? This analyzer:
- **Reverse engineers** facility codes from raw hex data
- **Finds patterns** across multiple cards to validate results
- **Matches against** known HID card formats for extra confidence
- **Shows you exactly** where the FC and CN bits are located

Perfect for penetration testers, security researchers, or anyone curious about how their access cards work under the hood.

## 🚀 Quick Start

```bash
# Single card analysis
python main.py -c 27bafc0864 32443

# Multiple cards (more reliable)
python main.py -c 27bafc0864 32443 -c 1a2b3c4d5e 12345

# If you already know the facility code
python main.py --known-fc 2436 -c 27bafc0864 32443

# Load from JSON file
python main.py --file cards.json
```

## 📊 Example Output

```
🔍 Analyzing 2 cards...

📊 Cards:
  Card_001: 27BAFC0864 (CN: 32443)
  Card_002: 1A2B3C4D5E (CN: 12345)

✅ Found 1 FC candidate(s)

📊 FC 2436 - All Permutations
═══════════════════════════════════════════════════════════
📊 Summary: 2 matches, 2 cards, 1 patterns
🎯 Matched Format: HID H10301 (26-bit) (+50 confidence)

🔍 Pattern #1:
  📐 Window: 26 bits at offset 8
  🎯 FC: 8 bits at pos 1
  🎯 CN: 16 bits at pos 9
  🔄 Reversed: False
  📱 Cards: 2
    └─ Card_001: FC=10011000, CN=0111111010101011
    └─ Card_002: FC=10011000, CN=0011000000111001

🎉 Most likely FC: 2436
```

## 💾 Input Formats

### Command Line
```bash
# Format: HEX_DATA KNOWN_CN [OPTIONAL_NAME]
python main.py -c 27bafc0864 32443 "Bob's Card"
```

### JSON File
```json
[
  {
    "hex_data": "27bafc0864",
    "known_cn": 32443,
    "name": "Bob's Card"
  },
  {
    "hex_data": "1a2b3c4d5e",
    "known_cn": 12345,
    "name": "Alice's Card"
  }
]
```

## 🔧 Advanced Options

```bash
# Custom bit window sizes
python main.py -c 27bafc0864 32443 --min-bits 24 --max-bits 37

# Show more candidates
python main.py -c 27bafc0864 32443 --max-candidates 10

# Skip interactive mode (show all details)
python main.py -c 27bafc0864 32443 --no-interactive

# Disable colors (for piping output)
python main.py -c 27bafc0864 32443 --no-color
```

## 🧠 How It Works

The analyzer uses a brute-force approach with intelligence:

1. **Bit Window Scanning**: Tries different bit window sizes (default 32-35 bits)
2. **Pattern Testing**: Tests every possible FC/CN position combination
3. **Multi-Card Validation**: Confirms patterns work across ALL provided cards
4. **Format Matching**: Compares against known HID card formats for confidence boost
5. **Scoring**: Ranks candidates by consistency and real-world likelihood

## 🎨 Configuration

### HID Patterns (Optional)
Create `hid_patterns.json` in the same directory for format matching:

```json
{
  "formats": [
    {
      "name": "HID H10301 (26-bit)",
      "total_bits": 26,
      "fc_bits": 8,
      "fc_position": 1,
      "cn_bits": 16,
      "cn_position": 9,
      "confidence_boost": 50
    }
  ],
  "tolerance": {
    "bit_length": 2,
    "position": 3
  }
}
```

## 📝 Pro Tips

### For Best Results:
- **Use multiple cards** from the same facility - single cards give lots of false positives
- **Know your card numbers** - without them, the tool can't work its magic
- **Try different bit windows** if standard ranges don't work
- **Check the pattern details** - sometimes multiple valid interpretations exist

### Common Gotchas:
- Some cards use **reversed bit order** - the tool handles this automatically
- **Endianness matters** - hex might need byte-swapping depending on your reader
- **Padding bits** can shift everything - experiment with different offsets

## 🔬 Understanding the Output

### Confidence Levels:
- **HIGH**: Pattern confirmed across multiple cards
- **KNOWN**: Matches a documented HID format
- **SINGLE**: Only one card available (less reliable)

### Pattern Details:
- **Window**: The bit range being analyzed
- **FC/CN positions**: Where facility code and card number bits are located
- **Reversed**: Whether bits are read in reverse order

## 🛠️ Requirements

- Python 3.6+
- No external dependencies (uses only stdlib)
- Terminal with color support (optional)

## 🤝 Contributing

Found a bug? Have a cool feature idea? PRs welcome! This tool grew out of real pentesting needs, so practical improvements are always appreciated.

## 📄 License

MIT License - hack away! 

## 🔗 Related Tools

This analyzer finds the patterns - stay tuned for the companion **badge_creator.py** that lets you generate new hex data with custom FC/CN values using the discovered patterns.

---

*Built with ❤️ for the security research community*
