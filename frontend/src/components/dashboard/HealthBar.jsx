export default function HealthBar({ health }) {
  if (!health) return null
  const ok = health.status === 'ok'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '24px',
      padding: '10px 20px', background: 'var(--bg-surface)',
      borderBottom: '1px solid var(--border)', flexWrap: 'wrap',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%', display: 'inline-block',
          background: ok ? 'var(--green)' : 'var(--p0)',
          boxShadow: ok ? '0 0 6px var(--green)' : '0 0 6px var(--p0)',
          animation: 'pulse-dot 2s infinite',
        }} />
        <span style={{ fontSize: '10px', letterSpacing: '0.1em', color: 'var(--text-secondary)' }}>
          {ok ? 'ALL SYSTEMS NOMINAL' : 'DEGRADED'}
        </span>
      </div>

      {[
        { val: health.signals_per_sec?.toFixed(1), lbl: 'sig/sec' },
        { val: health.buffer_utilization_pct?.toFixed(1) + '%', lbl: 'buffer' },
        { val: health.active_work_items, lbl: 'active' },
        { val: Math.round(health.uptime_seconds) + 's', lbl: 'uptime' },
      ].map(({ val, lbl }) => (
        <div key={lbl} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1px' }}>
          <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>{val}</span>
          <span style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{lbl}</span>
        </div>
      ))}

      <div style={{ display: 'flex', gap: '6px', marginLeft: 'auto', flexWrap: 'wrap' }}>
        {Object.entries(health.checks || {}).map(([k, v]) => {
          const isOk = v === 'ok'
          const isWarn = v.startsWith('warning')
          return (
            <span key={k} style={{
              fontSize: '9px', padding: '2px 7px', borderRadius: '2px',
              textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700,
              background: isOk ? 'var(--green-dim)' : isWarn ? 'var(--p2-bg)' : 'var(--p0-bg)',
              color: isOk ? 'var(--green)' : isWarn ? 'var(--p2)' : 'var(--p0)',
            }}>{k}</span>
          )
        })}
      </div>
    </div>
  )
}