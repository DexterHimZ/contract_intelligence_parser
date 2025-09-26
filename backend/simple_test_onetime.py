#!/usr/bin/env python3
"""
Simple test for OneTime_Contract.pdf extraction patterns without dependencies.
Tests the core regex patterns and logic.
"""

import re

# Test data matching OneTime_Contract.pdf format
SAMPLE_CONTRACT_TEXT = """
GreenEnergyCorp OneTime Contract

Party Information:
Client: TechCorp Solutions
Vendor: GreenEnergyCorp

Contract Details:
Description             Quantity  Unit Price  Currency  Total
System Setup           1         5,000.00    U S D     5,000.00
Data Migration          1         3,000.00    USD       3,000.00
Staff Training          2×$1,500  USD         3,000.00

Total Due (One-Time): 11,000.00 USD

Payment Terms:
Payment Due: Net 15 days
Payment Method: Wire Transfer or Corporate Credit Card
Late Fee: 2% per month on overdue balances

Contract Date: December 15, 2024
"""

def normalize_text(text: str) -> str:
    """Normalize OCR text to fix common artifacts"""
    if not text:
        return text

    # Split into lines for processing
    lines = text.split('\n')
    normalized_lines = []

    for line in lines:
        # Replace non-breaking spaces and unicode spaces with regular spaces
        line = re.sub(r'[\u00A0\u2000-\u200B\u2028\u2029]', ' ', line)

        # Replace em/en dashes with hyphens
        line = re.sub(r'[\u2013\u2014]', '-', line)

        # Fix split currency codes: "U S D" -> "USD", "E U R" -> "EUR", etc.
        line = re.sub(r'\bU\s+S\s+D\b', 'USD', line, flags=re.IGNORECASE)
        line = re.sub(r'\bE\s+U\s+R\b', 'EUR', line, flags=re.IGNORECASE)
        line = re.sub(r'\bG\s+B\s+P\b', 'GBP', line, flags=re.IGNORECASE)
        line = re.sub(r'\bC\s+A\s+D\b', 'CAD', line, flags=re.IGNORECASE)
        line = re.sub(r'\bI\s+N\s+R\b', 'INR', line, flags=re.IGNORECASE)

        # Collapse multiple spaces/tabs into single spaces
        line = re.sub(r'[\s\t]+', ' ', line)

        # Strip but preserve the line
        normalized_lines.append(line.strip())

    return '\n'.join(normalized_lines)

def test_total_extraction():
    """Test total amount extraction patterns"""
    print("=== Testing Total Amount Extraction ===")

    normalized_text = normalize_text(SAMPLE_CONTRACT_TEXT)
    print(f"Text normalization: {'U S D' in SAMPLE_CONTRACT_TEXT} -> {'USD' in normalized_text and 'U S D' not in normalized_text}")

    # Test total patterns
    total_patterns = [
        (r'(?i)total\s+due\s*(?:\([^)]+\))?\s*:', 0.95),
        (r'(?i)amount\s+due\s*:', 0.9),
        (r'(?i)grand\s*total\s*:', 0.9),
        (r'(?i)(?<!sub)total\s*:', 0.85),
    ]

    money_pattern = re.compile(r'(?:([$€£₹¥])\s?(\d{1,3}(?:[, \u00A0]\d{3})*(?:\.\d{1,2})?)|(\d{1,3}(?:[, \u00A0]\d{3})*(?:\.\d{1,2})?)\s?(USD|EUR|GBP|INR|CAD))')

    for pattern, confidence in total_patterns:
        match = re.search(pattern, normalized_text, re.MULTILINE | re.IGNORECASE)
        if match:
            print(f"✓ Found total keyword: '{match.group(0)}' (confidence: {confidence})")

            # Look for money amount in +120 char window after the keyword
            search_window = normalized_text[match.end():match.end() + 120]
            money_match = money_pattern.search(search_window)

            if money_match:
                # Extract currency and amount
                prefix_symbol = money_match.group(1)
                prefix_amount = money_match.group(2)
                suffix_amount = money_match.group(3)
                suffix_currency = money_match.group(4)

                if prefix_symbol and prefix_amount:
                    currency = prefix_symbol
                    amount_str = prefix_amount
                elif suffix_amount and suffix_currency:
                    currency = suffix_currency
                    amount_str = suffix_amount
                else:
                    continue

                # Parse amount
                cleaned = re.sub(r'[,$£€₹¥\s\u00A0]', '', amount_str.strip())
                amount = float(cleaned)

                print(f"  ✓ Extracted amount: {amount:,.2f} {currency}")

                if amount == 11000.0 and currency == "USD":
                    print("  ✓ CORRECT: Total amount matches expected 11,000.00 USD")
                else:
                    print(f"  ✗ INCORRECT: Expected 11,000.00 USD, got {amount:,.2f} {currency}")
                break
            else:
                print(f"  ✗ No money amount found after keyword")
    else:
        print("✗ No total keyword patterns matched")

