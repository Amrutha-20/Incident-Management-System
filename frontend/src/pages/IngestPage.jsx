import { useState } from 'react'
import { ingestSignal, ingestBatch } from '../services/api'

const COMPONENT_TYPES = ['API', 'MCP_HOST', 'CACHE', 'ASYNC_QUEUE', 'RDBMS', 'NOSQL']
const SEVERITIES      = ['P0', 'P1', 'P2', 'P3']

const SCENARIOS = [
  { label: 'RDBMS Outage (P0)',     signal: { component_id: 'POSTGRES_PRIMARY_01', component_type: 'RDBMS',      error_code: 'CONN_REFUSED',    message: 'Connection refused. Host unreachable on port 5432.', severity: 'P0', metadata: { host: '10.0.1.5', port: 5432 } } },
  { label: 'Cache Degraded (P2)',   signal: { component_id: 'CACHE_CLUSTER_01',    component_type: 'CACHE',      error_code: 'CACHE_MISS_STORM', message: 'Cache miss rate exceeding 80%. Falling back to DB.', severity: 'P2', metadata: { miss_rate_pct: 82 } } },
  { label: 'MCP Host Down (P0)',    signal: { component_id: 'MCP_HOST_PRIMARY',    component_type: 'MCP_HOST',   error_code: 'AGENT_UNREACHABLE',message: 'MCP host not responding. Agent timeout after 5000ms.', severity: 'P0', metadata: { timeout_ms: 5000 } } },
  { label: 'API Latency Spike (P1)',signal: { component_id: 'API_GATEWAY_01',      component_type: 'API',        error_code: 'LATENCY_SPIKE',   message: 'P99 latency exceeded 2000ms threshold.', severity: 'P1', metadata: { p99_ms: 2340 } } },
  { label: 'Queue Backlog (P1)',    signal: { component_id: 'QUEUE_WORKER_01',     component_type: 'ASYNC_QUEUE',error_code: 'CONSUMER_LAG',    message: 'Consumer lag growing beyond 10k messages.', severity: 'P1', metadata: { lag: 12400 } } },
]

const inputStyle = {
  background: 'var(--bg-base)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)',
  fontFamily: 'var(--font-mono)', fontSize: '12px',
  padding: '7px 10px', width: '100%', outline: 'none',
}

export default function IngestPage() {
  const [form, setForm] = useState({
    component_id: '', component_type: 'API',
    error_code: '', message: '', severity: 'P1',
    metadata: '{}',
  })
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState(null)
  const [loading, setLoading] = useState(false)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const loadScenario = (s) => {
    setForm({ component_id: s.component_id, component_type: s.component_type, error_code: s.error_code, message: s.message, severity: s.severity, metadata: JSON.stringify(s.metadata, null, 2) })
    setResult(null); setError(null)
  }

  const send = async () => {
    setLoading(true); setResult(null); setError(null)
    try {
      let meta = {}
      try { meta = JSON.parse(form.metadata) } catch {}
      const res = await ingestSignal({ ...form, metadata: meta })
      setResult(res)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const burst = async () => {
    setLoading(true); setResult(null); setError(null)
    try {
      const signals = Array.from({ length: 100 }, (_, i) => ({
        component_id: form.component_id || 'BURST_TEST_01',
        component_type: form.component_type,
        error_code: form.error_code || 'BURST_TEST',
        message: `Burst test signal #${i + 1}`,
        severity: form.severity,
        metadata: { index: i },
      }))
      const res = await ingestBatch(signals)
      setResult(res)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={{ minHeight: '100vh' }}>
      <div style={{ padding: '24px' }}>
        <div style={{ marginBottom: '20px' }}>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '22px', fontWeight: 800, color: 'var(--text-primary)' }}>Ingest Signal</h1>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>Send signals to the ingestion API</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '20px', alignItems: 'start' }}>
          {/* Left */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Scenarios */}
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>Quick Scenarios</div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {SCENARIOS.map(s => (
                  <button key={s.label} onClick={() => loadScenario(s.signal)}
                    style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)', color: 'var(--text-secondary)', borderRadius: 'var(--radius-sm)', padding: '5px 10px', fontFamily: 'var(--font-mono)', fontSize: '11px', cursor: 'pointer' }}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Form */}
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>Signal Payload</div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                {[
                  { lbl: 'Component ID', key: 'component_id', placeholder: 'e.g. POSTGRES_PRIMARY_01', type: 'input' },
                  { lbl: 'Component Type', key: 'component_type', options: COMPONENT_TYPES, type: 'select' },
                  { lbl: 'Error Code', key: 'error_code', placeholder: 'e.g. CONN_REFUSED', type: 'input' },
                  { lbl: 'Severity', key: 'severity', options: SEVERITIES, type: 'select' },
                ].map(({ lbl, key, placeholder, options, type }) => (
                  <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <span style={{ fontSize: '10px', color: 'var(--text-secondary)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>{lbl}</span>
                    {type === 'input'
                      ? <input style={inputStyle} value={form[key]} onChange={e => set(key, e.target.value)} placeholder={placeholder} />
                      : <select style={inputStyle} value={form[key]} onChange={e => set(key, e.target.value)}>
                          {options.map(o => <option key={o}>{o}</option>)}
                        </select>
                    }
                  </div>
                ))}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                <span style={{ fontSize: '10px', color: 'var(--text-secondary)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Message</span>
                <input style={inputStyle} value={form.message} onChange={e => set('message', e.target.value)} placeholder="Human-readable error description" />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                <span style={{ fontSize: '10px', color: 'var(--text-secondary)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Metadata (JSON)</span>
                <textarea style={{ ...inputStyle, resize: 'vertical' }} rows={3} value={form.metadata} onChange={e => set('metadata', e.target.value)} />
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={send} disabled={loading}
                  style={{ background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', padding: '8px 18px', fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1 }}>
                  ▶ Send Signal
                </button>
                <button onClick={burst} disabled={loading}
                  style={{ background: 'transparent', border: '1px solid var(--p1)', color: 'var(--p1)', borderRadius: 'var(--radius-sm)', padding: '8px 16px', fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1 }}>
                  ⚡ Burst 100 Signals
                </button>
              </div>
            </div>
          </div>

          {/* Right — response */}
          <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px', position: 'sticky', top: '20px' }}>
            <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>Response</div>
            {error && (
              <div style={{ background: 'var(--p0-bg)', color: 'var(--p0)', border: '1px solid var(--p0)', borderRadius: 'var(--radius-sm)', padding: '10px 12px', fontSize: '12px' }}>
                ⚠ {error}
              </div>
            )}
            {result && (
              <pre style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '12px', fontSize: '11px', color: 'var(--green)', overflowX: 'auto', lineHeight: 1.6, animation: 'fade-in 0.2s ease' }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
            {!result && !error && (
              <div style={{ color: 'var(--text-muted)', fontSize: '12px', padding: '20px', textAlign: 'center' }}>
                Response will appear here
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}