import { formatDistanceToNow, format } from 'date-fns'

export const relativeTime = (ts) => {
  if (!ts) return '—'
  try { return formatDistanceToNow(new Date(ts), { addSuffix: true }) }
  catch { return ts }
}

export const fullTime = (ts) => {
  if (!ts) return '—'
  try { return format(new Date(ts), 'MMM dd, yyyy HH:mm:ss') }
  catch { return ts }
}

export const formatMTTR = (seconds) => {
  if (!seconds) return '—'
  if (seconds < 60)   return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}

export const priorityColor = (p) => ({
  P0: 'var(--p0)',
  P1: 'var(--p1)',
  P2: 'var(--p2)',
  P3: 'var(--p3)',
}[p] || 'var(--text-muted)')

export const priorityBg = (p) => ({
  P0: 'var(--p0-bg)',
  P1: 'var(--p1-bg)',
  P2: 'var(--p2-bg)',
  P3: 'var(--p3-bg)',
}[p] || 'transparent')

export const statusColor = (s) => ({
  OPEN:          'var(--status-open)',
  INVESTIGATING: 'var(--status-investigating)',
  RESOLVED:      'var(--status-resolved)',
  CLOSED:        'var(--status-closed)',
}[s] || 'var(--text-muted)')

export const nextStatuses = (current) => ({
  OPEN:          ['INVESTIGATING'],
  INVESTIGATING: ['RESOLVED'],
  RESOLVED:      ['INVESTIGATING', 'CLOSED'],
  CLOSED:        [],
}[current] || [])