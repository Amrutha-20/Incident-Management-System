import { useState, useEffect, useCallback } from 'react'
import { getIncidentDetail } from '../services/api'

export function useIncidentDetail(id) {
  const [detail, setDetail]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  const fetch = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const data = await getIncidentDetail(id)
      setDetail(data)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { fetch() }, [fetch])

  return { detail, loading, error, refetch: fetch }
}