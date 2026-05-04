import { useState, useEffect, useCallback } from 'react'
import { getIncidents, getHealth } from '../services/api'

export function useIncidents(refreshInterval = 5000) {
  const [incidents, setIncidents] = useState([])
  const [health, setHealth]       = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)

  const fetch = useCallback(async () => {
    try {
      const [inc, hlt] = await Promise.all([getIncidents(), getHealth()])
      setIncidents(inc)
      setHealth(hlt)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
    const id = setInterval(fetch, refreshInterval)
    return () => clearInterval(id)
  }, [fetch, refreshInterval])

  return { incidents, health, loading, error, refetch: fetch }
}