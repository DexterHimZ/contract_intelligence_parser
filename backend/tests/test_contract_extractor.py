import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.contract_extractor import ContractExtractor
from app.models.contract import ConfidenceSummary, ContractGap, GapReason, GapSeverity


class TestContractExtractor:
    def setup_method(self):
        self.extractor = ContractExtractor()

    @patch('app.services.contract_extractor.PDFProcessor')
    async def test_process_contract_success(self, mock_pdf_processor):
        # Mock PDF processor
        mock_pdf_processor_instance = Mock()
        mock_pdf_processor.return_value = mock_pdf_processor_instance
        mock_pdf_processor_instance.extract_text_from_pdf.return_value = (
            [{"page": 1, "content": "Sample contract text with Acme Corporation and net 30 payment terms"}],
            False
        )

        # Create new extractor with mocked PDF processor
        extractor = ContractExtractor()
        extractor.pdf_processor = mock_pdf_processor_instance

        result = await extractor.process_contract("/fake/path")

        assert "text" in result
        assert "fields" in result
        assert "gaps" in result
        assert "confidence_summary" in result
        assert "overall_score" in result
        assert "processing" in result

        # Check that processing metadata is included
        assert result["processing"]["duration_ms"] > 0
        assert result["processing"]["ocr_used"] is False

    def test_extract_fields_from_text(self):
        text = """
        This Agreement is between Acme Corporation and Vendor Inc.
        The effective date is January 1, 2024.
        Payment terms: Net 30 days.
        Total contract value: $100,000.
        """

        pages_data = [{"page": 1, "content": text}]
        fields = self.extractor._extract_fields_from_text(text, pages_data)

        # Should extract some fields
        assert len(fields) > 0

        # Check specific extractions
        if "party_1_name" in fields:
            assert "Acme" in str(fields["party_1_name"].value)
            assert fields["party_1_name"].evidence.page == 1

    def test_calculate_confidence_summary(self):
        from app.models.contract import ExtractedField, FieldEvidence

        fields = {
            "field1": ExtractedField(value="test", confidence=0.9, evidence=FieldEvidence(page=1, snippet="test", source="rule")),
            "field2": ExtractedField(value="test", confidence=0.5, evidence=FieldEvidence(page=1, snippet="test", source="rule")),
            "field3": ExtractedField(value="test", confidence=0.8, evidence=FieldEvidence(page=1, snippet="test", source="rule"))
        }

        summary = self.extractor._calculate_confidence_summary(fields)

        assert summary.total_fields == 3
        assert summary.high_confidence_fields == 2  # 0.9 and 0.8
        assert summary.low_count == 1  # 0.5
        assert abs(summary.average - 0.733) < 0.01  # (0.9 + 0.5 + 0.8) / 3

    def test_identify_gaps_missing_required_fields(self):
        from app.models.contract import ExtractedField, FieldEvidence

        # Missing required fields
        fields = {
            "party_1_name": ExtractedField(value="Acme", confidence=0.8, evidence=FieldEvidence(page=1, snippet="Acme", source="rule"))
            # Missing party_2_name, effective_date, contract_value, payment_terms
        }

        confidence_summary = ConfidenceSummary(average=0.8, low_count=0, high_confidence_fields=1, total_fields=1)
        gaps = self.extractor._identify_gaps(fields, confidence_summary)

        # Should identify missing required fields
        missing_gaps = [gap for gap in gaps if gap.reason == GapReason.MISSING]
        assert len(missing_gaps) > 0

        # Check that all missing gaps are for required fields
        required_fields = {"party_2_name", "effective_date", "contract_value", "payment_terms"}
        missing_field_names = {gap.field for gap in missing_gaps}
        assert missing_field_names.intersection(required_fields)

    def test_identify_gaps_low_confidence_fields(self):
        from app.models.contract import ExtractedField, FieldEvidence

        fields = {
            "party_1_name": ExtractedField(value="Acme", confidence=0.4, evidence=FieldEvidence(page=1, snippet="Acme", source="rule")),  # Low confidence
            "party_2_name": ExtractedField(value="Vendor", confidence=0.9, evidence=FieldEvidence(page=1, snippet="Vendor", source="rule"))
        }

        confidence_summary = ConfidenceSummary(average=0.65, low_count=1, high_confidence_fields=1, total_fields=2)
        gaps = self.extractor._identify_gaps(fields, confidence_summary)

        # Should identify low confidence field
        low_confidence_gaps = [gap for gap in gaps if gap.reason == GapReason.LOW_CONFIDENCE]
        assert len(low_confidence_gaps) > 0
        assert "party_1_name" in [gap.field for gap in low_confidence_gaps]

    def test_calculate_overall_score_complete_contract(self):
        from app.models.contract import ExtractedField, FieldEvidence

        # Complete set of high-confidence fields
        fields = {
            # Financial (30 points)
            "contract_value": ExtractedField(value=100000, confidence=0.9, evidence=FieldEvidence(page=1, snippet="$100,000", source="rule")),
            "currency": ExtractedField(value="USD", confidence=0.9, evidence=FieldEvidence(page=1, snippet="USD", source="rule")),
            "payment_terms": ExtractedField(value="Net 30", confidence=0.8, evidence=FieldEvidence(page=1, snippet="Net 30", source="rule")),

            # Party identification (25 points)
            "party_1_name": ExtractedField(value="Acme Corp", confidence=0.9, evidence=FieldEvidence(page=1, snippet="Acme Corp", source="rule")),
            "party_2_name": ExtractedField(value="Vendor Inc", confidence=0.9, evidence=FieldEvidence(page=1, snippet="Vendor Inc", source="rule")),
        }

        confidence_summary = ConfidenceSummary(average=0.88, low_count=0, high_confidence_fields=5, total_fields=5)
        gaps = []

        score = self.extractor._calculate_overall_score(fields, gaps, confidence_summary)

        # Should have high score for complete, high-confidence contract
        assert score > 70  # Expecting good score
        assert score <= 100

    def test_calculate_overall_score_with_gaps(self):
        from app.models.contract import ExtractedField, FieldEvidence

        fields = {
            "party_1_name": ExtractedField(value="Acme Corp", confidence=0.9, evidence=FieldEvidence(page=1, snippet="Acme Corp", source="rule"))
        }

        confidence_summary = ConfidenceSummary(average=0.9, low_count=0, high_confidence_fields=1, total_fields=1)

        gaps = [
            ContractGap(field="party_2_name", reason=GapReason.MISSING, severity=GapSeverity.HIGH),
            ContractGap(field="contract_value", reason=GapReason.MISSING, severity=GapSeverity.HIGH),
            ContractGap(field="payment_terms", reason=GapReason.MISSING, severity=GapSeverity.MEDIUM)
        ]

        score = self.extractor._calculate_overall_score(fields, gaps, confidence_summary)

        # Score should be penalized for gaps
        assert score < 50  # Expecting lower score due to missing critical fields

    def test_calculate_category_score(self):
        from app.models.contract import ExtractedField, FieldEvidence

        fields = {
            "field1": ExtractedField(value="test", confidence=0.9, evidence=FieldEvidence(page=1, snippet="test", source="rule")),
            "field2": ExtractedField(value="test", confidence=0.7, evidence=FieldEvidence(page=1, snippet="test", source="rule")),
            "field3": ExtractedField(value="test", confidence=0.4, evidence=FieldEvidence(page=1, snippet="test", source="rule"))  # Low confidence
        }

        category_fields = ["field1", "field2", "field3", "missing_field"]
        max_points = 100

        score = self.extractor._calculate_category_score(fields, category_fields, max_points)

        # 3 found out of 4 fields = 75% presence
        # 2 high confidence out of 4 fields = 50% confidence
        # Score = 75% * 0.6 + 50% * 0.4 = 45% + 20% = 65%
        expected_score = 65.0
        assert abs(score - expected_score) < 1.0

    def test_find_page_number(self):
        pages_data = [
            {"page": 1, "content": "This is page one content"},
            {"page": 2, "content": "This is page two with specific text"},
            {"page": 3, "content": "This is page three"}
        ]

        # Should find correct page
        page_num = self.extractor._find_page_number("specific text", pages_data)
        assert page_num == 2

        # Should default to page 1 if not found
        page_num = self.extractor._find_page_number("nonexistent text", pages_data)
        assert page_num == 1