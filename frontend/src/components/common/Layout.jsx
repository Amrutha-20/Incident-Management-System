import { Outlet, NavLink } from 'react-router-dom'
import { Activity, Radio, Zap } from 'lucide-react'

const styles = {
  layout: {
    display: 'flex',
    minHeight: '100vh',
  },
  sidebar: {
    width: '200px',
    minWidth: '200px',
    background: 'var(--bg-surface)',
    borderRight: '1px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    position: 'sticky',
    top: 0,
    height: '100vh',
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '20px 16px',
    borderBottom: '1px solid var(--border)',
  },
  brandIcon: {
    fontSize: '22px',
    color: 'var(--accent)',
    lineHeight: 1,
  },
  brandName: {
    fontFamily: 'var(--font-display)',
    fontWeight: 800,
    fontSize: '16px',
    letterSpacing: '0.05em',
    color: 'var(--text-primary)',
  },
  brandSub: {
    fontSize: '9px',
    color: 'var(--text-muted)',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
    padding: '12px 8px',
    gap: '2px',
    flex: 1,
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '12px 16px',
    borderTop: '1px solid var(--border)',
    color: 'var(--text-muted)',
    fontSize: '10px',
  },
  main: {
    flex: 1,
    overflowY: 'auto',
    minWidth: 0,
  },
}

const navLinkStyle = (isActive) => ({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '8px 10px',
  borderRadius: 'var(--radius-sm)',
  color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
  background: isActive ? 'var(--accent-dim)' : 'transparent',
  textDecoration: 'none',
  fontSize: '12px',
  letterSpacing: '0.02em',
  transition: 'all 0.15s',
})

export default function Layout() {
  return (
    <div style={styles.layout}>
      <aside style={styles.sidebar}>
        <div style={styles.brand}>
          <span style={styles.brandIcon}>⬡</span>
          <div>
            <div style={styles.brandName}>IMS</div>
            <div style={styles.brandSub}>Incident Management</div>
          </div>
        </div>
        <nav style={styles.nav}>
          <NavLink to="/" end style={({ isActive }) => navLinkStyle(isActive)}>
            <Activity size={14} /> Live Feed
          </NavLink>
          <NavLink to="/ingest" style={({ isActive }) => navLinkStyle(isActive)}>
            <Radio size={14} /> Ingest Signal
          </NavLink>
        </nav>
        <div style={styles.footer}>
          <Zap size={11} /> v1.0.0
        </div>
      </aside>
      <main style={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}