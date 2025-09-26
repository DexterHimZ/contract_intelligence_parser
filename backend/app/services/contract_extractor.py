from typing import Dict, List, Optional, Tuple, Any
import logging
import re
from datetime import datetime
import time
from app.models.contract import (
    ExtractedField, FieldEvidence, ContractGap,
    GapReason, GapSeverity, ConfidenceSummary, ProcessingMetadata
)
from app.services.extraction_patterns import ContractPatterns
from app.services.pdf_processor import PDFProcessor
from app.services.invoice_extraction_patterns import InvoiceExtractionPatterns

logger = logging.getLogger(__name__)


class ContractExtractor:
    """Main contract extraction service"""

    def __init__(self):
        self.pdf_processor = PDFProcessor()
        self.patterns = ContractPatterns.compile_patterns()
        self.required_fields = [
            "party_1_name", "party_2_name", "effective_date",
            "contract_value", "payment_terms"
        ]
        self.important_fields = [
            "termination_date", "governing_law", "auto_renewal",
            "notice_period", "liability_cap", "line_items", "total_amount",
            "payment_net_days", "payment_methods"
        ]

    async def process_contract(self, file_path: str, progress_callback=None) -> Dict:
        """
        Process a contract PDF and extract all relevant information
        """
        start_time = time.time()
        processing_metadata = ProcessingMetadata()

        def update_progress(percentage: int, status: str = ""):
            if progress_callback:
                progress_callback(percentage, status)
            logger.info(f"Processing progress: {percentage}% - {status}")

        try:
            update_progress(10, "Extracting text from PDF")
            # Extract text from PDF
            pages_data, ocr_used = self.pdf_processor.extract_text_from_pdf(file_path)
            processing_metadata.ocr_used = ocr_used

            update_progress(40, "Analyzing contract content")
            # Combine all pages text for extraction
            full_text = "\n".join([page["content"] for page in pages_data])

            # Extract fields using regex patterns
            extracted_fields = self._extract_fields_from_text(full_text, pages_data)

            update_progress(70, "Calculating confidence scores")
            # Calculate confidence scores
            confidence_summary = self._calculate_confidence_summary(extracted_fields)

            # Identify gaps
            gaps = self._identify_gaps(extracted_fields, confidence_summary)

            # Calculate overall score
            overall_score = self._calculate_overall_score(
                extracted_fields, gaps, confidence_summary
            )

            update_progress(100, "Processing complete")

            # Calculate processing time
            processing_metadata.duration_ms = int((time.time() - start_time) * 1000)

            return {
                "text": {"pages": pages_data},
                "fields": extracted_fields,
                "gaps": gaps,
                "confidence_summary": confidence_summary.dict(),
                "overall_score": overall_score,
                "processing": processing_metadata.dict()
            }

        except Exception as e:
            logger.error(f"Error processing contract: {e}", exc_info=True)
            processing_metadata.error_message = str(e)
            processing_metadata.duration_ms = int((time.time() - start_time) * 1000)
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            raise

    def _extract_fields_from_text(
        self, full_text: str, pages_data: List[Dict]
    ) -> Dict[str, ExtractedField]:
        """Extract fields using regex patterns"""
        extracted_fields = {}

        # Convert pages_data to ContractPage objects for enhanced extraction
        from app.models.contract import ContractPage
        contract_pages = [ContractPage(page=page["page"], content=page["content"]) for page in pages_data]

        # Enhanced invoice and payment terms extraction
        try:
            invoice_fields = InvoiceExtractionPatterns.extract_invoice_and_terms(contract_pages)
            extracted_fields.update(invoice_fields)
            logger.info(f"Enhanced extraction found {len(invoice_fields)} invoice/payment fields")

            # Map invoice fields to core schema fields
            self._map_invoice_fields_to_schema(extracted_fields, invoice_fields)
        except Exception as e:
            logger.error(f"Error in enhanced invoice extraction: {e}", exc_info=True)
            # Continue processing even if invoice extraction fails

        # Standard field extraction using existing patterns
        logger.info(f"Starting field extraction with {len(self.patterns)} patterns")
        logger.info(f"Full text sample (first 500 chars): {full_text[:500]}...")
        missing_fields = ["effective_date", "termination_date", "governing_law", "auto_renewal", "notice_period", "liability_cap"]

        for field_name, pattern in self.patterns.items():
            value, confidence, snippet = ContractPatterns.extract_field(full_text, pattern)

            # Log attempt for missing fields
            if field_name in missing_fields:
                logger.info(f"Attempting extraction for {field_name} with {len(pattern.patterns)} patterns")

            if value is not None:
                # Find which page the evidence is from
                page_num = self._find_page_number(snippet, pages_data)

                # Log extraction of key fields including the missing ones
                if field_name in ["contract_value", "termination_date", "auto_renewal", "effective_date", "governing_law", "notice_period", "liability_cap"]:
                    logger.info(f"Extracted {field_name}: {value} (confidence: {confidence:.3f}) from snippet: {snippet[:100]}...")

                extracted_fields[field_name] = ExtractedField(
                    value=value,
                    confidence=confidence,
                    evidence=FieldEvidence(
                        page=page_num,
                        snippet=snippet[:200],  # Limit snippet length
                        source="rule"
                    )
                )
            else:
                # Log failed extraction for missing fields
                if field_name in missing_fields:
                    logger.warning(f"Failed to extract {field_name} - patterns did not match")

        # Log final extraction results for missing fields
        for field in missing_fields:
            if field in extracted_fields:
                logger.info(f"Successfully extracted {field}: {extracted_fields[field].value}")
            else:
                logger.warning(f"Missing field: {field}")

        # Try to derive termination date if not found but we have effective_date and contract_term
        logger.info(f"Checking termination derivation - termination_date exists: {'termination_date' in extracted_fields}, effective_date exists: {'effective_date' in extracted_fields}, contract_term exists: {'contract_term' in extracted_fields}")

        if ("termination_date" not in extracted_fields and
            "effective_date" in extracted_fields and
            "contract_term" in extracted_fields):

            effective_date_value = extracted_fields["effective_date"].value
            contract_term_value = extracted_fields["contract_term"].value

            logger.info(f"Attempting to derive termination_date from effective_date: {effective_date_value} + contract_term: {contract_term_value}")

            derived_termination, derived_confidence = ContractPatterns.derive_termination_date(
                effective_date_value, str(contract_term_value)
            )

            if derived_termination and derived_confidence > 0:
                logger.info(f"Successfully derived termination_date: {derived_termination} with confidence: {derived_confidence}")
                extracted_fields["termination_date"] = ExtractedField(
                    value=derived_termination,
                    confidence=derived_confidence,
                    evidence=FieldEvidence(
                        page=extracted_fields["effective_date"].evidence.page,
                        snippet=f"Derived from Effective Date: {effective_date_value} + Contract Term: {contract_term_value}",
                        source="derived"
                    )
                )
            else:
                logger.info(f"Failed to derive termination_date - result: {derived_termination}, confidence: {derived_confidence}")

        # Add fields marked as "not applicable" for one-time contracts
        self._mark_inapplicable_fields_for_one_time_contracts(extracted_fields, full_text)

        return extracted_fields

    def _find_page_number(self, snippet: str, pages_data: List[Dict]) -> int:
        """Find which page contains the snippet"""
        for page in pages_data:
            if snippet in page["content"]:
                return page["page"]
        return 1  # Default to first page if not found

    def _calculate_confidence_summary(
        self, fields: Dict[str, ExtractedField]
    ) -> ConfidenceSummary:
        """Calculate confidence statistics"""
        if not fields:
            return ConfidenceSummary()

        confidences = [field.confidence for field in fields.values()]
        low_confidence_threshold = 0.6

        return ConfidenceSummary(
            average=sum(confidences) / len(confidences),
            low_count=sum(1 for c in confidences if c < low_confidence_threshold),
            high_confidence_fields=sum(1 for c in confidences if c >= low_confidence_threshold),
            total_fields=len(fields)
        )

    def _identify_gaps(
        self, fields: Dict[str, ExtractedField],
        confidence_summary: ConfidenceSummary
    ) -> List[ContractGap]:
        """Identify missing or low-confidence fields"""
        gaps = []

        # Updated confidence threshold: don't flag derived values with confidence >= 0.7
        confidence_threshold = 0.6
        derived_confidence_threshold = 0.7

        # Check required fields - skip if marked as N/A
        for field_name in self.required_fields:
            if field_name not in fields:
                gaps.append(ContractGap(
                    field=field_name,
                    reason=GapReason.MISSING,
                    severity=GapSeverity.HIGH
                ))
            else:
                field = fields[field_name]
                # Skip fields marked as "N/A"
                if field.value == "N/A":
                    continue

                # Use different threshold for derived values
                threshold = (
                    derived_confidence_threshold
                    if field.evidence.source == "derived"
                    else confidence_threshold
                )
                if field.confidence < threshold:
                    gaps.append(ContractGap(
                        field=field_name,
                        reason=GapReason.LOW_CONFIDENCE,
                        severity=GapSeverity.HIGH
                    ))

        # Check important fields - skip if marked as N/A
        for field_name in self.important_fields:
            if field_name not in fields:
                gaps.append(ContractGap(
                    field=field_name,
                    reason=GapReason.MISSING,
                    severity=GapSeverity.MEDIUM
                ))
            else:
                field = fields[field_name]
                # Skip fields marked as "N/A"
                if field.value == "N/A":
                    continue

                # Use different threshold for derived values
                threshold = (
                    derived_confidence_threshold
                    if field.evidence.source == "derived"
                    else confidence_threshold
                )
                if field.confidence < threshold:
                    gaps.append(ContractGap(
                        field=field_name,
                        reason=GapReason.LOW_CONFIDENCE,
                        severity=GapSeverity.MEDIUM
                    ))

        return gaps

    def _calculate_overall_score(
        self, fields: Dict[str, ExtractedField],
        gaps: List[ContractGap],
        confidence_summary: ConfidenceSummary
    ) -> float:
        """
        Calculate overall contract score (0-100)
        Based on weighted scoring system from requirements
        """
        score = 0.0

        # Financial completeness: 30 points
        financial_fields = ["contract_value", "total_amount", "currency", "payment_terms", "billing_frequency", "line_items"]
        financial_score = self._calculate_category_score(fields, financial_fields, 30)
        score += financial_score

        # Party identification: 25 points
        party_fields = ["party_1_name", "party_2_name"]
        party_score = self._calculate_category_score(fields, party_fields, 25)
        score += party_score

        # Payment terms clarity: 20 points
        payment_fields = ["payment_terms", "payment_net_days", "payment_methods", "late_fee_percentage", "billing_frequency", "notice_period"]
        payment_score = self._calculate_category_score(fields, payment_fields, 20)
        score += payment_score

        # SLA definition: 15 points
        sla_fields = ["sla_uptime", "support_hours", "liability_cap"]
        sla_score = self._calculate_category_score(fields, sla_fields, 15)
        score += sla_score

        # Contact information: 10 points
        # For now, we'll base this on general completeness
        if confidence_summary.total_fields > 0:
            completeness_ratio = confidence_summary.high_confidence_fields / max(
                len(self.required_fields) + len(self.important_fields), 1
            )
            score += 10 * min(completeness_ratio, 1.0)

        # Apply penalties for gaps
        high_severity_gaps = sum(1 for gap in gaps if gap.severity == GapSeverity.HIGH)
        medium_severity_gaps = sum(1 for gap in gaps if gap.severity == GapSeverity.MEDIUM)

        score -= (high_severity_gaps * 5)  # -5 points per high severity gap
        score -= (medium_severity_gaps * 2)  # -2 points per medium severity gap

        return max(0.0, min(100.0, score))

    def _map_invoice_fields_to_schema(self, extracted_fields: Dict[str, ExtractedField], invoice_fields: Dict[str, ExtractedField]) -> None:
        """Map invoice-specific fields to core schema fields"""
        # Map total_amount to contract_value if not present
        if "total_amount" in invoice_fields and "contract_value" not in extracted_fields:
            extracted_fields["contract_value"] = invoice_fields["total_amount"]
            logger.info("Mapped total_amount to contract_value")

        # Also map total_due_amount to contract_value with higher priority
        if "total_due_amount" in invoice_fields:
            extracted_fields["contract_value"] = invoice_fields["total_due_amount"]
            logger.info("Mapped total_due_amount to contract_value")

        # Map currency fields
        if "total_due_currency" in invoice_fields:
            extracted_fields["currency"] = invoice_fields["total_due_currency"]
            logger.info("Mapped total_due_currency to currency")

        # Map payment terms
        if "payment_due_terms" in invoice_fields and "payment_terms" not in extracted_fields:
            extracted_fields["payment_terms"] = invoice_fields["payment_due_terms"]
            logger.info("Mapped payment_due_terms to payment_terms")

        # Extract all additional fields that don't map to core schema
        additional_fields = {}
        core_schema_fields = set([
            "party_1_name", "party_2_name", "effective_date", "contract_value", "payment_terms",
            "termination_date", "governing_law", "auto_renewal", "notice_period", "liability_cap",
            "line_items", "billing_frequency", "currency"
        ])

        for field_name, field_value in invoice_fields.items():
            if field_name not in core_schema_fields and field_name not in extracted_fields:
                additional_fields[field_name] = field_value

        if additional_fields:
            extracted_fields["additional_fields"] = ExtractedField(
                value=additional_fields,
                confidence=0.8,
                evidence=FieldEvidence(
                    page=1,
                    snippet=f"Additional {len(additional_fields)} fields extracted",
                    source="rule"
                )
            )
            logger.info(f"Captured {len(additional_fields)} additional fields")

    def _mark_inapplicable_fields_for_one_time_contracts(self, extracted_fields: Dict[str, ExtractedField], full_text: str) -> None:
        """Mark fields as N/A for one-time contracts to avoid penalizing score"""
        # Check if this is a one-time contract
        one_time_indicators = [
            r'(?i)\b(one[-\s]?time|single\s+payment|invoice)\b',
            r'(?i)\b(setup|migration|training)\b.*\$',  # Line items suggest one-time work
            r'(?i)total\s+due\s*\([^)]*one[-\s]?time[^)]*\)',
        ]

        is_one_time = any(re.search(pattern, full_text) for pattern in one_time_indicators)

        if is_one_time:
            # Fields not relevant for one-time contracts
            inapplicable_fields = [
                "auto_renewal", "renewal_term", "notice_period",
                "termination_date", "billing_frequency"
            ]

            for field in inapplicable_fields:
                if field not in extracted_fields:
                    extracted_fields[field] = ExtractedField(
                        value="N/A",
                        confidence=0.95,  # High confidence it's not applicable
                        evidence=FieldEvidence(
                            page=1,
                            snippet="not applicable for one-time contract",
                            source="rule"
                        )
                    )

            logger.info(f"Marked {len(inapplicable_fields)} fields as N/A for one-time contract")
        else:
            logger.info("Contract does not appear to be one-time, all fields remain applicable")

    def _calculate_category_score(
        self, fields: Dict[str, ExtractedField],
        category_fields: List[str],
        max_points: float
    ) -> float:
        """Calculate score for a category of fields"""
        found_fields = [f for f in category_fields if f in fields]
        high_confidence_fields = [
            f for f in found_fields
            if fields[f].confidence >= 0.6
        ]

        if not category_fields:
            return 0

        # Score based on presence and confidence
        presence_ratio = len(found_fields) / len(category_fields)
        confidence_ratio = len(high_confidence_fields) / len(category_fields)

        # Weighted average: 60% presence, 40% confidence
        final_ratio = (presence_ratio * 0.6) + (confidence_ratio * 0.4)

        return max_points * final_ratio