import React from 'react';
import { Activity, AlertTriangle, CheckCircle, Clock, ShieldCheck, Zap } from 'lucide-react';

export default function OverviewCards({ overview }) {
  if (!overview) return null;

  const healthScore = overview.system_health_score ?? 100;
  const isHealthy = healthScore >= 90;
  const isDegraded = healthScore >= 70 && healthScore < 90;

  return (
    <div className="grid-overview">
      {/* Health Score */}
      <div className="card" style={{
        borderLeft: `4px solid ${isHealthy ? 'var(--accent-healthy)' : isDegraded ? 'var(--accent-degraded)' : 'var(--accent-critical)'}`
      }}>
        <div className="stat-card-header">
          <span className="stat-label">System Health Index</span>
          <div className="stat-icon-wrapper">
            <ShieldCheck size={18} color={isHealthy ? 'var(--accent-healthy)' : isDegraded ? 'var(--accent-degraded)' : 'var(--accent-critical)'} />
          </div>
        </div>
        <div className="stat-value" style={{
          color: isHealthy ? 'var(--accent-healthy)' : isDegraded ? 'var(--accent-degraded)' : 'var(--accent-critical)'
        }}>
          {healthScore.toFixed(0)}<span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>/100</span>
        </div>
        <div className="stat-subtext">
          {isHealthy ? 'Operational & Protected' : isDegraded ? 'Degraded Performance' : 'Critical Attention Required'}
        </div>
      </div>

      {/* Monitored Services */}
      <div className="card">
        <div className="stat-card-header">
          <span className="stat-label">Services Status</span>
          <div className="stat-icon-wrapper">
            <CheckCircle size={18} color="var(--accent-healthy)" />
          </div>
        </div>
        <div className="stat-value">{overview.total_services}</div>
        <div className="stat-subtext" style={{ display: 'flex', gap: '0.75rem' }}>
          <span style={{ color: 'var(--accent-healthy)' }}>● {overview.healthy_services} healthy</span>
          {overview.degraded_services > 0 && <span style={{ color: 'var(--accent-degraded)' }}>● {overview.degraded_services} degraded</span>}
          {overview.down_services > 0 && <span style={{ color: 'var(--accent-critical)' }}>● {overview.down_services} down</span>}
        </div>
      </div>

      {/* Active Incidents */}
      <div className="card">
        <div className="stat-card-header">
          <span className="stat-label">Active Incidents</span>
          <div className="stat-icon-wrapper">
            <AlertTriangle size={18} color={overview.active_incidents > 0 ? 'var(--accent-critical)' : 'var(--accent-healthy)'} />
          </div>
        </div>
        <div className="stat-value" style={{ color: overview.active_incidents > 0 ? 'var(--accent-critical)' : 'var(--text-primary)' }}>
          {overview.active_incidents}
        </div>
        <div className="stat-subtext">
          {overview.active_incidents === 0 ? 'Zero active incidents' : 'Triggered AI analysis'}
        </div>
      </div>

      {/* Avg Response Time */}
      <div className="card">
        <div className="stat-card-header">
          <span className="stat-label">Avg Response Time</span>
          <div className="stat-icon-wrapper">
            <Clock size={18} color="var(--accent-cyan)" />
          </div>
        </div>
        <div className="stat-value">{overview.average_response_time_ms}<span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>ms</span></div>
        <div className="stat-subtext">Global telemetry latency</div>
      </div>

      {/* Availability */}
      <div className="card">
        <div className="stat-card-header">
          <span className="stat-label">Overall Availability</span>
          <div className="stat-icon-wrapper">
            <Zap size={18} color="var(--accent-ai)" />
          </div>
        </div>
        <div className="stat-value">{overview.overall_availability_percentage.toFixed(1)}%</div>
        <div className="stat-subtext">SLA uptime compliance</div>
      </div>
    </div>
  );
}
