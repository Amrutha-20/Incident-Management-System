import { useState } from 'react'
import { transitionStatus } from '../../services/api'
import { statusColor, nextStatuses } from '../../utils/format'

export default function StatusTransition({ workItemId, currentStatus, onSuccess }) {
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const nexts = nextStatuses(currentStatus)

  const transition = async (s) => {
    setLoading(true)
    setError(null)
    try {
      await transitionStatus(workItemId, { new_status: s })
      onSuccess && onSuccess()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (!nexts.length) {
    return (
      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
        <span style={{ color: 'var(--status-closed)' }}>● CLOSED</span> — Terminal state
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {error && (
        <div style={{ background: 'var(--p0-bg)', color: 'var(--p0)', border: '1px solid var(--p0)', borderRadius: 'var(--radius-sm)', padding: '6px 10px', fontSize: '11px' }}>
          {error}
        </div>
      )}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {nexts.filter(s => s !== 'CLOSED').map(s => (
          <button
            key={s}
            onClick={() => transition(s)}
            disabled={loading}
            style={{
              background: 'transparent',
              border: `1px solid ${statusColor(s)}`,
              color: statusColor(s),
              borderRadius: 'var(--radius-sm)',
              padding: '6px 14px',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px', fontWeight: 700, letterSpacing: '0.06em',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.5 : 1,
              transition: 'all 0.15s',
            }}>
            → {s}
          </button>
        ))}
      </div>
    </div>
  )
}