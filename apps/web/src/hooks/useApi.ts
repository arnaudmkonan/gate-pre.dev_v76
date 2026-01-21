import { useState, useCallback } from 'react'
import axios, { AxiosError } from 'axios'

const API_URL = 'http://localhost:8000'

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

        const response = await axios({
          method,
          url: `${API_URL}${endpoint}`,
          data: payload,
          headers: {
            'Content-Type': 'application/json',
          },
        })

        setData(response.data)
        return response.data
      } catch (err) {
        const apiError = err as AxiosError
        const errorData = (apiError.response?.data as E) || ({ message: apiError.message } as E)
        setError(errorData)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [],
  )

  return { data, isLoading, error, execute }
}
