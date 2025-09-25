import axios from 'axios'
import { Contract, ContractListResponse, UploadResponse, ProcessingStatusResponse } from '@/types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 30000,
})

// Request interceptor for logging
api.interceptors.request.use((config) => {
  console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`)
  return config
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export const contractsApi = {
  // Upload contract
  uploadContract: async (file: File): Promise<UploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)

    const response = await api.post('/contracts/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // Get processing status
  getProcessingStatus: async (contractId: string): Promise<ProcessingStatusResponse> => {
    const response = await api.get(`/contracts/${contractId}/status`)
    return response.data
  },

  // Get contract details
  getContract: async (contractId: string): Promise<Contract> => {
    const response = await api.get(`/contracts/${contractId}`)
    return response.data
  },

  // List contracts
  listContracts: async (params: {
    page?: number
    limit?: number
    status?: string
    sort_by?: string
    sort_order?: 'asc' | 'desc'
  } = {}): Promise<ContractListResponse> => {
    const response = await api.get('/contracts', { params })
    return response.data
  },

  // Download contract
  downloadContract: async (contractId: string): Promise<Blob> => {
    const response = await api.get(`/contracts/${contractId}/download`, {
      responseType: 'blob',
    })
    return response.data
  },

  // Reprocess contract
  reprocessContract: async (
    contractId: string,
    options: { use_ocr?: boolean; use_llm?: boolean } = {}
  ): Promise<{ message: string }> => {
    const response = await api.post(`/contracts/${contractId}/reprocess`, null, {
      params: options,
    })
    return response.data
  },

  // Delete contract
  deleteContract: async (contractId: string): Promise<{ message: string }> => {
    const response = await api.delete(`/contracts/${contractId}`)
    return response.data
  },
}

export const healthApi = {
  checkHealth: async () => {
    const response = await api.get('/health')
    return response.data
  },
}

export default api