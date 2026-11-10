import React, { useState, useEffect } from 'react';
import { api } from '../services/api';

export default function OperationsPanel({ services, incidents, onRefresh }) {
  const [notifications, setNotifications] = useState(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState('ONLINE');
  useEffect(() => {
    let live = true;
    api.getNotifications()
      .then((n) => { if (live) setNotifications(n); })
      .catch((err) => { if (live) setMessage(err.message); });
    return () => { live = false; };
  }, [services]);
  async function run(action) {
    setBusy(true); setMessage('');
    try { await action(); await onRefresh(); }
    catch (err) { setMessage(err.message); }
    finally { setBusy(false); }
  }
  const active = incidents.filter((i) => !['RESOLVED', 'CLOSED'].includes(i.status));
  const events = incidents.flatMap((i) => (i.timeline || []).map((e) => ({ ...e, service: i.service_name })))
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp)).slice(0, 12);
  return <section className="operations-grid">
    <div className="card"><h3>Incident response</h3>
      {active.length === 0 && <p>No active incidents in loaded results.</p>}
      {active.slice(0, 5).map((i) => <div className="incident-operation" key={i.incident_id}>
        <strong>{i.service_name} · {i.severity}</strong>
        <p>{i.status} · {Math.max(0, Math.round((Date.now() - Date.parse(i.created_at)) / 60000))} min · AI {i.ai_status || 'not requested'} ({i.ai_confidence || 'unknown'} confidence)</p>
        <p>{(i.likely_cause || []).slice(0, 1).join(' ') || 'Cause unconfirmed'}</p>
        <div className="operation-actions">{['ACKNOWLEDGED', 'INVESTIGATING', 'MITIGATING'].map((status) => <button disabled={busy || i.status === status} className="btn btn-secondary" key={status} onClick={() => run(() => api.updateIncident(i.incident_id, { status }))}>{status.toLowerCase()}</button>)}</div>
        <div className="operation-actions"><button disabled={busy} className="btn btn-secondary" onClick={() => run(() => api.remediate(i.incident_id, 'retry_health_check', 'Operator approved retry'))}>Authorize retry check</button><button disabled={busy} className="btn btn-secondary" onClick={() => run(() => api.remediate(i.incident_id, 'mute_alerts', 'Operator approved one hour mute'))}>Mute 1 hour</button><button disabled={busy} className="btn btn-secondary" onClick={() => run(() => api.remediate(i.incident_id, 'unmute_alerts', 'Operator resumed notifications'))}>Unmute</button></div>
      </div>)}
      <p>Notifications: {notifications?.configured ? `${notifications.confirmed_email_subscriptions} confirmed email subscriptions` : 'SNS not configured'}. Email receipt requires a live delivery test.</p>
    </div>
    <div className="card"><h3>Failure demonstration</h3><p>Register the demo HTTPS endpoint first. Changing mode changes the actual test service response.</p>
      <div className="operation-actions"><select aria-label="Demo failure mode" className="form-select" value={demo} onChange={(e) => setDemo(e.target.value)}>{['ONLINE','HTTP_500','HTTP_503','TIMEOUT','SLOW_RESPONSE','RECOVERY'].map((m) => <option key={m}>{m}</option>)}</select><button disabled={busy} className="btn btn-primary" onClick={() => run(() => api.setDemoMode(demo))}>Apply demo mode</button></div>
    </div>
    <div className="card"><h3>System timeline</h3>{events.length === 0 && <p>Lifecycle events appear after incident detection.</p>}{events.map((e, i) => <p className="timeline-event" key={i}><time>{new Date(e.timestamp).toLocaleTimeString()}</time> · {e.service} · {e.action} · {e.actor}</p>)}
      <h3>Recovery</h3>{incidents.filter((i) => i.resolved_at).slice(0, 5).map((i) => <p key={i.incident_id}>{i.service_name} · downtime {i.downtime_seconds == null ? 'unknown' : `${Math.round(i.downtime_seconds)}s`}</p>)}
    </div>
    {message && <div className="error-banner" role="status">{message}</div>}
  </section>;
}
