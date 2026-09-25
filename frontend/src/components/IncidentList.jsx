import React from 'react';
import { AlertTriangle, CheckCheck, Sparkles, ShieldAlert, ArrowRight } from 'lucide-react';

export default function IncidentList({
  incidents = [],
  onSelectIncident,
  onResolveIncident,
}) {
  if (!incidents || incidents.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
        <CheckCheck size={40} color="var(--accent-healthy)" style={{ margin: '0 auto 1rem' }} />
        <h3 style={{ marginBottom: '0.5rem' }}>All Systems Operating Normally</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          No open alerts or predictive degradation detected across any services.
        </p>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="data-table">
        <thead>
          <tr>
            <th>Incident & Target</th>
            <th>Severity</th>
            <th>Trigger Cause</th>
            <th>AI Risk Score</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((inc) => {
            const isCritical = inc.severity === 'CRITICAL';
            const isHigh = inc.severity === 'HIGH';
            const isResolved = inc.status === 'RESOLVED';

            return (
              <tr key={inc.incident_id}>
                <td>
                  <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>{inc.service_name || inc.service_id}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {inc.incident_id} • {new Date(inc.created_at).toLocaleTimeString()}
                  </div>
                </td>
                <td>
                  <span className={`badge ${isCritical ? 'badge-critical' : isHigh ? 'badge-degraded' : 'badge-healthy'}`}>
                    <span className="badge-dot" /> {inc.severity}
                  </span>
                </td>
                <td style={{ maxWidth: '280px', color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
                  {inc.trigger_reason}
                </td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: (inc.risk_score || 0) > 70 ? 'var(--accent-critical)' : 'var(--accent-degraded)' }}>
                      {inc.risk_score || 0}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>/100</span>
                  </div>
                </td>
                <td>
                  <span className="badge" style={{
                    background: isResolved ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                    color: isResolved ? 'var(--accent-healthy)' : 'var(--accent-critical)',
                    border: `1px solid ${isResolved ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
                  }}>
                    {inc.status}
                  </span>
                </td>
                <td>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      className="btn btn-primary"
                      style={{ padding: '0.4rem 0.8rem', fontSize: '0.78rem' }}
                      onClick={() => onSelectIncident(inc)}
                      title="Open AI root-cause analysis"
                    >
                      <Sparkles size={13} />
                      <span>AI Insights</span>
                    </button>
                    {!isResolved && (
                      <button
                        className="btn btn-secondary btn-icon-only"
                        onClick={() => onResolveIncident(inc.incident_id)}
                        title="Mark as resolved"
                      >
                        <CheckCheck size={14} color="var(--accent-healthy)" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
