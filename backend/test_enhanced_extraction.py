#!/usr/bin/env python3
"""
Test script for enhanced invoice and payment terms extraction
"""
import sys
import os
import asyncio
import logging
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.contract_extractor import ContractExtractor
from app.services.invoice_extraction_patterns import InvoiceExtractionPatterns
from app.models.contract import ContractPage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_invoice_extraction_patterns():
    """Test invoice extraction patterns with sample text"""
    print("=" * 80)
    print("TESTING INVOICE EXTRACTION PATTERNS")
    print("=" * 80)

    # Sample contract text from OneTime_Contract.pdf
    sample_text = """
    3. Invoice
    Description Qty Unit Price Currency Total
    System Setup & Configuration 1 5,000.00 USD 5,000.00
    Data Migration (up to 1TB) 1 3,000.00 USD 3,000.00
    Initial Staff Training (On-site) 2 days 1,500.00 USD 3,000.00
    Total Due (One-Time): 11,000.00 USD

    4. Payment Terms
    Invoice to be issued immediately upon execution of this agreement.
    Payment Due: Net 15 days from invoice date.
    Late Fee: 2% per month on overdue balances.
    Payment Method: Wire Transfer or Corporate Credit Card.
    """

    # Create ContractPage objects
    pages = [ContractPage(page=1, content=sample_text)]

    try:
        # Test enhanced extraction
        extracted_fields = InvoiceExtractionPatterns.extract_invoice_and_terms(pages)

        print(f"\nExtracted {len(extracted_fields)} fields:")
        for field_name, field in extracted_fields.items():
            print(f"\n{field_name}:")
            print(f"  Value: {field.value}")
            print(f"  Confidence: {field.confidence:.3f}")
            if field.evidence:
                print(f"  Evidence (page {field.evidence.page}): {field.evidence.snippet[:100]}...")

        # Test helper function
        result_dict = {}
        InvoiceExtractionPatterns.write_invoice_fields_into_dict(extracted_fields, result_dict)

        print("\n" + "=" * 40)
        print("STRUCTURED OUTPUT:")
        print("=" * 40)
        for key, value in result_dict.items():
            print(f"{key}: {value}")

    except Exception as e:
        print(f"Error in test: {e}")
        import traceback
        traceback.print_exc()


async def test_full_contract_extraction():
    """Test full contract extraction with sample PDF"""
    print("\n" + "=" * 80)
    print("TESTING FULL CONTRACT EXTRACTION")
    print("=" * 80)

    # Test with actual sample contracts
    sample_files = [
        "/mnt/e/contract_intelligence_parser/OneTime_Contract.pdf",
        "/mnt/e/contract_intelligence_parser/GreenEnergyCorp_OneTime_Contract.pdf"
    ]

    extractor = ContractExtractor()

    for file_path in sample_files:
        if not Path(file_path).exists():
            print(f"Sample file not found: {file_path}")
            continue

        print(f"\n{'='*20} TESTING: {Path(file_path).name} {'='*20}")

        try:
            result = await extractor.process_contract(file_path)

            print(f"Processing completed successfully!")
            print(f"Text pages: {len(result['text']['pages'])}")
            print(f"Extracted fields: {len(result['fields'])}")
            print(f"Gaps identified: {len(result['gaps'])}")
            print(f"Overall score: {result['overall_score']:.1f}")

            # Show extracted invoice/payment fields
            invoice_fields = [k for k in result['fields'].keys()
                            if any(keyword in k for keyword in ['line_items', 'total_amount', 'payment', 'late_fee'])]

            if invoice_fields:
                print(f"\nInvoice/Payment fields extracted:")
                for field_name in invoice_fields:
                    field = result['fields'][field_name]
                    print(f"  {field_name}: {field['value']} (confidence: {field['confidence']:.3f})")

            # Show any gaps
            if result['gaps']:
                print(f"\nGaps identified:")
                for gap in result['gaps']:
                    print(f"  {gap['field']}: {gap['reason']} ({gap['severity']})")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            import traceback
            traceback.print_exc()


def test_regex_patterns():
    """Test individual regex patterns"""
    print("\n" + "=" * 80)
    print("TESTING INDIVIDUAL REGEX PATTERNS")
    print("=" * 80)

    test_cases = [
        ("Total Due (One-Time): 11,000.00 USD", "total amount pattern"),
        ("Payment Due: Net 15 days from invoice date.", "net payment terms"),
        ("Late Fee: 2% per month on overdue balances.", "late fee percentage"),
        ("Payment Method: Wire Transfer or Corporate Credit Card.", "payment methods"),
        ("System Setup & Configuration 1 5,000.00 USD 5,000.00", "line item pattern"),
    ]

    import re
    from app.services.invoice_extraction_patterns import InvoiceExtractionPatterns

    for text, description in test_cases:
        print(f"\nTesting: {description}")
        print(f"Text: {text}")

        # Test total amount pattern
        if "total amount" in description:
            pattern = r'(?i)total\s+due\s*(?:\([^)]+\))?\s*:\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(USD|EUR|GBP|CAD)'
            match = re.search(pattern, text)
            if match:
                amount = InvoiceExtractionPatterns._parse_money(match.group(1))
                currency = match.group(2)
                print(f"  Matched: Amount=${amount}, Currency={currency}")

        # Test net payment terms
        elif "net payment" in description:
            pattern = r'(?i)payment\s+due\s*:\s*net\s+(\d+)\s+days?'
            match = re.search(pattern, text)
            if match:
                print(f"  Matched: Net {match.group(1)} days")

        # Test late fee
        elif "late fee" in description:
            pattern = r'(?i)late\s+fee\s*:\s*(\d+(?:\.\d+)?)\s*%\s*per\s+month'
            match = re.search(pattern, text)
            if match:
                print(f"  Matched: {match.group(1)}% per month")

        # Test payment methods
        elif "payment methods" in description:
            pattern = r'(?i)payment\s+method\s*:\s*([^.\n]+)'
            match = re.search(pattern, text)
            if match:
                print(f"  Matched: {match.group(1).strip()}")


if __name__ == "__main__":
    print("Enhanced Contract Intelligence Parser - Test Suite")
    print("=" * 80)

    # Run tests
    test_regex_patterns()
    test_invoice_extraction_patterns()

    # Run async test
    asyncio.run(test_full_contract_extraction())

    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETED")
    print("=" * 80)