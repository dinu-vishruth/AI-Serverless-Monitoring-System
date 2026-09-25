import React, { useState } from 'react';
import { X, Sparkles, AlertCircle, CheckCircle2, ShieldAlert, RefreshCw, Layers } from 'lucide-react';
import { api } from '../services/api';

export default function AIIncidentDrawer({ incident, onClose, onAskAssistant }) {
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState(incident?.ai_analysis || null);

  async function handleReanalyze() {
    if (!incident) return;
    setAnalyzing(true);
    try {
      const result = await api.analyzeIncident(incident.incident_id);
      setAnalysis(result);
    } catch (err) {
      console.error('Analysis failed', err);
    } finally {
      setAnalyzing(false);
    }
  }

  if (!incident) return null;

  const currentAnalysis = analysis || incident.ai_analysis;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="drawer-right" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
              <span className="badge badge-ai">
                <Sparkles size={12} /> AI Root Cause Analysis
              </span>
              <span className="badge badge-critical">{incident.severity}</span>
            </div>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 800 }}>{incident.service_name || incident.service_id}</h2>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {incident.incident_id}
            </div>
          </div>
          <button className="btn btn-secondary btn-icon-only" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Telemetry Snapshot */}
        <div style={{
          background: 'rgba(0, 0, 0, 0.3)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '1rem',
          marginBottom: '1.5rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '0.75rem',
          textAlign: 'center'
        }}>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Latency</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent-cyan)' }}>
              {incident.metrics_snapshot?.response_time || 0}ms
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Status Code</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: (incident.metrics_snapshot?.status_code || 200) >= 400 ? 'var(--accent-critical)' : 'var(--accent-healthy)' }}>
              {incident.metrics_snapshot?.status_code || 'Err'}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>AI Risk Score</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent-critical)' }}>
              {incident.risk_score || 0}/100
            </div>
          </div>
        </div>

        {/* AI Analysis Content */}
        {currentAnalysis ? (
          <div>
            {/* Summary */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(168, 85, 247, 0.12) 100%)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              borderRadius: 'var(--radius-md)',
              padding: '1.25rem',
              marginBottom: '1.5rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '0.9rem', color: '#c7d2fe', marginBottom: '0.5rem' }}>
                <Sparkles size={16} /> Executive AI Summary
              </div>
              <p style={{ fontSize: '0.875rem', lineHeight: '1.6', color: 'var(--text-primary)' }}>
                {currentAnalysis.incident_summary}
              </p>
            </div>

            {/* Observed Facts */}
            {currentAnalysis.observed_facts?.length > 0 && (
              <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                  Observed Telemetry Facts
                </h4>
                <ul style={{ listStyle: 'none', paddingLeft: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {currentAnalysis.observed_facts.map((fact, i) => (
                    <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      <span style={{ color: 'var(--accent-ai)', marginTop: '2px' }}>●</span>
                      <span>{fact}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Possible Causes */}
            {currentAnalysis.possible_causes?.length > 0 && (
              <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                  Probable Root Causes
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {currentAnalysis.possible_causes.map((cause, i) => (
                    <div key={i} style={{
                      background: 'rgba(239, 68, 68, 0.08)',
                      borderLeft: '3px solid var(--accent-critical)',
                      padding: '0.75rem 1rem',
                      borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
                      fontSize: '0.85rem',
                      color: '#fca5a5'
                    }}>
                      {cause}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommended Actions */}
            {currentAnalysis.recommended_actions?.length > 0 && (
              <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                  Actionable Remediation Steps
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {currentAnalysis.recommended_actions.map((act, i) => (
                    <div key={i} style={{
                      background: 'rgba(16, 185, 129, 0.08)',
                      borderLeft: '3px solid var(--accent-healthy)',
                      padding: '0.75rem 1rem',
                      borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
                      fontSize: '0.85rem',
                      color: '#a7f3d0',
                      display: 'flex',
                      gap: '0.5rem',
                      alignItems: 'center'
                    }}>
                      <CheckCircle2 size={16} color="var(--accent-healthy)" style={{ flexShrink: 0 }} />
                      <span>{act}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
            <p style={{ marginBottom: '1rem', fontSize: '0.875rem' }}>No AI analysis generated yet for this incident.</p>
          </div>
        )}

        {/* Action buttons */}
        <div style={{ marginTop: '2rem', display: 'flex', gap: '0.75rem' }}>
          <button
            className="btn btn-primary"
            style={{ flex: 1 }}
            onClick={handleReanalyze}
            disabled={analyzing}
          >
            <RefreshCw size={15} className={analyzing ? 'spin' : ''} />
            <span>{analyzing ? 'Analyzing Telemetry...' : 'Regenerate Analysis'}</span>
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => {
              onClose();
              onAskAssistant(incident.incident_id, incident.service_id);
            }}
          >
            <Sparkles size={15} color="#a5b4fc" />
            <span>Chat with AI</span>
          </button>
        </div>
      </div>
    </div>
  );
}
