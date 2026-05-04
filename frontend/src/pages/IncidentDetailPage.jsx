import { useParams, useNavigate } from 'react-router-dom'
import { useIncidentDetail } from '../hooks/useIncidentDetail'
import SignalList from '../components/signals/SignalList'
import RCAForm from '../components/incidents/RCAForm'
import StatusTransition from '../components/incidents/StatusTransition'
import { fullTime, priorityColor, statusColor, formatMTTR } from '../utils/format'
import { ArrowLeft, Clock, Cpu, AlertTriangle } from 'lucide-react'

const sectionBox = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-lg)',
  padding: '16px',
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
}

const sectionLabel = {
  fontSize: '10px', textTransform: 'uppercase',
  letterSpacing: '0.1em', color: 'var(--text-muted)',
  borderBottom: '1px solid var(--border)', paddingBottom: '8px',
}

export default function IncidentDetailPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const { detail, loading, error, refetch } = useIncidentDetail(id)

  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px', color: 'var(--text-muted)' }}>Loading incident...</div>
  if (error)   return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px', color: 'var(--p0)' }}>⚠ {error}</div>
  if (!detail) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px', color: 'var(--text-muted)' }}>Incident not found</div>

  const wi  = detail.work_item
  const rca = detail.rca

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Topbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 24px', borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)', position: 'sticky', top: 0, zIndex: 10 }}>
        <button onClick={() => nav('/')} style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: 'none', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: '12px', cursor: 'pointer' }}>
          <ArrowLeft size={14} /> Back
        </button>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: 'auto', letterSpacing: '0.05em' }}>
          #{wi.work_item_id.slice(0, 8)}
        </span>
      </div>

      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Header */}
        <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.08em', border: `1px solid ${priorityColor(wi.priority)}`, color: priorityColor(wi.priority), borderRadius: 'var(--radius-sm)', padding: '4px 10px', flexShrink: 0 }}>
            {wi.priority}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {wi.title}
            </h1>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {[
                { text: wi.component_id, color: 'var(--accent)' },
                { text: wi.component_type, color: 'var(--text-muted)' },
                { text: `● ${wi.status}`, color: statusColor(wi.status) },
              ].map(({ text, color }) => (
                <span key={text} style={{ fontSize: '10px', padding: '2px 8px', border: '1px solid var(--border)', borderRadius: '2px', color, letterSpacing: '0.04em' }}>
                  {text}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Stats strip */}
        <div style={{ display: 'flex', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
          {[
            { icon: <Clock size={11} />, val: fullTime(wi.created_at), lbl: 'Created' },
            { icon: <AlertTriangle size={11} />, val: detail.signal_count, lbl: 'Total Signals' },
            { icon: <Cpu size={11} />, val: wi.component_type, lbl: 'Component' },
            ...(rca ? [{ icon: <Clock size={11} />, val: formatMTTR(rca.mttr_seconds), lbl: 'MTTR' }] : []),
          ].map(({ icon, val, lbl }, i, arr) => (
            <div key={lbl} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px', padding: '12px 20px', flex: 1, borderRight: i < arr.length - 1 ? '1px solid var(--border)' : 'none' }}>
              <span style={{ color: 'var(--text-muted)' }}>{icon}</span>
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>{val}</span>
              <span style={{ fontSize: '9px', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{lbl}</span>
            </div>
          ))}
        </div>

        {/* Main grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '20px', alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {wi.status !== 'CLOSED' && (
              <div style={sectionBox}>
                <div style={sectionLabel}>Transition Status</div>
                <StatusTransition workItemId={wi.work_item_id} currentStatus={wi.status} onSuccess={refetch} />
              </div>
            )}
            <div style={sectionBox}>
              <div style={sectionLabel}>Raw Signals ({detail.signal_count})</div>
              <SignalList signals={detail.signals} />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {wi.status === 'RESOLVED' && (
              <RCAForm workItemId={wi.work_item_id} firstSignalAt={wi.first_signal_at} onSuccess={refetch} />
            )}
            {rca && (
              <div style={sectionBox}>
                <div style={sectionLabel}>RCA Record</div>
                {[
                  { lbl: 'Category', val: rca.root_cause_category },
                  { lbl: 'Root Cause', val: rca.root_cause_description },
                  { lbl: 'Fix Applied', val: rca.fix_applied },
                  { lbl: 'Prevention', val: rca.prevention_steps },
                  { lbl: 'MTTR', val: formatMTTR(rca.mttr_seconds), highlight: true },
                ].map(({ lbl, val, highlight }) => (
                  <div key={lbl} style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    <label style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{lbl}</label>
                    <span style={{ fontSize: highlight ? '16px' : '12px', fontWeight: highlight ? 700 : 400, color: highlight ? 'var(--green)' : 'var(--text-primary)', lineHeight: 1.5 }}>{val}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}