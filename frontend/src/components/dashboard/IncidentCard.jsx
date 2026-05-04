import { useNavigate } from 'react-router-dom'
import { ChevronRight, Signal } from 'lucide-react'
import { relativeTime, priorityColor, priorityBg, statusColor } from '../../utils/format'

export default function IncidentCard({ incident }) {
  const nav = useNavigate()

  return (
    <div
      onClick={() => nav('/incidents/' + incident.work_item_id)}
      style={{
        display: 'flex',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${priorityColor(incident.priority)}`,
        borderRadius: 'var(--radius-md)',
        cursor: 'pointer',
        transition: 'all 0.15s',
        overflow: 'hidden',
        animation: 'slide-in 0.25s ease both',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'var(--bg-raised)'
        e.currentTarget.style.transform = 'translateX(2px)'
        e.currentTarget.style.boxShadow = 'var(--shadow-md)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'var(--bg-surface)'
        e.currentTarget.style.transform = 'translateX(0)'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      {/* Priority badge */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minWidth: '44px',
        background: priorityBg(incident.priority),
        color: priorityColor(incident.priority),
        fontSize: '10px', fontWeight: 700, letterSpacing: '0.06em',
        writingMode: 'vertical-lr', transform: 'rotate(180deg)',
        padding: '8px 4px',
      }}>
        {incident.priority}
      </div>

      {/* Body */}
      <div style={{ flex: 1, padding: '10px 12px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: '5px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
          <span style={{
            fontFamily: 'var(--font-display)', fontSize: '13px', fontWeight: 600,
            color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {incident.title}
          </span>
          <ChevronRight size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', color: 'var(--accent)' }}>{incident.component_id}</span>
          <span style={{
            fontSize: '9px', color: 'var(--text-muted)',
            background: 'var(--bg-overlay)', padding: '1px 5px',
            borderRadius: '2px', letterSpacing: '0.05em',
          }}>{incident.component_type}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '10px', fontWeight: 700, color: statusColor(incident.status) }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: statusColor(incident.status), display: 'inline-block' }} />
            {incident.status}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px', color: 'var(--text-muted)' }}>
            <Signal size={10} /> {incident.signal_ids?.length || 0} signals
          </span>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
            {relativeTime(incident.created_at)}
          </span>
        </div>
      </div>
    </div>
  )
}