'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import { FileUpload } from '@/components/file-upload'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ArrowRight, CheckCircle, Clock, FileText, Zap } from 'lucide-react'
import { UploadResponse } from '@/types'

export default function UploadPage() {
  const router = useRouter()
  const [lastUpload, setLastUpload] = useState<UploadResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleUploadSuccess = (response: UploadResponse) => {
    setLastUpload(response)
    setError(null)
  }

  const handleUploadError = (errorMessage: string) => {
    setError(errorMessage)
    setLastUpload(null)
  }

  const handleViewContract = () => {
    if (lastUpload?.contract_id) {
      router.push(`/contracts/${lastUpload.contract_id}`)
    }
  }

  const handleViewAllContracts = () => {
    router.push('/contracts')
  }

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold text-gray-900">
          Contract Intelligence Platform
        </h1>
        <p className="text-xl text-gray-600 max-w-3xl mx-auto">
          Upload your PDF contracts and let our AI-powered system extract key business terms,
          identify gaps, and provide confidence scores for critical information.
        </p>
      </div>

      {/* Features */}
      <div className="grid md:grid-cols-3 gap-6 mb-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Zap className="h-5 w-5 text-blue-500" />
              Fast Processing
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription>
              Advanced OCR and regex-based extraction processes contracts in seconds
            </CardDescription>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <CheckCircle className="h-5 w-5 text-green-500" />
              High Accuracy
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription>
              Confidence scoring system helps identify reliable extractions and potential gaps
            </CardDescription>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <FileText className="h-5 w-5 text-purple-500" />
              Comprehensive Analysis
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription>
              Extracts parties, financial terms, payment schedules, and legal clauses
            </CardDescription>
          </CardContent>
        </Card>
      </div>

      {/* Upload Section */}
      <div className="flex justify-center">
        <FileUpload
          onUploadSuccess={handleUploadSuccess}
          onUploadError={handleUploadError}
        />
      </div>

      {/* Success/Error Messages */}
      {lastUpload && (
        <div className="flex justify-center">
          <Card className="w-full max-w-2xl bg-green-50 border-green-200">
            <CardContent className="pt-6">
              <div className="text-center space-y-4">
                <CheckCircle className="h-12 w-12 text-green-500 mx-auto" />
                <div>
                  <h3 className="text-lg font-semibold text-green-900">
                    Upload Successful!
                  </h3>
                  <p className="text-sm text-green-700 mt-1">
                    {lastUpload.message}
                  </p>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <Badge variant="secondary">
                    <Clock className="h-3 w-3 mr-1" />
                    {lastUpload.status}
                  </Badge>
                </div>
                <div className="flex gap-3 justify-center">
                  <Button onClick={handleViewContract}>
                    View Contract
                    <ArrowRight className="h-4 w-4 ml-1" />
                  </Button>
                  <Button variant="outline" onClick={handleViewAllContracts}>
                    View All Contracts
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {error && (
        <div className="flex justify-center">
          <Card className="w-full max-w-2xl bg-red-50 border-red-200">
            <CardContent className="pt-6">
              <div className="text-center space-y-4">
                <div>
                  <h3 className="text-lg font-semibold text-red-900">
                    Upload Failed
                  </h3>
                  <p className="text-sm text-red-700 mt-1">
                    {error}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* What's Extracted */}
      <Card className="max-w-4xl mx-auto">
        <CardHeader>
          <CardTitle>What We Extract</CardTitle>
          <CardDescription>
            Our system automatically identifies and extracts these key contract elements
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-semibold text-gray-900 mb-3">Party Information</h4>
              <ul className="text-sm text-gray-600 space-y-1">
                <li>• Contract parties and roles</li>
                <li>• Authorized signatories</li>
                <li>• Legal entity names</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-3">Financial Terms</h4>
              <ul className="text-sm text-gray-600 space-y-1">
                <li>• Contract value and currency</li>
                <li>• Payment terms and schedules</li>
                <li>• Billing frequency</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-3">Legal Clauses</h4>
              <ul className="text-sm text-gray-600 space-y-1">
                <li>• Governing law and jurisdiction</li>
                <li>• Liability caps and limitations</li>
                <li>• Confidentiality provisions</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-3">Important Dates</h4>
              <ul className="text-sm text-gray-600 space-y-1">
                <li>• Effective and termination dates</li>
                <li>• Auto-renewal clauses</li>
                <li>• Notice periods</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}