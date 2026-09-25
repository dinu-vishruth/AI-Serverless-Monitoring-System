import React, { useState, useEffect } from 'react';
import { X, RefreshCw, Cpu, Activity, Clock, AlertCircle } from 'lucide-react';
import { api } from '../services/api';
import MetricsChart from './MetricsChart';

export default function ServiceDetailModal({ service, onClose, onRefreshList }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [retraining, setRetraining] = useState(false);
  const [retrainMsg, setRetrainMsg] = useState(null);

  useEffect(() => {
    if (service?.service_id) {
      loadHistory();
    }
  }, [service]);

  async function loadHistory() {
    setLoading(true);
    try {
      const data = await api.getServiceRecords(service.service_id, 24);
      setRecords(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function handleRetrain() {
    setRetraining(true);
    setRetrainMsg(null);
    try {
      const res = await api.retrainModel(service.service_id);
      setRetrainMsg(`Model retrained successfully (${res.sample_count || records.length} samples)`);
    } catch (err) {
      setRetrainMsg(`Retraining: ${err.message}`);
    } finally {
      setRetraining(false);
    }
  }

  if (!service) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '800px' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
          <div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 800 }}>{service.service_name}</h2>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              {service.http_method || 'GET'} {service.url}
            </div>
          </div>
          <button className="btn btn-secondary btn-icon-only" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Telemetry Chart */}
        <div style={{ marginBottom: '1.5rem' }}>
          <MetricsChart records={records} threshold={service.response_time_threshold || 2000} />
        </div>

        {/* ML Model Controls & Stats */}
        <div style={{
          background: 'rgba(99, 102, 241, 0.08)',
          border: '1px solid rgba(99, 102, 241, 0.25)',
          borderRadius: 'var(--radius-md)',
          padding: '1.25rem',
          marginBottom: '1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '0.95rem' }}>
              <Cpu size={18} color="var(--accent-ai)" />
              Isolation Forest Anomaly Model
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
              Unsupervised multi-feature detection (Latency, Error Rate, Jitter, 4xx/5xx patterns)
            </div>
            {retrainMsg && (
              <div style={{ fontSize: '0.75rem', color: 'var(--accent-healthy)', marginTop: '0.4rem' }}>
                {retrainMsg}
              </div>
            )}
          </div>
          <button
            className="btn btn-secondary"
            onClick={handleRetrain}
            disabled={retraining}
            style={{ borderColor: 'rgba(99, 102, 241, 0.4)' }}
          >
            <RefreshCw size={14} className={retraining ? 'spin' : ''} />
            <span>Retrain ML</span>
          </button>
        </div>

        {/* Historical Checks Log */}
        <h4 style={{ fontSize: '0.9rem', marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>Recent Telemetry Log</h4>
        <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}>
          <table className="data-table" style={{ fontSize: '0.8rem' }}>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Status</th>
                <th>Latency</th>
                <th>Availability</th>
                <th>ML Anomaly</th>
              </tr>
            </thead>
            <tbody>
              {records.slice(0, 15).map((r, i) => (
                <tr key={i}>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{new Date(r.timestamp).toLocaleTimeString()}</td>
                  <td>
                    <span style={{ color: r.status_code < 400 ? 'var(--accent-healthy)' : 'var(--accent-critical)' }}>
                      {r.status_code || 'Err'}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{r.response_time}ms</td>
                  <td>{r.availability === 1 ? '100%' : '0%'}</td>
                  <td>
                    {r.anomaly ? (
                      <span className="badge badge-critical" style={{ fontSize: '0.65rem' }}>Anomaly</span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>Normal</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