def test_line_items_extraction():
    """Test line items extraction patterns"""
    print("\n=== Testing Line Items Extraction ===")

    normalized_text = normalize_text(SAMPLE_CONTRACT_TEXT)

    # Look for table headers
    table_patterns = [
        r'(?i)(?:description|item)\s+(?:qty|quantity)\s+(?:unit\s+price|price)\s+(?:currency)?\s*(?:total|amount)',
        r'(?i)description\s+quantity\s+unit\s+price\s+currency\s+total',
    ]

    table_match = None
    for pattern in table_patterns:
        table_match = re.search(pattern, normalized_text, re.MULTILINE)
        if table_match:
            print(f"✓ Found table header: '{table_match.group(0)}'")
            break

    if table_match:
        # Extract subsequent rows
        table_start = table_match.end()
        table_section = normalized_text[table_start:table_start + 1500]

        print(f"Table section to analyze:\n{table_section}\n")

        # Line item patterns
        line_patterns = [
            # "System Setup 1 5,000.00 USD 5,000.00"
            r'^([A-Za-z][\w\s&(),.-]{3,50}?)\s+(\d+(?:\s*×\s*)?(?:\d+)?)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+([A-Z]{3})\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
            # "Staff Training 2×$1,500 USD 3,000.00"
            r'^([A-Za-z][\w\s&(),.-]{3,50}?)\s+(\d+)×\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+([A-Z]{3})\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
        ]

        lines = table_section.split('\n')
        line_items = []

        for line in lines[:20]:  # Check first 20 lines
            line = line.strip()
            if len(line) < 10:  # Skip short lines
                continue

            for pattern in line_patterns:
                match = re.match(pattern, line)
                if match:
                    try:
                        description = match.group(1).strip()
                        quantity = match.group(2)

                        if len(match.groups()) == 5:  # Standard format
                            unit_price_str = match.group(3)
                            currency = match.group(4)
                            total_str = match.group(5)
                        else:  # Special format like "2×$1,500"
                            unit_price_str = match.group(3)
                            currency = match.group(4)
                            total_str = match.group(5)

                        # Parse amounts
                        unit_price = float(re.sub(r'[,$]', '', unit_price_str))
                        line_total = float(re.sub(r'[,$]', '', total_str))

                        item = {
                            "description": description,
                            "quantity": quantity,
                            "unit_price": unit_price,
                            "currency": currency,
                            "line_total": line_total
                        }
                        line_items.append(item)
                        print(f"  ✓ Extracted: {description} | {quantity} | ${unit_price:,.2f} | {currency} | ${line_total:,.2f}")
                        break
                    except Exception as e:
                        print(f"  ✗ Error parsing line: {line} - {e}")

        print(f"\nTotal line items extracted: {len(line_items)}")
        if len(line_items) == 3:
            print("✓ CORRECT: Found expected 3 line items")
        else:
            print(f"✗ INCORRECT: Expected 3 line items, found {len(line_items)}")
    else:
        print("✗ No table header found")

def test_payment_terms():
    """Test payment terms extraction"""
    print("\n=== Testing Payment Terms Extraction ===")

    normalized_text = normalize_text(SAMPLE_CONTRACT_TEXT)

    # Net payment terms patterns
    net_patterns = [
        (r'(?i)payment\s+due\s*:\s*net\s+(\d+)\s+days?', 0.9),
        (r'(?i)net\s+(\d+)\s+days?\s+from\s+invoice', 0.9),
        (r'(?i)net\s+(\d+)', 0.8),
    ]

    for pattern, confidence in net_patterns:
        match = re.search(pattern, normalized_text, re.MULTILINE | re.IGNORECASE)
        if match:
            net_days = int(match.group(1))
            print(f"✓ Found payment terms: '{match.group(0)}' -> {net_days} days (confidence: {confidence})")

            if net_days == 15:
                print("  ✓ CORRECT: Net 15 days matches expected")
            else:
                print(f"  ✗ INCORRECT: Expected 15 days, got {net_days}")
            break
    else:
        print("✗ No payment terms patterns matched")

