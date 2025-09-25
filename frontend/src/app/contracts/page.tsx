'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import {
  FileText,
  Clock,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Download,
  Search,
  Filter
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { contractsApi } from '@/lib/api'
import { formatDate, formatFileSize, getStatusColor, getConfidenceBadgeVariant } from '@/lib/utils'
import { Contract, ProcessingStatus } from '@/types'

export default function ContractsPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<ProcessingStatus | ''>('')
  const [sortBy, setSortBy] = useState('uploaded_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  const { data: contractsData, isLoading, error, refetch } = useQuery({
    queryKey: ['contracts', page, statusFilter, sortBy, sortOrder],
    queryFn: () => contractsApi.listContracts({
      page,
      limit: 10,
      status: statusFilter || undefined,
      sort_by: sortBy,
      sort_order: sortOrder
    }),
    refetchInterval: (query) => {
      // Refetch every 5 seconds if there are processing contracts
      const hasProcessing = query.state.data?.contracts?.some(c => c.status === 'processing') ?? false
      return hasProcessing ? 5000 : false
    }
  })

  const getStatusIcon = (status: ProcessingStatus) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'processing':
        return <Clock className="h-4 w-4 text-blue-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <Clock className="h-4 w-4 text-gray-500" />
    }
  }

  const handleDownload = async (contract: Contract) => {
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

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center space-y-4">
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto" />
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Failed to load contracts</h3>
          <p className="text-sm text-gray-500 mt-1">Please try again later</p>
          <Button className="mt-4" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Contracts</h1>
          <p className="text-gray-600 mt-1">
            {contractsData?.total || 0} contract{contractsData?.total !== 1 ? 's' : ''} uploaded
          </p>
        </div>
        <Link href="/">
          <Button>
            <FileText className="h-4 w-4 mr-2" />
            Upload New Contract
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4" />
              <span className="font-medium">Filters</span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as ProcessingStatus | '')}
                className="border rounded-md px-3 py-2 text-sm"
              >
                <option value="">All statuses</option>
                <option value="pending">Pending</option>
                <option value="processing">Processing</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Sort by</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="border rounded-md px-3 py-2 text-sm"
              >
                <option value="uploaded_at">Upload Date</option>
                <option value="overall_score">Score</option>
                <option value="filename">Filename</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Order</label>
              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')}
                className="border rounded-md px-3 py-2 text-sm"
              >
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Contracts List */}
      {contractsData?.contracts.length === 0 ? (
        <Card>
          <CardContent className="text-center py-12">
            <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900">No contracts found</h3>
            <p className="text-gray-500 mt-1 mb-4">
              {statusFilter ? 'No contracts match the current filter' : 'Upload your first contract to get started'}
            </p>
            <Link href="/">
              <Button>Upload Contract</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {contractsData?.contracts.map((contract) => (
            <Card key={contract.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Link
                        href={`/contracts/${contract.id}`}
                        className="text-lg font-semibold text-gray-900 hover:text-primary"
                      >
                        {contract.filename}
                      </Link>
                      {getStatusIcon(contract.status)}
                      <Badge variant={
                        contract.status === 'completed' ? 'default' :
                        contract.status === 'failed' ? 'destructive' : 'secondary'
                      }>
                        {contract.status}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-6 text-sm text-gray-500 mb-3">
                      <span>Uploaded {formatDate(contract.uploaded_at)}</span>
                      <span>{formatFileSize(contract.size_bytes)}</span>
                      {contract.status === 'completed' && (
                        <span>Score: {Math.round(contract.overall_score)}/100</span>
                      )}
                    </div>

                    {contract.status === 'processing' && (
                      <div className="mb-3">
                        <div className="flex items-center justify-between text-sm mb-1">
                          <span>Processing...</span>
                          <span>{contract.processing_progress}%</span>
                        </div>
                        <Progress value={contract.processing_progress} />
                      </div>
                    )}

                    {contract.status === 'completed' && (
                      <div className="flex items-center gap-4 text-sm">
                        <span className="text-gray-600">
                          Fields extracted: {contract.confidence_summary.total_fields}
                        </span>
                        <span className="text-gray-600">
                          High confidence: {contract.confidence_summary.high_confidence_fields}
                        </span>
                        {contract.gaps.length > 0 && (
                          <Badge variant="destructive" className="text-xs">
                            {contract.gaps.length} gap{contract.gaps.length !== 1 ? 's' : ''}
                          </Badge>
                        )}
                      </div>
                    )}

                    {contract.status === 'failed' && contract.processing.error_message && (
                      <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                        {contract.processing.error_message}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDownload(contract)}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                    <Link href={`/contracts/${contract.id}`}>
                      <Button size="sm">
                        View Details
                      </Button>
                    </Link>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination */}
      {contractsData && contractsData.total > 10 && (
        <div className="flex justify-center items-center gap-4">
          <Button
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>

          <span className="text-sm text-gray-600">
            Page {page} of {Math.ceil(contractsData.total / 10)}
          </span>

          <Button
            variant="outline"
            disabled={page >= Math.ceil(contractsData.total / 10)}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}