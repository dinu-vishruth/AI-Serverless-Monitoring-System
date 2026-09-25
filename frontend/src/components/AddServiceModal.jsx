import React, { useState } from 'react';
import { X, Plus, Globe } from 'lucide-react';
import { api } from '../services/api';

export default function AddServiceModal({ onClose, onCreated }) {
  const [formData, setFormData] = useState({
    service_name: '',
    url: '',
    http_method: 'GET',
    expected_status_code: 200,
    check_interval: 60,
    timeout: 10,
    response_time_threshold: 2000,
    error_threshold: 0.05,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await api.createService({
        ...formData,
        expected_status_code: Number(formData.expected_status_code),
        check_interval: Number(formData.check_interval),
        timeout: Number(formData.timeout),
        response_time_threshold: Number(formData.response_time_threshold),
        error_threshold: Number(formData.error_threshold),
      });
      onCreated();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div className="brand-icon" style={{ width: '32px', height: '32px' }}>
              <Globe size={18} color="#fff" />
            </div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Register Monitored Service</h3>
          </div>
          <button className="btn btn-secondary btn-icon-only" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: 'var(--accent-critical)',
            padding: '0.75rem',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1rem',
            fontSize: '0.85rem'
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Service Name *</label>
            <input
              type="text"
              className="form-input"
              required
              placeholder="e.g. Payment Gateway API"
              value={formData.service_name}
              onChange={(e) => setFormData({ ...formData, service_name: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Target URL *</label>
            <input
              type="url"
              className="form-input"
              required
              placeholder="https://api.example.com/health"
              value={formData.url}
              onChange={(e) => setFormData({ ...formData, url: e.target.value })}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">HTTP Method</label>
              <select
                className="form-select"
                value={formData.http_method}
                onChange={(e) => setFormData({ ...formData, http_method: e.target.value })}
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="HEAD">HEAD</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Expected Status</label>
              <input
                type="number"
                className="form-input"
                value={formData.expected_status_code}
                onChange={(e) => setFormData({ ...formData, expected_status_code: e.target.value })}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Check Interval (sec)</label>
              <input
                type="number"
                className="form-input"
                min="10"
                max="3600"
                value={formData.check_interval}
                onChange={(e) => setFormData({ ...formData, check_interval: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Latency Alert Threshold (ms)</label>
              <input
                type="number"
                className="form-input"
                min="100"
                value={formData.response_time_threshold}
                onChange={(e) => setFormData({ ...formData, response_time_threshold: e.target.value })}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              <Plus size={16} />
              <span>{loading ? 'Registering...' : 'Register Target'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
