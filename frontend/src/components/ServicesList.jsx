import React from 'react';
import { Play, Eye, Trash2, Cpu, Globe, ArrowUpRight } from 'lucide-react';

export default function ServicesList({
  services = [],
  onSelectService,
  onCheckNow,
  onDeleteService,
  checkingIds = {},
}) {
  if (!services || services.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
        <Globe size={40} color="var(--text-muted)" style={{ margin: '0 auto 1rem' }} />
        <h3 style={{ marginBottom: '0.5rem' }}>No Services Configured</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          Register your first HTTP/HTTPS target API or website to start automated AI monitoring.
        </p>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="data-table">
        <thead>
          <tr>
            <th>Service</th>
            <th>Status</th>
            <th>Latency</th>
            <th>HTTP Code</th>
            <th>Check Interval</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {services.map((s) => {
            const isChecking = checkingIds[s.service_id];
            const status = s.last_check_status || 'UNKNOWN';

            return (
              <tr key={s.service_id}>
                <td>
                  <div className="service-title">{s.service_name}</div>
                  <div className="service-url">
                    <span style={{ color: 'var(--accent-ai)', fontWeight: 600, marginRight: '6px' }}>{s.http_method || 'GET'}</span>
                    {s.url}
                  </div>
                </td>
                <td>
                  {status === 'HEALTHY' && (
                    <span className="badge badge-healthy">
                      <span className="badge-dot" /> Operational
                    </span>
                  )}
                  {status === 'DEGRADED' && (
                    <span className="badge badge-degraded">
                      <span className="badge-dot" /> Degraded
                    </span>
                  )}
                  {status === 'DOWN' && (
                    <span className="badge badge-critical">
                      <span className="badge-dot" /> Down
                    </span>
                  )}
                  {status === 'UNKNOWN' && (
                    <span className="badge" style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--text-muted)' }}>
                      Pending
                    </span>
                  )}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {s.last_response_time !== null && s.last_response_time !== undefined ? `${s.last_response_time}ms` : '—'}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {s.last_status_code ? (
                    <span style={{
                      color: s.last_status_code < 400 ? 'var(--accent-healthy)' : 'var(--accent-critical)'
                    }}>
                      {s.last_status_code}
                    </span>
                  ) : '—'}
                </td>
                <td style={{ color: 'var(--text-secondary)' }}>
                  Every {s.check_interval || 60}s
                </td>
                <td>
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <button
                      className="btn btn-secondary btn-icon-only"
                      onClick={() => onCheckNow(s.service_id)}
                      disabled={isChecking}
                      title="Run live probe now"
                    >
                      <Play size={14} color={isChecking ? 'var(--text-muted)' : 'var(--accent-healthy)'} />
                    </button>
                    <button
                      className="btn btn-secondary btn-icon-only"
                      onClick={() => onSelectService(s)}
                      title="View telemetry & charts"
                    >
                      <Eye size={14} color="var(--accent-cyan)" />
                    </button>
                    <button
                      className="btn btn-secondary btn-icon-only"
                      onClick={() => onDeleteService(s.service_id)}
                      title="Delete service"
                    >
                      <Trash2 size={14} color="var(--accent-critical)" />
                    </button>
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
