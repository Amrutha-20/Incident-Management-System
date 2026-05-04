import { useState } from 'react'
import { transitionStatus } from '../../services/api'

const CATEGORIES = ['INFRASTRUCTURE','CODE_BUG','DEPENDENCY_FAILURE','CONFIGURATION','CAPACITY','SECURITY','UNKNOWN']

const isoLocal = () => {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

const field = { display: 'flex', flexDirection: 'column', gap: '5px' }
const label = { fontSize: '10px', color: 'var(--text-secondary)', letterSpacing: '0.05em', textTransform: 'uppercase' }
const input = {
  background: 'var(--bg-base)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)',
  fontFamily: 'var(--font-mono)', fontSize: '12px',
  padding: '8px 10px', outline: 'none', width: '100%',
}

export default function RCAForm({ workItemId, firstSignalAt, onSuccess }) {
  const defaultStart = firstSignalAt
    ? new Date(firstSignalAt).toISOString().slice(0, 16)
    : isoLocal()

  const [form, setForm] = useState({
    incident_start: defaultStart,
    incident_end: isoLocal(),
    root_cause_category: 'INFRASTRUCTURE',
    root_cause_description: '',
    fix_applied: '',
    prevention_steps: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const submit = async () => {
    setSaving(true)
    setError(null)
    try {
      await transitionStatus(workItemId, {
        new_status: 'CLOSED',
        rca: {
          ...form,
          incident_start: new Date(form.incident_start).toISOString(),
          incident_end:   new Date(form.incident_end).toISOString(),
        },
      })
      onSuccess && onSuccess()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '20px' }}>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
        Root Cause Analysis
      </div>

      {error && (
        <div style={{ background: 'var(--p0-bg)', color: 'var(--p0)', border: '1px solid var(--p0)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', fontSize: '12px' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <div style={field}>
          <span style={label}>Incident Start</span>
          <input style={input} type="datetime-local" value={form.incident_start} onChange={e => set('incident_start', e.target.value)} />
        </div>
        <div style={field}>
          <span style={label}>Incident End</span>
          <input style={input} type="datetime-local" value={form.incident_end} onChange={e => set('incident_end', e.target.value)} />
        </div>
      </div>

      <div style={field}>
        <span style={label}>Root Cause Category</span>
        <select style={input} value={form.root_cause_category} onChange={e => set('root_cause_category', e.target.value)}>
          {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
        </select>
      </div>

      <div style={field}>
        <span style={label}>Root Cause Description <em style={{ color: 'var(--text-muted)', textTransform: 'none' }}>(min 20 chars)</em></span>
        <textarea style={{ ...input, resize: 'vertical' }} rows={3} value={form.root_cause_description}
          onChange={e => set('root_cause_description', e.target.value)}
          placeholder="Describe the root cause in detail..." />
      </div>

      <div style={field}>
        <span style={label}>Fix Applied <em style={{ color: 'var(--text-muted)', textTransform: 'none' }}>(min 10 chars)</em></span>
        <textarea style={{ ...input, resize: 'vertical' }} rows={2} value={form.fix_applied}
          onChange={e => set('fix_applied', e.target.value)}
          placeholder="What was done to resolve this?" />
      </div>

      <div style={field}>
        <span style={label}>Prevention Steps <em style={{ color: 'var(--text-muted)', textTransform: 'none' }}>(min 10 chars)</em></span>
        <textarea style={{ ...input, resize: 'vertical' }} rows={2} value={form.prevention_steps}
          onChange={e => set('prevention_steps', e.target.value)}
          placeholder="How do we prevent recurrence?" />
      </div>

      <button
        onClick={submit}
        disabled={saving}
        style={{
          background: 'var(--accent)', color: '#fff', border: 'none',
          borderRadius: 'var(--radius-sm)', padding: '10px 20px',
          fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700,
          letterSpacing: '0.05em', cursor: saving ? 'not-allowed' : 'pointer',
          opacity: saving ? 0.6 : 1, alignSelf: 'flex-start', transition: 'all 0.15s',
        }}>
        {saving ? 'Submitting...' : 'Submit RCA & Close Incident'}
      </button>
    </div>
  )
}