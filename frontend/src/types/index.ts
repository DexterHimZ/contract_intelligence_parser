export type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface FieldEvidence {
  page: number
  snippet: string
  source: 'rule' | 'llm'
}

export interface ExtractedField {
  value: any
  confidence: number
  evidence?: FieldEvidence
}

export interface ContractGap {
  field: string
  reason: 'missing' | 'low_confidence'
  severity: 'high' | 'medium' | 'low'
}

export interface ConfidenceSummary {
  average: number
  low_count: number
  high_confidence_fields: number
  total_fields: number
}

export interface ProcessingMetadata {
  ocr_used: boolean
  llm_used: boolean
  duration_ms: number
  error_message?: string
}

export interface Contract {
  id: string
  filename: string
  status: ProcessingStatus
  processing_progress: number
  uploaded_at: string
  size_bytes: number
  mime_type: string
  overall_score: number
  confidence_summary: ConfidenceSummary
  gaps: ContractGap[]
  fields: Record<string, ExtractedField>
  processing: ProcessingMetadata
}

export interface ContractListResponse {
  total: number
  page: number
  limit: number
  contracts: Contract[]
}

export interface UploadResponse {
  contract_id: string
  message: string
  status: ProcessingStatus
}

export interface ProcessingStatusResponse {
  contract_id: string
  status: ProcessingStatus
  progress: number
  error_message?: string
}