import { useState, useCallback } from 'react'
import { apiClient, ApiRequestError } from '../lib/apiClient'
import type { AxiosRequestConfig } from 'axios'

export interface ApiError {
  message: string
  status?: number
}

export function useApi<T, E = ApiError>() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<E | null>(null)
  const [data, setData] = useState<T | null>(null)

  const execute = useCallback(
    async (
      method: 'GET' | 'POST' | 'PUT' | 'DELETE',
      endpoint: string,
      payload?: any,
    ): Promise<T | null> => {
      try {
        setIsLoading(true)
        setError(null)

        const config: AxiosRequestConfig = {
          method,
          url: endpoint,
          data: payload,
        }

        const response = await apiClient(config)

        setData(response.data)
        return response.data
      } catch (err) {
        if (err instanceof ApiRequestError) {
          setError({ message: err.message, status: err.status } as E)
        } else {
          const message = err instanceof Error ? err.message : 'An unknown error occurred'
          setError({ message } as E)
        }
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [],
  )

  return { data, isLoading, error, execute }
}
