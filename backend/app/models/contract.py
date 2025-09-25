from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from beanie import Document
from enum import Enum


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FieldEvidence(BaseModel):
    page: int
    snippet: str
    source: str = "rule"  # rule | llm


class ExtractedField(BaseModel):
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: Optional[FieldEvidence] = None


class ContractPage(BaseModel):
    page: int
    content: str


class GapReason(str, Enum):
    MISSING = "missing"
    LOW_CONFIDENCE = "low_confidence"


class GapSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContractGap(BaseModel):
    field: str
    reason: GapReason
    severity: GapSeverity


class ProcessingMetadata(BaseModel):
    ocr_used: bool = False
    llm_used: bool = False
    duration_ms: int = 0
    error_message: Optional[str] = None


class ConfidenceSummary(BaseModel):
    average: float = 0.0
    low_count: int = 0
    high_confidence_fields: int = 0
    total_fields: int = 0


class Contract(Document):
    # File metadata
    filename: str
    hash: str
    mime_type: str = "application/pdf"
    size_bytes: int
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    # Processing status
    status: ProcessingStatus = ProcessingStatus.PENDING
    processing_progress: int = Field(default=0, ge=0, le=100)

    # Extracted text
    text: Dict[str, List[ContractPage]] = Field(default_factory=lambda: {"pages": []})

    # Extracted fields
    fields: Dict[str, ExtractedField] = Field(default_factory=dict)

    # Gap analysis
    gaps: List[ContractGap] = Field(default_factory=list)

    # Confidence summary
    confidence_summary: ConfidenceSummary = Field(default_factory=ConfidenceSummary)

    # Processing metadata
    processing: ProcessingMetadata = Field(default_factory=ProcessingMetadata)

    # Scoring (0-100)
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0)

    class Settings:
        name = "contracts"
        indexes = [
            [("filename", 1)],
            [("status", 1)],
            [("uploaded_at", -1)],
            [("hash", 1)]
        ]


class ContractCreate(BaseModel):
    filename: str
    size_bytes: int
    hash: str


class ContractUpdate(BaseModel):
    fields: Optional[Dict[str, ExtractedField]] = None
    gaps: Optional[List[ContractGap]] = None
    confidence_summary: Optional[ConfidenceSummary] = None
    overall_score: Optional[float] = None


class ContractResponse(BaseModel):
    id: str
    filename: str
    status: ProcessingStatus
    processing_progress: int
    uploaded_at: datetime
    size_bytes: int
    mime_type: str
    overall_score: float
    confidence_summary: ConfidenceSummary
    gaps: List[ContractGap]
    fields: Dict[str, ExtractedField]
    processing: ProcessingMetadata


class ContractListResponse(BaseModel):
    total: int
    page: int
    limit: int
    contracts: List[ContractResponse]