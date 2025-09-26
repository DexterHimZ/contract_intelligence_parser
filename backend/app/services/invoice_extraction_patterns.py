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
            # Combine all pages text for extraction
            full_text = "\n".join([f"PAGE {page.page}:\n{page.content}" for page in pages if page.content])

            if not full_text.strip():
                logger.warning("No text content found in pages")
                return {}

            extracted_fields = {}

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

            # Extract total amounts with error handling
            try:
                total_fields = InvoiceExtractionPatterns._extract_totals(full_text, pages)
                if total_fields:
                    # Validate totals are reasonable
                    validated_totals = InvoiceExtractionPatterns._validate_totals(total_fields)
                    extracted_fields.update(validated_totals)
            except Exception as e:
                logger.error(f"Error extracting totals: {e}")

            # Extract payment terms details with error handling
            try:
                payment_fields = InvoiceExtractionPatterns._extract_enhanced_payment_terms(full_text, pages)
                if payment_fields:
                    extracted_fields.update(payment_fields)
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
        table_pattern = r'(?i)(?:description|item)\s+(?:qty|quantity)\s+(?:unit\s+price|price)\s+(?:currency)?\s*(?:total|amount)'
        table_match = re.search(table_pattern, full_text, re.MULTILINE)

        if table_match:
            # Found table headers, extract subsequent rows
            table_start = table_match.end()
            table_section = full_text[table_start:table_start + 1000]  # Look ahead 1000 chars

            # Improved pattern for line item rows with various formats
            line_patterns = [
                # Pattern: Description | Qty | Unit Price | Currency | Total (on same line)
                r'^([A-Za-z][\w\s&(),.-]{3,50}?)\s+(\d+(?:\s+\w+)?)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(USD|EUR|GBP|CAD)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
                # Pattern: Description | Qty | Price | Total (no currency column, on same line)
                r'^([A-Za-z][\w\s&(),.-]{3,50}?)\s+(\d+(?:\s+\w+)?)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
                # Pattern with dollar signs (more restrictive)
                r'^([A-Za-z][\w\s&(),.-]{3,50}?)\s+(\d+(?:\s+\w+)?)\s+\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(?:USD\s+)?\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)$',
            ]

            # Process line by line for better accuracy
            lines = table_section.split('\n')
            for line in lines[:20]:  # Limit to first 20 lines after table header
                line = line.strip()
                if not line or len(line) < 10:  # Skip empty or very short lines
                    continue

                for pattern in line_patterns:
                    match = re.match(pattern, line)
                    if match:
                        try:
                            if len(match.groups()) == 5:  # With currency column
                                description, qty, unit_price, currency, total = match.groups()
                            elif len(match.groups()) == 4:  # Without currency column
                                description, qty, unit_price, total = match.groups()
                                currency = "USD"  # Default currency
                            else:
                                continue

                            # Skip if description is too generic or seems like a header
                            if any(header_word in description.lower() for header_word in
                                   ['description', 'qty', 'quantity', 'price', 'total', 'currency']):
                                continue

                            # Parse quantity and unit
                            qty_parts = qty.strip().split()
                            quantity = qty_parts[0] if qty_parts else qty
                            qty_unit = " ".join(qty_parts[1:]) if len(qty_parts) > 1 else None

                            # Parse monetary amounts
                            parsed_unit_price = InvoiceExtractionPatterns._parse_money(unit_price)
                            parsed_total = InvoiceExtractionPatterns._parse_money(total)

                            # Validate parsed amounts
                            if parsed_unit_price and parsed_total:
                                line_item = {
                                    "description": description.strip(),
                                    "quantity": quantity,
                                    "qty_unit": qty_unit,
                                    "unit_price": parsed_unit_price,
                                    "currency": currency,
                                    "line_total": parsed_total
                                }

                                line_items.append(line_item)

                                # Set evidence from first match
                                if not best_evidence:
                                    page_num = InvoiceExtractionPatterns._find_page_number(line, pages)
                                    best_evidence = FieldEvidence(
                                        page=page_num,
                                        snippet=line[:200],
                                        source="rule"
                                    )
                                break  # Found match for this line, try next line

                        except Exception as e:
                            logger.debug(f"Error parsing line item from line '{line}': {e}")
                            continue

        return line_items if line_items else None, best_evidence

    @staticmethod
    def _extract_totals(full_text: str, pages: List[ContractPage]) -> Dict[str, ExtractedField]:
        """Extract various total amounts and currencies"""
        fields = {}

        # Total amount patterns
        total_patterns = [
            (r'(?i)total\s+due\s*(?:\([^)]+\))?\s*:\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(USD|EUR|GBP|CAD)', "total_amount", 0.9),
            (r'(?i)(?:grand\s+)?total\s*:\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(USD|EUR|GBP|CAD)?', "total_amount", 0.85),
            (r'(?i)contract\s+value\s*:\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(USD|EUR|GBP|CAD)?', "contract_value_total", 0.9),
            (r'(?i)subtotal\s*:\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(USD|EUR|GBP|CAD)?', "subtotal", 0.8),
        ]

        for pattern, field_name, confidence in total_patterns:
            match = re.search(pattern, full_text, re.MULTILINE | re.IGNORECASE)
            if match:
                amount = InvoiceExtractionPatterns._parse_money(match.group(1))
                currency = match.group(2) if len(match.groups()) > 1 and match.group(2) else "USD"

                if amount:
                    page_num = InvoiceExtractionPatterns._find_page_number(match.group(0), pages)
                    fields[field_name] = ExtractedField(
                        value=amount,
                        confidence=confidence,
                        evidence=FieldEvidence(
                            page=page_num,
                            snippet=match.group(0)[:200],
                            source="rule"
                        )
                    )

                    # Also extract currency if we have it
                    if currency and f"{field_name}_currency" not in fields:
                        fields[f"{field_name}_currency"] = ExtractedField(
                            value=currency,
                            confidence=confidence,
                            evidence=FieldEvidence(
                                page=page_num,
                                snippet=match.group(0)[:200],
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
            (r'(?i)payment\s+due\s*:\s*net\s+(\d+)\s+days?', "payment_net_days", 0.9),
            (r'(?i)net\s+(\d+)\s+days?\s+from\s+invoice', "payment_net_days", 0.9),
            (r'(?i)net\s+(\d+)', "payment_net_days", 0.8),
        ]

        for pattern, field_name, confidence in net_patterns:
            match = re.search(pattern, full_text, re.MULTILINE | re.IGNORECASE)
            if match:
                net_days = int(match.group(1))
                page_num = InvoiceExtractionPatterns._find_page_number(match.group(0), pages)

                fields[field_name] = ExtractedField(
                    value=net_days,
                    confidence=confidence,
                    evidence=FieldEvidence(
                        page=page_num,
                        snippet=match.group(0)[:200],
                        source="rule"
                    )
                )

                # Also store the original string
                fields["payment_terms_original"] = ExtractedField(
                    value=match.group(0).strip(),
                    confidence=confidence,
                    evidence=FieldEvidence(
                        page=page_num,
                        snippet=match.group(0)[:200],
                        source="rule"
                    )
                )
                break

        # Late fee patterns
        late_fee_patterns = [
            (r'(?i)late\s+fee\s*:\s*(\d+(?:\.\d+)?)\s*%\s*per\s+month', "late_fee_percentage", 0.9),
            (r'(?i)(\d+(?:\.\d+)?)\s*%\s*per\s+month\s+(?:on\s+)?(?:overdue|late)', "late_fee_percentage", 0.85),
            (r'(?i)late\s+fee\s*:\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "late_fee_amount", 0.8),
        ]

        for pattern, field_name, confidence in late_fee_patterns:
            match = re.search(pattern, full_text, re.MULTILINE | re.IGNORECASE)
            if match:
                if "percentage" in field_name:
                    value = float(match.group(1))
                else:
                    value = InvoiceExtractionPatterns._parse_money(match.group(1))

                page_num = InvoiceExtractionPatterns._find_page_number(match.group(0), pages)
                fields[field_name] = ExtractedField(
                    value=value,
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
    def _parse_money(money_str: str) -> Optional[float]:
        """Parse money string to float, handling commas and currency symbols"""
        try:
            if money_str:
                # Remove currency symbols, commas, and extra spaces
                cleaned = re.sub(r'[,$£€₹¥\s]', '', money_str.strip())
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