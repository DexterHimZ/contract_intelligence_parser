'use client'

import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation } from '@tanstack/react-query'
import { Upload, FileText, AlertCircle, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { contractsApi } from '@/lib/api'
import { formatFileSize } from '@/lib/utils'
import { UploadResponse } from '@/types'

interface FileUploadProps {
  onUploadSuccess?: (response: UploadResponse) => void
  onUploadError?: (error: string) => void
}

export function FileUpload({ onUploadSuccess, onUploadError }: FileUploadProps) {
  const [uploadProgress, setUploadProgress] = useState(0)

  const uploadMutation = useMutation({
    mutationFn: contractsApi.uploadContract,
    onSuccess: (response) => {
      setUploadProgress(100)
      onUploadSuccess?.(response)
    },
    onError: (error: any) => {
      const message = error?.response?.data?.detail || error.message || 'Upload failed'
      onUploadError?.(message)
    },
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      setUploadProgress(10)
      uploadMutation.mutate(file)
    }
  }, [uploadMutation])

  const { getRootProps, getInputProps, isDragActive, acceptedFiles, fileRejections } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024, // 50MB
  })

  return (
    <Card className="w-full max-w-2xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Upload className="h-5 w-5" />
          Upload Contract
        </CardTitle>
        <CardDescription>
          Upload a PDF contract for automated analysis and data extraction
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div
          {...getRootProps()}
          className={`
            relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
            ${isDragActive ? 'border-primary bg-primary/5' : 'border-gray-300 hover:border-gray-400'}
            ${uploadMutation.isPending ? 'pointer-events-none opacity-75' : ''}
          `}
        >
          <input {...getInputProps()} />

          <div className="space-y-4">
            {uploadMutation.isPending ? (
              <div className="space-y-3">
                <div className="flex justify-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                </div>
                <p className="text-sm text-gray-600">Uploading and processing...</p>
                <Progress value={uploadProgress} className="w-full" />
              </div>
            ) : uploadMutation.isSuccess ? (
              <div className="space-y-3">
                <CheckCircle className="h-12 w-12 text-green-500 mx-auto" />
                <p className="text-sm text-green-600 font-medium">
                  Contract uploaded successfully!
                </p>
                <Badge variant="default">Processing started</Badge>
              </div>
            ) : uploadMutation.isError ? (
              <div className="space-y-3">
                <AlertCircle className="h-12 w-12 text-red-500 mx-auto" />
                <p className="text-sm text-red-600 font-medium">
                  Upload failed
                </p>
                <p className="text-xs text-red-500">
                  {uploadMutation.error?.message || 'Please try again'}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => uploadMutation.reset()}
                >
                  Try Again
                </Button>
              </div>
            ) : (
              <>
                {isDragActive ? (
                  <>
                    <Upload className="h-12 w-12 text-primary mx-auto" />
                    <p className="text-lg font-medium text-primary">Drop the PDF here</p>
                  </>
                ) : (
                  <>
                    <FileText className="h-12 w-12 text-gray-400 mx-auto" />
                    <div>
                      <p className="text-lg font-medium text-gray-900">
                        Drag and drop a PDF contract
                      </p>
                      <p className="text-sm text-gray-500 mt-1">
                        or click to browse your files
                      </p>
                    </div>
                    <div className="flex justify-center">
                      <Button variant="outline">
                        Choose File
                      </Button>
                    </div>
                  </>
                )}

                <div className="text-xs text-gray-500 space-y-1">
                  <p>Supported format: PDF only</p>
                  <p>Maximum file size: 50MB</p>
                </div>
              </>
            )}
          </div>
        </div>

        {/* File validation errors */}
        {fileRejections.length > 0 && (
          <div className="mt-4 space-y-2">
            {fileRejections.map(({ file, errors }) => (
              <div key={file.name} className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="text-sm font-medium text-red-800">{file.name}</p>
                <ul className="text-xs text-red-600 mt-1">
                  {errors.map((error) => (
                    <li key={error.code}>{error.message}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {/* Accepted files preview */}
        {acceptedFiles.length > 0 && !uploadMutation.isPending && !uploadMutation.isSuccess && (
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-900 mb-2">Ready to upload:</h4>
            {acceptedFiles.map((file) => (
              <div key={file.name} className="flex items-center justify-between bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-3">
                  <FileText className="h-5 w-5 text-red-500" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{file.name}</p>
                    <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}