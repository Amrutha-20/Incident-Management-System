import IncidentCard from './IncidentCard'

const PRIORITY_ORDER = { P0: 0, P1: 1, P2: 2, P3: 3 }

export default function LiveFeed({ incidents, loading }) {
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '60px', color: 'var(--text-muted)', fontSize: '13px' }}>
        Loading incidents...
      </div>
    )
  }

  if (!incidents.length) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '60px', color: 'var(--text-secondary)', fontSize: '13px' }}>
        <span style={{ fontSize: '32px' }}>✓</span>
        <span>No active incidents</span>
        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>All systems operational</span>
      </div>
    )
  }

  const sorted = [...incidents].sort((a, b) =>
    (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9)
  )

  const byPriority = sorted.reduce((acc, inc) => {
    ;(acc[inc.priority] = acc[inc.priority] || []).push(inc)
    return acc
  }, {})

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {Object.entries(byPriority).map(([p, items]) => (
        <div key={p} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', padding: '0 2px' }}>
            {p} — {items.length} incident{items.length !== 1 ? 's' : ''}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {items.map(inc => <IncidentCard key={inc.work_item_id} incident={inc} />)}
          </div>
        </div>
      ))}
    </div>
  )
}