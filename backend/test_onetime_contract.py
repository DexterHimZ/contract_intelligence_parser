#!/usr/bin/env python3
"""
Test script for OneTime_Contract.pdf to verify all extraction fixes.

This script tests:
1. Total/contract value extraction (should be 11,000 USD)
2. Billing frequency guard (should not be set for one-time contracts)
3. Line items extraction (should find 3 items)
4. Payment terms extraction (Net 15 days)
5. Late fee handling (2% per month, separate from billing)
6. Text normalization ("U S D" -> "USD")
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend to Python path
backend_path = Path(__file__).parent / "app"
sys.path.insert(0, str(backend_path))

from app.services.contract_extractor import ContractExtractor
from app.services.invoice_extraction_patterns import InvoiceExtractionPatterns
from app.models.contract import ContractPage

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

async def test_extraction():
    """Test the extraction fixes"""
    print("=== Testing OneTime Contract Extraction Fixes ===\n")

    # Create contract pages from sample text
    pages = [ContractPage(page=1, content=SAMPLE_CONTRACT_TEXT)]

    print("1. Testing text normalization...")
    normalized_text = InvoiceExtractionPatterns.normalize_text(SAMPLE_CONTRACT_TEXT)
    if "USD" in normalized_text and "U S D" not in normalized_text:
        print("✓ Text normalization working: 'U S D' -> 'USD'")
    else:
        print("✗ Text normalization failed")

    print("\n2. Testing invoice and payment terms extraction...")
    extracted_fields = InvoiceExtractionPatterns.extract_invoice_and_terms(pages)

    # Test contract value / total amount
    print("\n3. Testing total/contract value extraction...")
    if "total_due_amount" in extracted_fields:
        total_amount = extracted_fields["total_due_amount"].value
        if total_amount == 11000.0:
            print(f"✓ Total due amount correctly extracted: ${total_amount:,.2f}")
        else:
            print(f"✗ Total due amount incorrect: ${total_amount:,.2f} (expected $11,000.00)")
    else:
        print("✗ Total due amount not found")

    if "contract_value" in extracted_fields:
        contract_value = extracted_fields["contract_value"].value
        if contract_value == 11000.0:
            print(f"✓ Contract value correctly mapped: ${contract_value:,.2f}")
        else:
            print(f"✗ Contract value incorrect: ${contract_value:,.2f}")
    else:
        print("✗ Contract value not found")

    # Test currency extraction
    print("\n4. Testing currency extraction...")
    if "total_due_currency" in extracted_fields:
        currency = extracted_fields["total_due_currency"].value
        if currency == "USD":
            print(f"✓ Currency correctly extracted: {currency}")
        else:
            print(f"✗ Currency incorrect: {currency} (expected USD)")
    else:
        print("✗ Currency not found")

    # Test line items
    print("\n5. Testing line items extraction...")
    if "line_items" in extracted_fields:
        line_items = extracted_fields["line_items"].value
        if len(line_items) == 3:
            print(f"✓ Line items count correct: {len(line_items)} items")

            # Check specific line items
            expected_items = [
                {"description": "System Setup", "quantity": "1", "unit_price": 5000.0, "line_total": 5000.0},
                {"description": "Data Migration", "quantity": "1", "unit_price": 3000.0, "line_total": 3000.0},
                {"description": "Staff Training", "quantity": "2", "unit_price": 1500.0, "line_total": 3000.0},
            ]

            for i, expected in enumerate(expected_items):
                if i < len(line_items):
                    item = line_items[i]
                    if (item.get("description", "").startswith(expected["description"][:6]) and
                        float(item.get("unit_price", 0)) == expected["unit_price"] and
                        float(item.get("line_total", 0)) == expected["line_total"]):
                        print(f"  ✓ Line item {i+1}: {item.get('description')} - ${item.get('unit_price'):,.2f} x {item.get('quantity')} = ${item.get('line_total'):,.2f}")
                    else:
                        print(f"  ✗ Line item {i+1} mismatch: {item}")
                else:
                    print(f"  ✗ Missing line item {i+1}")
        else:
            print(f"✗ Line items count incorrect: {len(line_items)} (expected 3)")
            for i, item in enumerate(line_items):
                print(f"  Item {i+1}: {item}")
    else:
        print("✗ Line items not found")

    # Test payment terms
    print("\n6. Testing payment terms extraction...")
    if "payment_due_terms" in extracted_fields:
        payment_terms = extracted_fields["payment_due_terms"].value
        if "Net 15" in payment_terms:
            print(f"✓ Payment terms correctly extracted: {payment_terms}")
        else:
            print(f"✗ Payment terms incorrect: {payment_terms}")
    else:
        print("✗ Payment terms not found")

    if "payment_net_days" in extracted_fields:
        net_days = extracted_fields["payment_net_days"].value
        if net_days == 15:
            print(f"✓ Net days correctly extracted: {net_days}")
        else:
            print(f"✗ Net days incorrect: {net_days}")
    else:
        print("✗ Net days not found")

    # Test late fee (should NOT affect billing frequency)
    print("\n7. Testing late fee extraction...")
    if "late_fee_rate" in extracted_fields:
        late_fee_rate = extracted_fields["late_fee_rate"].value
        if abs(late_fee_rate - 0.02) < 0.001:  # 2% = 0.02
            print(f"✓ Late fee rate correctly extracted: {late_fee_rate*100:.1f}%")
        else:
            print(f"✗ Late fee rate incorrect: {late_fee_rate*100:.1f}%")
    else:
        print("✗ Late fee rate not found")

    if "late_fee_cadence" in extracted_fields:
        cadence = extracted_fields["late_fee_cadence"].value
        if cadence == "monthly":
            print(f"✓ Late fee cadence correctly extracted: {cadence}")
        else:
            print(f"✗ Late fee cadence incorrect: {cadence}")
    else:
        print("✗ Late fee cadence not found")

    # Test billing frequency guard (should NOT be set)
    print("\n8. Testing billing frequency guard...")
    if "billing_frequency" not in extracted_fields:
        print("✓ Billing frequency correctly NOT set for one-time contract")
    else:
        billing_freq = extracted_fields["billing_frequency"].value
        print(f"✗ Billing frequency incorrectly set: {billing_freq}")

    print("\n" + "="*60)
    print("SUMMARY:")
    print(f"Total fields extracted: {len(extracted_fields)}")

    # Print all extracted fields for debugging
    print("\nAll extracted fields:")
    for field_name, field in extracted_fields.items():
        print(f"  {field_name}: {field.value} (confidence: {field.confidence:.3f})")

    return extracted_fields

async def test_full_extraction():
    """Test the full contract extractor with the sample text"""
    print("\n" + "="*60)
    print("=== Testing Full Contract Extractor ===\n")

    extractor = ContractExtractor()

    # Create a temporary file with the sample text
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(SAMPLE_CONTRACT_TEXT)
        temp_file = f.name

    try:
        # This would normally be a PDF, but we'll test with text content directly
        pages_data = [{"page": 1, "content": SAMPLE_CONTRACT_TEXT}]

        # Test the field extraction
        extracted_fields = extractor._extract_fields_from_text(SAMPLE_CONTRACT_TEXT, pages_data)

        print(f"Full extraction found {len(extracted_fields)} fields:")
        for field_name, field in extracted_fields.items():
            print(f"  {field_name}: {field.value} (confidence: {field.confidence:.3f})")

        # Test gap identification
        confidence_summary = extractor._calculate_confidence_summary(extracted_fields)
        gaps = extractor._identify_gaps(extracted_fields, confidence_summary)

        print(f"\nConfidence summary:")
        print(f"  Average: {confidence_summary.average:.3f}")
        print(f"  High confidence fields: {confidence_summary.high_confidence_fields}")
        print(f"  Total fields: {confidence_summary.total_fields}")

        print(f"\nGaps identified: {len(gaps)}")
        for gap in gaps:
            print(f"  {gap.field}: {gap.reason} ({gap.severity} severity)")

        # Test overall score
        overall_score = extractor._calculate_overall_score(extracted_fields, gaps, confidence_summary)
        print(f"\nOverall score: {overall_score:.1f}/100")

    finally:
        os.unlink(temp_file)

if __name__ == "__main__":
    print("Running OneTime Contract extraction tests...\n")
    asyncio.run(test_extraction())
    asyncio.run(test_full_extraction())
    print("\nTest completed!")