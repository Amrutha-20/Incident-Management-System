import { relativeTime, priorityColor } from '../../utils/format'

export default function SignalList({ signals = [] }) {
  if (!signals.length) {
    return <div style={{ color: 'var(--text-muted)', fontSize: '12px', padding: '20px', textAlign: 'center' }}>No signals found</div>
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: '2px',
      maxHeight: '340px', overflowY: 'auto',
      background: 'var(--bg-base)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      padding: '4px',
    }}>
      {signals.map((s, i) => (
        <div key={s.signal_id || i} style={{
          display: 'grid',
          gridTemplateColumns: '36px 110px 1fr 100px',
          gap: '10px', alignItems: 'center',
          padding: '6px 10px',
          borderRadius: 'var(--radius-sm)',
          fontSize: '11px',
        }}>
          <span style={{ fontWeight: 700, fontSize: '9px', letterSpacing: '0.05em', color: priorityColor(s.severity) }}>
            {s.severity}
          </span>
          <span style={{ color: 'var(--accent)', fontSize: '10px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {s.error_code}
          </span>
          <span style={{ color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {s.message}
          </span>
          <span style={{ color: 'var(--text-muted)', textAlign: 'right', fontSize: '10px' }}>
            {relativeTime(s.received_at)}
          </span>
        </div>
      ))}
    </div>
  )
}