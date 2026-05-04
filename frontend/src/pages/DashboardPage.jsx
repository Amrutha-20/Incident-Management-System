import { useIncidents } from '../hooks/useIncidents'
import HealthBar from '../components/dashboard/HealthBar'
import LiveFeed from '../components/dashboard/LiveFeed'

export default function DashboardPage() {
  const { incidents, health, loading, error, refetch } = useIncidents(5000)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <HealthBar health={health} />
      <div style={{ padding: '24px', flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
          <div>
            <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '22px', fontWeight: 800, color: 'var(--text-primary)' }}>
              Live Incident Feed
            </h1>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Auto-refreshes every 5 seconds
            </p>
          </div>
          <button
            onClick={refetch}
            style={{
              background: 'var(--bg-raised)', border: '1px solid var(--border)',
              color: 'var(--text-secondary)', borderRadius: 'var(--radius-sm)',
              padding: '6px 12px', fontFamily: 'var(--font-mono)',
              fontSize: '11px', cursor: 'pointer',
            }}>
            ↻ Refresh
          </button>
        </div>

        {error && (
          <div style={{ background: 'var(--p0-bg)', color: 'var(--p0)', border: '1px solid var(--p0)', borderRadius: 'var(--radius-sm)', padding: '10px 14px', fontSize: '12px', marginBottom: '16px' }}>
            ⚠ {error}
          </div>
        )}

        <LiveFeed incidents={incidents} loading={loading} />
      </div>
    </div>
  )
}