"""
Enhanced extraction patterns for invoice and payment terms data
"""
import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from app.models.contract import ExtractedField, FieldEvidence, ContractPage

logger = logging.getLogger(__name__)


@dataclass
class LineItem:
    """Represents a single line item from an invoice"""
    description: str
    quantity: Optional[str] = None
    qty_unit: Optional[str] = None
    unit_price: Optional[float] = None
    currency: Optional[str] = None
    line_total: Optional[float] = None
    confidence: float = 0.0


class InvoiceExtractionPatterns:
    """Enhanced patterns for invoice, line items, and payment terms extraction"""

    # Money pattern for flexible currency detection (supports both prefix and suffix currency)
    MONEY_PAT = re.compile(r'(?:([$€£₹¥])\s?(\d{1,3}(?:[, \u00A0]\d{3})*(?:\.\d{1,2})?)|(\d{1,3}(?:[, \u00A0]\d{3})*(?:\.\d{1,2})?)\s?(USD|EUR|GBP|INR|CAD))')

    # Explicit total detection pattern
    TOTAL_LINE = re.compile(r'(?i)\b(total|grand\s*total|total\s*due|amount\s*due)\b')

    # Currency symbol to code mapping
    CURRENCY_MAP = {
        '$': 'USD',
        '€': 'EUR',
        '£': 'GBP',
        '₹': 'INR',
        '¥': 'JPY'
    }

    @staticmethod
    def _extract_currency_and_amount(money_match) -> Tuple[Optional[str], Optional[str]]:
        """Extract currency and amount from the flexible money pattern match"""
        if not money_match:
            return None, None

        # Group 1: symbol (prefix), Group 2: amount (prefix format)
        # Group 3: amount (suffix format), Group 4: currency code (suffix)
        prefix_symbol = money_match.group(1)
        prefix_amount = money_match.group(2)
        suffix_amount = money_match.group(3)
        suffix_currency = money_match.group(4)

        if prefix_symbol and prefix_amount:
            # Prefix format: $1,000.00
            return prefix_symbol, prefix_amount
        elif suffix_amount and suffix_currency:
            # Suffix format: 1,000.00 USD
            return suffix_currency, suffix_amount

        return None, None

    @staticmethod
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

    @staticmethod
    def extract_invoice_and_terms(pages: List[ContractPage]) -> Dict[str, ExtractedField]:
        """
        Extract comprehensive invoice and payment terms data from contract pages

        Returns:
            Dict containing extracted fields with confidence scores and evidence
        """
        if not pages:
            logger.warning("No pages provided for invoice extraction")
            return {}

        try:
            logger.info(">>> running invoice/one-time extractor")
            # Combine all pages text for extraction with normalization
            page_texts = []
            for page in pages:
                if page.content:
                    normalized_content = InvoiceExtractionPatterns.normalize_text(page.content)
                    page_texts.append(f"PAGE {page.page}:\n{normalized_content}")

            full_text = "\n".join(page_texts)

            if not full_text.strip():
                logger.warning("No text content found in pages")
                return {}

            extracted_fields = {}
            logger.info(f"Processing {len(pages)} pages of contract text")

            # Extract line items with error handling
            try:
                line_items, line_items_evidence = InvoiceExtractionPatterns._extract_line_items(full_text, pages)
                if line_items and len(line_items) > 0:
                    # Validate line items
                    valid_items = InvoiceExtractionPatterns._validate_line_items(line_items)
                    if valid_items:
                        extracted_fields["line_items"] = ExtractedField(
                            value=valid_items,
                            confidence=0.9,  # High confidence for structured table data
                            evidence=line_items_evidence
                        )
                        logger.info(f"Extracted {len(valid_items)} valid line items")
            except Exception as e:
                logger.error(f"Error extracting line items: {e}")

            # Extract total amounts with error handling - PRIORITY for contract_value
            try:
                total_fields = InvoiceExtractionPatterns._extract_totals(full_text, pages)
                if total_fields:
                    # Validate totals are reasonable
                    validated_totals = InvoiceExtractionPatterns._validate_totals(total_fields)
                    extracted_fields.update(validated_totals)
                    logger.info(f"Extracted {len(validated_totals)} total/contract value fields")
            except Exception as e:
                logger.error(f"Error extracting totals: {e}")

            # Extract payment terms details with error handling - AVOID billing_frequency confusion
            try:
                payment_fields = InvoiceExtractionPatterns._extract_enhanced_payment_terms(full_text, pages)
                if payment_fields:
                    # GUARD: Do not derive billing_frequency from late fee text
                    if "billing_frequency" in payment_fields:
                        del payment_fields["billing_frequency"]
                        logger.info("Billing frequency extraction skipped for one-time contracts")
                    extracted_fields.update(payment_fields)
                    logger.info(f"Extracted {len(payment_fields)} payment terms fields")
            except Exception as e:
                logger.error(f"Error extracting payment terms: {e}")

            # Extract payment methods with error handling
            try:
                payment_methods = InvoiceExtractionPatterns._extract_payment_methods(full_text, pages)
                if payment_methods:
                    extracted_fields.update(payment_methods)
            except Exception as e:
                logger.error(f"Error extracting payment methods: {e}")

            logger.info(f"Successfully extracted {len(extracted_fields)} invoice/payment fields")
            return extracted_fields

        except Exception as e:
            logger.error(f"Unexpected error in invoice extraction: {e}")
            return {}

    @staticmethod
    def _extract_line_items(full_text: str, pages: List[ContractPage]) -> Tuple[Optional[List[Dict]], Optional[FieldEvidence]]:
        """Extract line items from invoice tables"""
        line_items = []
        best_evidence = None

        # Pattern 1: Table with headers (Description, Qty, Unit Price, Currency, Total)
        table_patterns = [
            r'(?i)(?:description|item)\s+(?:qty|quantity)\s+(?:unit\s+price|price)\s+(?:currency)?\s*(?:total|amount)',
            r'(?i)description\s+quantity\s+unit\s+price\s+currency\s+total',  # Exact OneTime_Contract format
            r'(?i)item\s+qty\s+price\s+total',  # Simplified format
        ]

        table_match = None
        for pattern in table_patterns:
            table_match = re.search(pattern, full_text, re.MULTILINE)
            if table_match:
                break

        if table_match:
            # Found table headers, extract subsequent rows
            table_start = table_match.end()
            table_section = full_text[table_start:table_start + 1500]  # Look ahead 1500 chars for more line items

            # Try two approaches: single-line format and multi-line format
            line_items = InvoiceExtractionPatterns._extract_single_line_format(table_section, pages) or \
                        InvoiceExtractionPatterns._extract_multi_line_format(table_section, pages)

            if line_items:
                best_evidence = FieldEvidence(
                    page=InvoiceExtractionPatterns._find_page_number(table_section[:100], pages),
                    snippet=table_section[:200],
                    source="rule"
                )
                logger.info(f"Extracted {len(line_items)} line items from table format")
        else:
            # Fallback: Look for line items without explicit table headers
            logger.info("No table headers found, trying fallback line item extraction")
            line_items = InvoiceExtractionPatterns._extract_fallback_line_items(full_text, pages)
            if line_items:
                best_evidence = FieldEvidence(
                    page=1,
                    snippet="line items extracted without headers",
                    source="rule"
                )

        return line_items if line_items else None, best_evidence

    @staticmethod
    def _extract_fallback_line_items(full_text: str, pages: List[ContractPage]) -> Optional[List[Dict]]:
        """Fallback extraction for line items without explicit table headers"""
        line_items = []
        lines = full_text.split('\n')

        # Look for lines that match line item patterns
        item_patterns = [
            # "System Setup 1 5,000.00 USD 5,000.00"
            r'^([A-Za-z][\w\s&(),.-]{3,50})\s+(\d+)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+([A-Z]{3})\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
            # "Staff Training 2×$1,500 USD 3,000.00"
            r'^([A-Za-z][\w\s&(),.-]{3,50})\s+(\d+)×\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+([A-Z]{3})\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
        ]

        for line in lines:
            line = line.strip()
            if len(line) < 10:  # Skip short lines
                continue

            for pattern in item_patterns:
                match = re.match(pattern, line)
                if match:
                    try:
                        description = match.group(1).strip()
                        quantity = match.group(2)
                        unit_price_str = match.group(3)
                        currency = match.group(4)
                        total_str = match.group(5)

                        # Parse amounts
                        unit_price = InvoiceExtractionPatterns._parse_money(unit_price_str)
                        line_total = InvoiceExtractionPatterns._parse_money(total_str)

                        if unit_price and line_total:
                            item = {
                                "description": description,
                                "quantity": quantity,
                                "qty_unit": None,
                                "unit_price": unit_price,
                                "currency": currency,
                                "line_total": line_total
                            }
                            line_items.append(item)
                            logger.debug(f"Fallback extracted line item: {description}")
                            break
                    except Exception as e:
                        logger.debug(f"Error in fallback line item extraction: {e}")
                        continue

        return line_items if line_items else None

    @staticmethod
    def _extract_single_line_format(table_section: str, pages: List[ContractPage]) -> Optional[List[Dict]]:
        """Extract line items from single-line table format"""
        line_items = []

        # Enhanced single-line patterns for the OneTime_Contract.pdf format
        line_patterns = [
            # Pattern for "System Setup 1 5,000.00 USD 5,000.00"
            r'^(?P<desc>[A-Za-z][\w\s&(),.-]{3,50}?)\s+(?P<qty>\d+(?:\s*×\s*)?(?:\d+)?)\s+(?P<price>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(?P<cur>[A-Z]{3})\s+(?P<total>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
            # Pattern for "Staff Training 2×$1,500 USD 3,000.00"
            r'^(?P<desc>[A-Za-z][\w\s&(),.-]{3,50}?)\s+(?P<qty>\d+)×\$(?P<price>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(?P<cur>[A-Z]{3})\s+(?P<total>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
            # ROW_A: Description | Qty | Unit Price | Currency | Total
            r'^(?P<desc>[A-Za-z][\w\s&(),.-]{3,50}?)\s+(?P<qty>\d+(?:\s+\w+)?)\s+(?P<price>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(?P<cur>[A-Z]{3})?\s*(?P<total>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
            # ROW_B: Description | Qty | Price | Total (no explicit currency)
            r'^(?P<desc>[A-Za-z][\w\s&(),.-]{3,50}?)\s+(?P<qty>\d+(?:\s+\w+)?)\s+(?P<price>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(?P<total>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
            # Pattern with currency symbols (flexible)
            r'^(?P<desc>[A-Za-z][\w\s&(),.-]{3,50}?)\s+(?P<qty>\d+(?:\s+\w+)?)\s+[$€£₹]?(?P<price>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?P<cur>[A-Z]{3})?\s*[$€£₹]?(?P<total>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
        ]

        lines = table_section.split('\n')
        for line in lines[:20]:  # Limit to first 20 lines after table header
            line = line.strip()
            if not line or len(line) < 10:  # Skip empty or very short lines
                continue

            for pattern in line_patterns:
                match = re.match(pattern, line)
                if match:
                    try:
                        # Extract and process the line item
                        item = InvoiceExtractionPatterns._process_line_item_match(match, line)
                        if item:
                            line_items.append(item)
                            break  # Found match for this line, try next line

                    except Exception as e:
                        logger.debug(f"Error parsing line item from line '{line}': {e}")
                        continue

        return line_items if line_items else None

    @staticmethod
    def _extract_multi_line_format(table_section: str, pages: List[ContractPage]) -> Optional[List[Dict]]:
        """Extract line items from multi-line table format (each field on separate line)"""
        line_items = []
        lines = [line.strip() for line in table_section.split('\n') if line.strip()]

        i = 0
        while i < len(lines) - 4:  # Need at least 5 lines for desc, qty, price, currency, total
            # Look for a description line (starts with letter, not a number or currency)
            if (not re.match(r'^(\d+|USD|EUR|GBP|[$€£])', lines[i]) and
                len(lines[i]) > 5 and
                not any(word in lines[i].lower() for word in ['total due', 'payment', 'terms'])):

                desc = lines[i]

                # Check if we can find a valid quantity, price, currency, total sequence
                item = InvoiceExtractionPatterns._try_multi_line_sequence(lines, i, desc)
                if item:
                    line_items.append(item)
                    # Skip past the fields we just processed
                    i += 5  # desc + qty + price + currency + total
                else:
                    i += 1
            else:
                i += 1

        return line_items if line_items else None

    @staticmethod
    def _try_multi_line_sequence(lines: List[str], start_idx: int, description: str) -> Optional[Dict]:
        """Try to extract a line item from a multi-line sequence starting at start_idx"""
        try:
            if start_idx + 4 >= len(lines):
                return None

            qty_line = lines[start_idx + 1]
            price_line = lines[start_idx + 2]
            currency_line = lines[start_idx + 3]
            total_line = lines[start_idx + 4]

            # Validate quantity (number possibly followed by unit)
            qty_match = re.match(r'^(\d+)(?:\s+(\w+))?$', qty_line)
            if not qty_match:
                return None
            quantity = qty_match.group(1)
            qty_unit = qty_match.group(2)

            # Validate price (number with optional commas and decimals)
            if not re.match(r'^\d{1,3}(?:,\d{3})*(?:\.\d{2})?$', price_line):
                return None
            unit_price = InvoiceExtractionPatterns._parse_money(price_line)

            # Validate currency (3-letter code)
            if not re.match(r'^[A-Z]{3}$', currency_line):
                return None
            currency = currency_line

            # Validate total (number with optional commas and decimals)
            if not re.match(r'^\d{1,3}(?:,\d{3})*(?:\.\d{2})?$', total_line):
                return None
            line_total = InvoiceExtractionPatterns._parse_money(total_line)

            # Basic validation: total should be reasonable relative to qty * unit_price
            expected_total = float(quantity) * unit_price
            if abs(line_total - expected_total) / expected_total > 0.01:  # Allow 1% tolerance
                return None

            return {
                "description": description.strip(),
                "quantity": quantity,
                "qty_unit": qty_unit,
                "unit_price": unit_price,
                "currency": currency,
                "line_total": line_total
            }

        except Exception as e:
            logger.debug(f"Error processing multi-line sequence: {e}")
            return None

    @staticmethod
    def _process_line_item_match(match, line: str) -> Optional[Dict]:
        """Process a regex match into a line item dictionary"""
        try:
            # Extract named groups
            description = match.group('desc')
            qty = match.group('qty')
            unit_price = match.group('price')
            total = match.group('total')
            currency = match.group('cur') if 'cur' in match.groupdict() else None

            # If no currency detected in row, scan the line for currency symbols/codes
            if not currency:
                money_match = InvoiceExtractionPatterns.MONEY_PAT.search(line)
                if money_match:
                    symbol_or_code, _ = InvoiceExtractionPatterns._extract_currency_and_amount(money_match)
                    currency = InvoiceExtractionPatterns.CURRENCY_MAP.get(symbol_or_code, symbol_or_code)
                else:
                    currency = "USD"  # Default fallback

            # Skip if description is too generic or seems like a header
            if any(header_word in description.lower() for header_word in
                   ['description', 'qty', 'quantity', 'price', 'total', 'currency']):
                return None

            # Handle special quantity formats like "2×$1,500" or "2×1,500"
            if '×' in qty:
                qty_parts = qty.split('×')
                if len(qty_parts) == 2:
                    quantity = qty_parts[0].strip()
                    # Check if price is embedded in qty ("2×$1,500")
                    embedded_price = qty_parts[1].strip()
                    if embedded_price.startswith('$'):
                        unit_price = embedded_price[1:]  # Remove $
                    qty_unit = None
                else:
                    # Parse quantity and unit normally
                    qty_parts = qty.strip().split()
                    quantity = qty_parts[0] if qty_parts else qty
                    qty_unit = " ".join(qty_parts[1:]) if len(qty_parts) > 1 else None
            else:
                # Parse quantity and unit normally
                qty_parts = qty.strip().split()
                quantity = qty_parts[0] if qty_parts else qty
                qty_unit = " ".join(qty_parts[1:]) if len(qty_parts) > 1 else None

            # Parse monetary amounts
            parsed_unit_price = InvoiceExtractionPatterns._parse_money(unit_price)
            parsed_total = InvoiceExtractionPatterns._parse_money(total)

            # Validate parsed amounts and basic consistency
            if parsed_unit_price and parsed_total:
                # Clean quantity to get numeric value
                numeric_qty = re.sub(r'[^\d.]', '', quantity)
                try:
                    qty_float = float(numeric_qty) if numeric_qty else 1.0
                    # Allow some tolerance for rounding differences
                    expected_total = qty_float * parsed_unit_price
                    if abs(parsed_total - expected_total) / max(parsed_total, expected_total) <= 0.05:  # 5% tolerance
                        return {
                            "description": description.strip(),
                            "quantity": quantity,
                            "qty_unit": qty_unit,
                            "unit_price": parsed_unit_price,
                            "currency": currency,
                            "line_total": parsed_total
                        }
                    else:
                        logger.debug(f"Line item validation failed: qty={qty_float}, unit_price={parsed_unit_price}, expected={expected_total}, actual={parsed_total}")
                except (ValueError, ZeroDivisionError):
                    # If we can't validate, still return the item if amounts are reasonable
                    return {
                        "description": description.strip(),
                        "quantity": quantity,
                        "qty_unit": qty_unit,
                        "unit_price": parsed_unit_price,
                        "currency": currency,
                        "line_total": parsed_total
                    }

        except Exception as e:
            logger.debug(f"Error processing line item match: {e}")

        return None

    @staticmethod
    def _extract_totals(full_text: str, pages: List[ContractPage]) -> Dict[str, ExtractedField]:
        """Extract various total amounts with explicit keyword prioritization and fallback computation"""
        fields = {}
        total_amount = None
        total_currency = None
        total_evidence = None
        contract_value = None
        contract_currency = None
        contract_evidence = None

        # Step 1: Look for explicit total keywords with priority
        explicit_total_patterns = [
            (r'(?i)total\s+due\s*(?:\([^)]+\))?\s*:', 0.95),  # Highest priority
            (r'(?i)amount\s+due\s*:', 0.9),
            (r'(?i)grand\s*total\s*:', 0.9),
            (r'(?i)(?<!sub)total\s*:', 0.85),  # Exclude "subtotal"
        ]

        for pattern, confidence in explicit_total_patterns:
            match = re.search(pattern, full_text, re.MULTILINE | re.IGNORECASE)
            if match and not total_amount:  # Only take first explicit match
                # Look for money amount in +120 char window after the keyword
                search_window = full_text[match.end():match.end() + 120]
                money_match = InvoiceExtractionPatterns.MONEY_PAT.search(search_window)

                if money_match:
                    symbol_or_code, amount_str = InvoiceExtractionPatterns._extract_currency_and_amount(money_match)

                    total_amount = InvoiceExtractionPatterns._parse_money(amount_str)
                    total_currency = InvoiceExtractionPatterns.CURRENCY_MAP.get(symbol_or_code, symbol_or_code)

                    if total_amount:
                        page_num = InvoiceExtractionPatterns._find_page_number(match.group(0), pages)
                        total_evidence = FieldEvidence(
                            page=page_num,
                            snippet=f"{match.group(0)} {money_match.group(0)}"[:200],
                            source="rule"
                        )

                        fields["total_amount"] = ExtractedField(
                            value=total_amount,
                            confidence=confidence,
                            evidence=total_evidence
                        )

                        fields["total_amount_currency"] = ExtractedField(
                            value=total_currency,
                            confidence=confidence,
                            evidence=total_evidence
                        )
                        break

        # Step 2: Look for explicit contract value
        contract_value_pattern = r'(?i)contract\s+value\s*:'
        match = re.search(contract_value_pattern, full_text, re.MULTILINE | re.IGNORECASE)
        if match:
            search_window = full_text[match.end():match.end() + 120]
            money_match = InvoiceExtractionPatterns.MONEY_PAT.search(search_window)

            if money_match:
                symbol_or_code, amount_str = InvoiceExtractionPatterns._extract_currency_and_amount(money_match)

                contract_value = InvoiceExtractionPatterns._parse_money(amount_str)
                contract_currency = InvoiceExtractionPatterns.CURRENCY_MAP.get(symbol_or_code, symbol_or_code)

                if contract_value:
                    page_num = InvoiceExtractionPatterns._find_page_number(match.group(0), pages)
                    contract_evidence = FieldEvidence(
                        page=page_num,
                        snippet=f"{match.group(0)} {money_match.group(0)}"[:200],
                        source="rule"
                    )

                    fields["contract_value_total"] = ExtractedField(
                        value=contract_value,
                        confidence=0.9,
                        evidence=contract_evidence
                    )

                    fields["contract_value_total_currency"] = ExtractedField(
                        value=contract_currency,
                        confidence=0.9,
                        evidence=contract_evidence
                    )

        # Step 3: Fallback total computation from line items if no explicit total found
        if not total_amount:
            line_items_total, computed_currency = InvoiceExtractionPatterns._compute_total_from_line_items(full_text, pages)
            if line_items_total and line_items_total > 0:
                total_amount = round(line_items_total, 2)
                total_currency = computed_currency or "USD"

                fields["total_amount"] = ExtractedField(
                    value=total_amount,
                    confidence=0.8,  # Lower confidence for computed
                    evidence=FieldEvidence(
                        page=1,
                        snippet="computed from line items",
                        source="rule"
                    )
                )

                fields["total_amount_currency"] = ExtractedField(
                    value=total_currency,
                    confidence=0.8,
                    evidence=FieldEvidence(
                        page=1,
                        snippet="inferred from line items",
                        source="rule"
                    )
                )

        # Step 4: For one-time invoices, ALWAYS set contract_value = total_amount
        if total_amount and not contract_value:
            # Set contract_value = total_due_amount for all one-time agreements
            fields["contract_value"] = ExtractedField(
                value=total_amount,
                confidence=0.9,  # High confidence for one-time contracts
                evidence=FieldEvidence(
                    page=total_evidence.page if total_evidence else 1,
                    snippet="derived from total amount for one-time contract",
                    source="rule"
                )
            )

            fields["currency"] = ExtractedField(
                value=total_currency,
                confidence=0.9,
                evidence=FieldEvidence(
                    page=total_evidence.page if total_evidence else 1,
                    snippet="derived from total currency for one-time contract",
                    source="rule"
                )
            )

        # Also maintain the specific total fields
        if total_amount:
            fields["total_due_amount"] = ExtractedField(
                value=total_amount,
                confidence=fields["total_amount"].confidence if "total_amount" in fields else 0.9,
                evidence=total_evidence or FieldEvidence(
                    page=1,
                    snippet="total due amount extracted",
                    source="rule"
                )
            )

            fields["total_due_currency"] = ExtractedField(
                value=total_currency,
                confidence=fields["total_amount_currency"].confidence if "total_amount_currency" in fields else 0.9,
                evidence=total_evidence or FieldEvidence(
                    page=1,
                    snippet="total due currency extracted",
                    source="rule"
                )
            )

        # Extract subtotals separately (lower priority)
        subtotal_pattern = r'(?i)subtotal\s*:'
        match = re.search(subtotal_pattern, full_text, re.MULTILINE | re.IGNORECASE)
        if match:
            search_window = full_text[match.end():match.end() + 120]
            money_match = InvoiceExtractionPatterns.MONEY_PAT.search(search_window)

            if money_match:
                symbol_or_code, amount_str = InvoiceExtractionPatterns._extract_currency_and_amount(money_match)

                subtotal = InvoiceExtractionPatterns._parse_money(amount_str)
                subtotal_currency = InvoiceExtractionPatterns.CURRENCY_MAP.get(symbol_or_code, symbol_or_code)

                if subtotal:
                    page_num = InvoiceExtractionPatterns._find_page_number(match.group(0), pages)
                    fields["subtotal"] = ExtractedField(
                        value=subtotal,
                        confidence=0.8,
                        evidence=FieldEvidence(
                            page=page_num,
                            snippet=f"{match.group(0)} {money_match.group(0)}"[:200],
                            source="rule"
                        )
                    )

        return fields

    @staticmethod
    def _extract_enhanced_payment_terms(full_text: str, pages: List[ContractPage]) -> Dict[str, ExtractedField]:
        """Extract detailed payment terms including net days, late fees, etc."""
        fields = {}

        # Net payment terms patterns
        net_patterns = [
            (r'(?i)payment\s+due\s*:\s*net\s+(\d+)\s+days?', "payment_net_days", "payment_due_terms", 0.9),
            (r'(?i)net\s+(\d+)\s+days?\s+from\s+invoice', "payment_net_days", "payment_due_terms", 0.9),
            (r'(?i)net\s+(\d+)', "payment_net_days", "payment_due_terms", 0.8),
        ]

        for pattern, days_field, terms_field, confidence in net_patterns:
            match = re.search(pattern, full_text, re.MULTILINE | re.IGNORECASE)
            if match:
                net_days = int(match.group(1))
                page_num = InvoiceExtractionPatterns._find_page_number(match.group(0), pages)

                fields[days_field] = ExtractedField(
                    value=net_days,
                    confidence=confidence,
                    evidence=FieldEvidence(
                        page=page_num,
                        snippet=match.group(0)[:200],
                        source="rule"
                    )
                )

                # Store both structured and original terms
                fields[terms_field] = ExtractedField(
                    value=f"Net {net_days} days",
                    confidence=confidence,
                    evidence=FieldEvidence(
                        page=page_num,
                        snippet=match.group(0)[:200],
                        source="rule"
                    )
                )

                # Also store the exact original string
                fields["payment_terms"] = ExtractedField(
                    value=match.group(0).strip(),
                    confidence=confidence,
                    evidence=FieldEvidence(
                        page=page_num,
                        snippet=match.group(0)[:200],
                        source="rule"
                    )
                )
                break

        # Late fee patterns - separate from billing frequency
        late_fee_patterns = [
            (r'(?i)late\s+fee\s*:\s*(\d+(?:\.\d+)?)\s*%\s*per\s+month', "late_fee_rate", "late_fee_cadence", 0.9),
            (r'(?i)(\d+(?:\.\d+)?)\s*%\s*per\s+month\s+(?:on\s+)?(?:overdue|late)', "late_fee_rate", "late_fee_cadence", 0.85),
            (r'(?i)late\s+fee\s*:\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "late_fee_amount", None, 0.8),
        ]

        for pattern, rate_field, cadence_field, confidence in late_fee_patterns:
            match = re.search(pattern, full_text, re.MULTILINE | re.IGNORECASE)
            if match:
                if "rate" in rate_field:
                    rate_value = float(match.group(1)) / 100.0  # Convert percentage to decimal
                    page_num = InvoiceExtractionPatterns._find_page_number(match.group(0), pages)

                    fields[rate_field] = ExtractedField(
                        value=rate_value,
                        confidence=confidence,
                        evidence=FieldEvidence(
                            page=page_num,
                            snippet=match.group(0)[:200],
                            source="rule"
                        )
                    )

                    # Store cadence separately - do NOT confuse with billing_frequency
                    if cadence_field:
                        fields[cadence_field] = ExtractedField(
                            value="monthly",
                            confidence=confidence,
                            evidence=FieldEvidence(
                                page=page_num,
                                snippet=match.group(0)[:200],
                                source="rule"
                            )
                        )
                else:
                    amount_value = InvoiceExtractionPatterns._parse_money(match.group(1))
                    page_num = InvoiceExtractionPatterns._find_page_number(match.group(0), pages)
                    fields[rate_field] = ExtractedField(
                        value=amount_value,
                        confidence=confidence,
                        evidence=FieldEvidence(
                            page=page_num,
                            snippet=match.group(0)[:200],
                            source="rule"
                        )
                    )
                break

        return fields

    @staticmethod
    def _extract_payment_methods(full_text: str, pages: List[ContractPage]) -> Dict[str, ExtractedField]:
        """Extract accepted payment methods"""
        # Payment method patterns
        payment_method_pattern = r'(?i)payment\s+method\s*:\s*([^.\n]+)'
        match = re.search(payment_method_pattern, full_text, re.MULTILINE)

        if match:
            methods_text = match.group(1).strip()
            # Parse individual methods
            methods = []
            method_keywords = {
                "wire transfer": "Wire Transfer",
                "wire": "Wire Transfer",
                "ach": "ACH",
                "credit card": "Credit Card",
                "bank transfer": "Bank Transfer",
                "check": "Check",
                "cash": "Cash"
            }

            methods_lower = methods_text.lower()
            for keyword, method_name in method_keywords.items():
                if keyword in methods_lower:
                    methods.append(method_name)

            if methods:
                page_num = InvoiceExtractionPatterns._find_page_number(match.group(0), pages)
                return {
                    "payment_methods": ExtractedField(
                        value=methods,
                        confidence=0.9,
                        evidence=FieldEvidence(
                            page=page_num,
                            snippet=match.group(0)[:200],
                            source="rule"
                        )
                    )
                }

        return {}

    @staticmethod
    def _compute_total_from_line_items(full_text: str, pages: List[ContractPage]) -> Tuple[Optional[float], Optional[str]]:
        """Compute total by summing line items as fallback"""
        try:
            # Re-extract line items for computation
            line_items, _ = InvoiceExtractionPatterns._extract_line_items(full_text, pages)

            if not line_items:
                return None, None

            total_sum = 0.0
            currency = None

            for item in line_items:
                # Try line_total first, then compute from qty * unit_price
                if item.get("line_total"):
                    total_sum += item["line_total"]
                    if not currency and item.get("currency"):
                        currency = item["currency"]
                elif item.get("quantity") and item.get("unit_price"):
                    try:
                        qty = float(item["quantity"])
                        price = item["unit_price"]
                        total_sum += qty * price
                        if not currency and item.get("currency"):
                            currency = item["currency"]
                    except (ValueError, TypeError):
                        continue

            return total_sum if total_sum > 0 else None, currency

        except Exception as e:
            logger.debug(f"Error computing total from line items: {e}")
            return None, None

    @staticmethod
    def _parse_money(money_str: str) -> Optional[float]:
        """Parse money string to float, handling commas and currency symbols"""
        try:
            if money_str:
                # Remove currency symbols, commas, and extra spaces
                cleaned = re.sub(r'[,$£€₹¥\s\u00A0]', '', money_str.strip())
                return float(cleaned)
        except (ValueError, AttributeError):
            pass
        return None

    @staticmethod
    def _find_page_number(snippet: str, pages: List[ContractPage]) -> int:
        """Find which page contains the snippet"""
        for page in pages:
            if snippet in page.content:
                return page.page
        return 1  # Default to first page if not found

    @staticmethod
    def _validate_line_items(line_items: List[Dict]) -> List[Dict]:
        """Validate and clean line items"""
        valid_items = []
        for item in line_items:
            try:
                # Must have description
                if not item.get("description") or len(item["description"].strip()) < 3:
                    continue

                # Validate numeric fields
                if item.get("unit_price") and (item["unit_price"] < 0 or item["unit_price"] > 1000000):
                    continue

                if item.get("line_total") and (item["line_total"] < 0 or item["line_total"] > 10000000):
                    continue

                # Validate quantity
                if item.get("quantity"):
                    try:
                        qty = float(item["quantity"])
                        if qty < 0 or qty > 10000:
                            continue
                    except (ValueError, TypeError):
                        # Keep as string if not numeric
                        pass

                # Clean up description
                item["description"] = item["description"].strip()

                valid_items.append(item)

            except Exception as e:
                logger.debug(f"Error validating line item: {e}")
                continue

        return valid_items

    @staticmethod
    def _validate_totals(total_fields: Dict[str, ExtractedField]) -> Dict[str, ExtractedField]:
        """Validate total amounts are reasonable"""
        validated = {}
        for field_name, field in total_fields.items():
            try:
                if isinstance(field.value, (int, float)):
                    # Check if amount is reasonable (between $1 and $100M)
                    if 1 <= field.value <= 100000000:
                        validated[field_name] = field
                    else:
                        logger.warning(f"Total amount {field.value} seems unreasonable for field {field_name}")
                else:
                    # Non-numeric values (like currency codes) pass through
                    validated[field_name] = field
            except Exception as e:
                logger.debug(f"Error validating total field {field_name}: {e}")
                continue

        return validated

    @staticmethod
    def write_invoice_fields_into_dict(fields: Dict[str, ExtractedField], result: Dict[str, Any]) -> None:
        """
        Helper function to write invoice fields into a result dictionary

        Args:
            fields: Dictionary of extracted fields
            result: Target dictionary to write structured results into
        """
        # Write line items
        if "line_items" in fields:
            result["line_items"] = {
                "items": fields["line_items"].value,
                "count": len(fields["line_items"].value),
                "confidence": fields["line_items"].confidence,
                "evidence": fields["line_items"].evidence.dict() if fields["line_items"].evidence else None
            }

        # Write financial totals
        financial_fields = ["total_amount", "contract_value_total", "subtotal"]
        for field in financial_fields:
            if field in fields:
                result[field] = {
                    "value": fields[field].value,
                    "currency": fields.get(f"{field}_currency", {}).get("value", "USD"),
                    "confidence": fields[field].confidence,
                    "evidence": fields[field].evidence.dict() if fields[field].evidence else None
                }

        # Write payment terms
        payment_fields = ["payment_net_days", "payment_terms_original", "late_fee_percentage", "late_fee_amount"]
        for field in payment_fields:
            if field in fields:
                result[field] = {
                    "value": fields[field].value,
                    "confidence": fields[field].confidence,
                    "evidence": fields[field].evidence.dict() if fields[field].evidence else None
                }

        # Write payment methods
        if "payment_methods" in fields:
            result["payment_methods"] = {
                "methods": fields["payment_methods"].value,
                "confidence": fields["payment_methods"].confidence,
                "evidence": fields["payment_methods"].evidence.dict() if fields["payment_methods"].evidence else None
            }