def test_late_fee():
    """Test late fee extraction (should NOT affect billing frequency)"""
    print("\n=== Testing Late Fee Extraction ===")

    normalized_text = normalize_text(SAMPLE_CONTRACT_TEXT)

    # Late fee patterns
    late_fee_patterns = [
        (r'(?i)late\s+fee\s*:\s*(\d+(?:\.\d+)?)\s*%\s*per\s+month', 0.9),
        (r'(?i)(\d+(?:\.\d+)?)\s*%\s*per\s+month\s+(?:on\s+)?(?:overdue|late)', 0.85),
    ]

    for pattern, confidence in late_fee_patterns:
        match = re.search(pattern, normalized_text, re.MULTILINE | re.IGNORECASE)
        if match:
            late_fee_pct = float(match.group(1))
            print(f"✓ Found late fee: '{match.group(0)}' -> {late_fee_pct}% (confidence: {confidence})")

            if late_fee_pct == 2.0:
                print("  ✓ CORRECT: 2% late fee matches expected")
            else:
                print(f"  ✗ INCORRECT: Expected 2%, got {late_fee_pct}%")
            break
    else:
        print("✗ No late fee patterns matched")

def test_billing_frequency_guard():
    """Test that billing frequency is NOT extracted from late fee text"""
    print("\n=== Testing Billing Frequency Guard ===")

    normalized_text = normalize_text(SAMPLE_CONTRACT_TEXT)

    # Original problematic patterns that would incorrectly match late fees
    problematic_patterns = [
        r"(?i)\b(monthly|quarterly|annually|yearly|weekly|bi-weekly|semi-annually)\s+(?:billing|payment|invoice)",
        r"(?i)(?:billed|invoiced|paid)\s+(monthly|quarterly|annually|yearly|weekly)",
        r"(?i)(?:per|every)\s+(month|quarter|year|week)",
    ]

    # Enhanced patterns with guards
    guarded_patterns = [
        r"(?i)\b(monthly|quarterly|annually|yearly|weekly|bi-weekly|semi-annually)\s+(?:billing|payment|invoice)\s+(?:schedule|cycle|frequency)",
        r"(?i)(?:billed|invoiced|paid)\s+(monthly|quarterly|annually|yearly|weekly)\s+(?:in\s+advance|recurring)",
        r"(?i)(?:recurring|subscription)\s+(?:billing|payment)\s*:\s*(monthly|quarterly|annually|yearly|weekly)",
        r"(?i)billing\s+cycle\s*:\s*(monthly|quarterly|annually|yearly|weekly)",
        r"(?i)(?:per|every)\s+(month|quarter|year|week)\s+(?:billing|recurring|subscription)",  # Simplified without lookbehind
    ]

    print("Testing problematic patterns (should match late fee text):")
    for i, pattern in enumerate(problematic_patterns):
        match = re.search(pattern, normalized_text, re.MULTILINE | re.IGNORECASE)
        if match:
            print(f"  ✗ Problematic pattern {i+1} matches: '{match.group(0)}' (would incorrectly extract billing frequency)")
        else:
            print(f"  ✓ Problematic pattern {i+1} does not match")

    print("\nTesting guarded patterns (should NOT match late fee text):")
    for i, pattern in enumerate(guarded_patterns):
        match = re.search(pattern, normalized_text, re.MULTILINE | re.IGNORECASE)
        if match:
            print(f"  ✗ Guarded pattern {i+1} matches: '{match.group(0)}' (unexpected)")
        else:
            print(f"  ✓ Guarded pattern {i+1} does not match (correct)")

if __name__ == "__main__":
    print("Running OneTime Contract Pattern Tests...\n")
    test_total_extraction()
    test_line_items_extraction()
    test_payment_terms()
    test_late_fee()
    test_billing_frequency_guard()
    print("\n" + "="*60)
    print("Test completed! Check results above.")