#!/usr/bin/env python3
"""
Quick test script to verify extraction patterns work with sample contract or not...
testing the core extraction functionality before starting the full system.....
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.pdf_processor import PDFProcessor
from backend.app.services.extraction_patterns import ContractPatterns

def test_sample_contract():
    """Test extraction on the sample contract"""
    print("Testing Contract Intelligence Parser with sample contract...")

    # Initialize processors
    pdf_processor = PDFProcessor()
    patterns = ContractPatterns.compile_patterns()

    # Process the sample contract
    contract_path = "sample_contract.pdf"

    if not os.path.exists(contract_path):
        print(f"Error: Sample contract not found at {contract_path}")
        return

    try:
        # Extract text
        print(f"\n1. Extracting text from {contract_path}...")
        pages_data, ocr_used = pdf_processor.extract_text_from_pdf(contract_path)
        print(f"   - Pages extracted: {len(pages_data)}")
        print(f"   - OCR used: {ocr_used}")

        # Combine text
        full_text = "\n".join([page["content"] for page in pages_data])
        print(f"   - Total text length: {len(full_text)} characters")

        # Test extraction patterns
        print(f"\n2. Testing extraction patterns...")
        extractions = {}

        for field_name, pattern in patterns.items():
            value, confidence, snippet = ContractPatterns.extract_field(full_text, pattern)
            if value is not None:
                extractions[field_name] = {
                    'value': value,
                    'confidence': confidence,
                    'snippet': snippet[:100] + '...' if len(snippet) > 100 else snippet
                }

        # Display results
        print(f"\n3. Extraction Results ({len(extractions)} fields found):")
        print("=" * 80)

        for field_name, data in extractions.items():
            print(f"\n{field_name.replace('_', ' ').title()}:")
            print(f"  Value: {data['value']}")
            print(f"  Confidence: {data['confidence']:.2f}")
            print(f"  Evidence: {data['snippet']}")

        if not extractions:
            print("No fields extracted. This might indicate:")
            print("- The sample contract format is not recognized by current patterns")
            print("- The PDF text extraction failed")
            print("- The regex patterns need adjustment")

            # Show first 500 characters of extracted text for debugging
            print(f"\nFirst 500 characters of extracted text:")
            print("-" * 50)
            print(full_text[:500])
            print("-" * 50)

        print(f"\n4. Summary:")
        print(f"   - Contract processed successfully: {len(pages_data) > 0}")
        print(f"   - Fields extracted: {len(extractions)}")
        print(f"   - Average confidence: {sum(e['confidence'] for e in extractions.values()) / len(extractions):.2f if extractions else 0}")

        return len(extractions) > 0

    except Exception as e:
        print(f"Error processing contract: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sample_contract()
    print(f"\nTest {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)