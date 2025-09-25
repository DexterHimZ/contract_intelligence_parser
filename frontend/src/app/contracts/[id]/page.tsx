'use client'

import React from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  Download,
  AlertTriangle,
  CheckCircle,
  Clock,
  FileText,
  Users,
  Calendar,
  DollarSign,
  Scale,
  Shield,
  RefreshCw
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { contractsApi } from '@/lib/api'
import { formatDate, formatFileSize, cn } from '@/lib/utils'
import { Contract, ExtractedField } from '@/types'

export default function ContractDetailPage() {
  const params = useParams()
  const router = useRouter()
  const contractId = params.id as string

  const { data: contract, isLoading, error, refetch } = useQuery({
    queryKey: ['contract', contractId],
    queryFn: () => contractsApi.getContract(contractId),
    refetchInterval: (query) => {
      return query.state.data?.status === 'processing' ? 5000 : false
    }
  })

  const handleDownload = async () => {
    if (!contract) return
    try {
      const blob = await contractsApi.downloadContract(contract.id)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = contract.filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Download failed:', error)
    }
  }

  const handleReprocess = async () => {
    if (!contract) return
    try {
      await contractsApi.reprocessContract(contract.id, { use_ocr: true })
      refetch()
    } catch (error) {
      console.error('Reprocess failed:', error)
    }
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-50 border-green-200'
    if (confidence >= 0.6) return 'text-yellow-600 bg-yellow-50 border-yellow-200'
    return 'text-red-600 bg-red-50 border-red-200'
  }

  const formatFieldValue = (field: ExtractedField) => {
    if (field.value === null || field.value === undefined) return 'N/A'
    if (typeof field.value === 'boolean') return field.value ? 'Yes' : 'No'
    if (typeof field.value === 'number') return field.value.toLocaleString()
    return String(field.value)
  }

  const getFieldsByCategory = (fields: Record<string, ExtractedField>) => {
    const categories = {
      parties: ['party_1_name', 'party_2_name'],
      dates: ['effective_date', 'execution_date', 'termination_date', 'renewal_term', 'auto_renewal', 'notice_period'],
      financial: ['contract_value', 'currency', 'payment_terms', 'billing_frequency'],
      legal: ['governing_law', 'liability_cap', 'confidentiality', 'termination_for_convenience', 'termination_for_cause'],
      sla: ['sla_uptime', 'support_hours']
    }

    return Object.entries(categories).reduce((acc, [category, fieldNames]) => {
      acc[category] = fieldNames.map(name => ({ name, field: fields[name] })).filter(({ field }) => field)
      return acc
    }, {} as Record<string, Array<{ name: string; field: ExtractedField }>>)
  }

  const formatFieldName = (fieldName: string) => {
    return fieldName
      .replace(/_/g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase())
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
      </div>
    )
  }

  if (error || !contract) {
    return (
      <div className="text-center space-y-4">
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto" />
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Contract not found</h3>
          <p className="text-sm text-gray-500 mt-1">The contract may have been deleted or the ID is invalid</p>
          <Button className="mt-4" onClick={() => router.push('/contracts')}>
            Back to Contracts
          </Button>
        </div>
      </div>
    )
  }

  const fieldsByCategory = getFieldsByCategory(contract.fields)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Button variant="outline" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{contract.filename}</h1>
            <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
              <span>Uploaded {formatDate(contract.uploaded_at)}</span>
              <span>{formatFileSize(contract.size_bytes)}</span>
              <div className="flex items-center gap-2">
                {contract.status === 'completed' && <CheckCircle className="h-4 w-4 text-green-500" />}
                {contract.status === 'processing' && <Clock className="h-4 w-4 text-blue-500" />}
                {contract.status === 'failed' && <AlertTriangle className="h-4 w-4 text-red-500" />}
                <Badge variant={
                  contract.status === 'completed' ? 'default' :
                  contract.status === 'failed' ? 'destructive' : 'secondary'
                }>
                  {contract.status}
                </Badge>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {contract.status === 'completed' && (
            <Button variant="outline" onClick={handleReprocess}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Reprocess
            </Button>
          )}
          <Button variant="outline" onClick={handleDownload}>
            <Download className="h-4 w-4 mr-2" />
            Download
          </Button>
        </div>
      </div>

      {/* Processing Status */}
      {contract.status === 'processing' && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Processing Contract...</span>
                <span className="text-sm text-gray-500">{contract.processing_progress}%</span>
              </div>
              <Progress value={contract.processing_progress} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error State */}
      {contract.status === 'failed' && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-red-500 mt-1" />
              <div>
                <h3 className="font-semibold text-red-900">Processing Failed</h3>
                <p className="text-red-700 text-sm mt-1">
                  {contract.processing.error_message || 'An error occurred during processing'}
                </p>
                <Button className="mt-3" size="sm" onClick={handleReprocess}>
                  Try Again
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards */}
      {contract.status === 'completed' && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Overall Score</p>
                  <p className="text-2xl font-bold">{Math.round(contract.overall_score)}/100</p>
                </div>
                <div className={cn('p-2 rounded-full', getConfidenceColor(contract.overall_score / 100))}>
                  <CheckCircle className="h-4 w-4" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Fields Extracted</p>
                  <p className="text-2xl font-bold">{contract.confidence_summary.total_fields}</p>
                </div>
                <FileText className="h-8 w-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">High Confidence</p>
                  <p className="text-2xl font-bold">{contract.confidence_summary.high_confidence_fields}</p>
                </div>
                <CheckCircle className="h-8 w-8 text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Gaps Identified</p>
                  <p className="text-2xl font-bold">{contract.gaps.length}</p>
                </div>
                <AlertTriangle className={cn('h-8 w-8', contract.gaps.length > 0 ? 'text-red-500' : 'text-gray-400')} />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Gaps */}
      {contract.status === 'completed' && contract.gaps.length > 0 && (
        <Card className="border-orange-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-orange-900">
              <AlertTriangle className="h-5 w-5" />
              Identified Gaps
            </CardTitle>
            <CardDescription>
              These fields are missing or have low confidence scores
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {contract.gaps.map((gap, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                  <div>
                    <p className="font-medium text-orange-900">{formatFieldName(gap.field)}</p>
                    <p className="text-sm text-orange-700">
                      {gap.reason === 'missing' ? 'Field not found' : 'Low confidence extraction'}
                    </p>
                  </div>
                  <Badge variant={gap.severity === 'high' ? 'destructive' : 'secondary'}>
                    {gap.severity} severity
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Extracted Fields */}
      {contract.status === 'completed' && Object.keys(contract.fields).length > 0 && (
        <div className="space-y-6">
          {/* Party Information */}
          {fieldsByCategory.parties.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Party Information
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4">
                  {fieldsByCategory.parties.map(({ name, field }) => (
                    <div key={name} className="flex items-start justify-between p-4 border rounded-lg">
                      <div className="flex-1">
                        <h4 className="font-medium">{formatFieldName(name)}</h4>
                        <p className="text-gray-600 mt-1">{formatFieldValue(field)}</p>
                        {field.evidence && (
                          <p className="text-xs text-gray-500 mt-2">
                            Page {field.evidence.page}: "{field.evidence.snippet}"
                          </p>
                        )}
                      </div>
                      <div className={cn('px-2 py-1 rounded text-xs font-medium border', getConfidenceColor(field.confidence))}>
                        {Math.round(field.confidence * 100)}%
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Financial Terms */}
          {fieldsByCategory.financial.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5" />
                  Financial Terms
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4">
                  {fieldsByCategory.financial.map(({ name, field }) => (
                    <div key={name} className="flex items-start justify-between p-4 border rounded-lg">
                      <div className="flex-1">
                        <h4 className="font-medium">{formatFieldName(name)}</h4>
                        <p className="text-gray-600 mt-1">{formatFieldValue(field)}</p>
                        {field.evidence && (
                          <p className="text-xs text-gray-500 mt-2">
                            Page {field.evidence.page}: "{field.evidence.snippet}"
                          </p>
                        )}
                      </div>
                      <div className={cn('px-2 py-1 rounded text-xs font-medium border', getConfidenceColor(field.confidence))}>
                        {Math.round(field.confidence * 100)}%
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Important Dates */}
          {fieldsByCategory.dates.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="h-5 w-5" />
                  Important Dates
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4">
                  {fieldsByCategory.dates.map(({ name, field }) => (
                    <div key={name} className="flex items-start justify-between p-4 border rounded-lg">
                      <div className="flex-1">
                        <h4 className="font-medium">{formatFieldName(name)}</h4>
                        <p className="text-gray-600 mt-1">{formatFieldValue(field)}</p>
                        {field.evidence && (
                          <p className="text-xs text-gray-500 mt-2">
                            Page {field.evidence.page}: "{field.evidence.snippet}"
                          </p>
                        )}
                      </div>
                      <div className={cn('px-2 py-1 rounded text-xs font-medium border', getConfidenceColor(field.confidence))}>
                        {Math.round(field.confidence * 100)}%
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Legal Terms */}
          {fieldsByCategory.legal.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Scale className="h-5 w-5" />
                  Legal Terms
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4">
                  {fieldsByCategory.legal.map(({ name, field }) => (
                    <div key={name} className="flex items-start justify-between p-4 border rounded-lg">
                      <div className="flex-1">
                        <h4 className="font-medium">{formatFieldName(name)}</h4>
                        <p className="text-gray-600 mt-1">{formatFieldValue(field)}</p>
                        {field.evidence && (
                          <p className="text-xs text-gray-500 mt-2">
                            Page {field.evidence.page}: "{field.evidence.snippet}"
                          </p>
                        )}
                      </div>
                      <div className={cn('px-2 py-1 rounded text-xs font-medium border', getConfidenceColor(field.confidence))}>
                        {Math.round(field.confidence * 100)}%
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Service Level Agreements */}
          {fieldsByCategory.sla.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  Service Level Agreements
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4">
                  {fieldsByCategory.sla.map(({ name, field }) => (
                    <div key={name} className="flex items-start justify-between p-4 border rounded-lg">
                      <div className="flex-1">
                        <h4 className="font-medium">{formatFieldName(name)}</h4>
                        <p className="text-gray-600 mt-1">{formatFieldValue(field)}</p>
                        {field.evidence && (
                          <p className="text-xs text-gray-500 mt-2">
                            Page {field.evidence.page}: "{field.evidence.snippet}"
                          </p>
                        )}
                      </div>
                      <div className={cn('px-2 py-1 rounded text-xs font-medium border', getConfidenceColor(field.confidence))}>
                        {Math.round(field.confidence * 100)}%
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Processing Metadata */}
      {contract.status === 'completed' && (
        <Card>
          <CardHeader>
            <CardTitle>Processing Information</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="font-medium text-gray-900">Processing Time</p>
                <p className="text-gray-600">{(contract.processing.duration_ms / 1000).toFixed(2)}s</p>
              </div>
              <div>
                <p className="font-medium text-gray-900">OCR Used</p>
                <p className="text-gray-600">{contract.processing.ocr_used ? 'Yes' : 'No'}</p>
              </div>
              <div>
                <p className="font-medium text-gray-900">LLM Enhanced</p>
                <p className="text-gray-600">{contract.processing.llm_used ? 'Yes' : 'No'}</p>
              </div>
              <div>
                <p className="font-medium text-gray-900">Average Confidence</p>
                <p className="text-gray-600">{Math.round(contract.confidence_summary.average * 100)}%</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}