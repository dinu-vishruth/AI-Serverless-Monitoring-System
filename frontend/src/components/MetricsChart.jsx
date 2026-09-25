import React from 'react';

export default function MetricsChart({ records = [], title = "Response Time (ms)", threshold = 2000 }) {
  if (!records || records.length === 0) {
    return (
      <div style={{
        height: '220px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-muted)',
        background: 'rgba(0,0,0,0.2)',
        borderRadius: 'var(--radius-md)',
        fontFamily: 'var(--font-mono)',
        fontSize: '0.85rem'
      }}>
        No telemetry records collected yet
      </div>
    );
  }

  // Sort ascending by timestamp
  const sorted = [...records].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  const times = sorted.map(r => r.response_time || 0);
  const maxVal = Math.max(...times, threshold * 1.2, 500);
  const minVal = 0;

  const width = 600;
  const height = 180;
  const padding = 30;

  const points = sorted.map((r, i) => {
    const x = padding + (i / Math.max(sorted.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - ((r.response_time - minVal) / (maxVal - minVal)) * (height - padding * 2);
    return { x, y, record: r };
  });

  const pathD = points.length > 1
    ? points.reduce((acc, p, i) => (i === 0 ? `M ${p.x},${p.y}` : `${acc} L ${p.x},${p.y}`), '')
    : '';

  const thresholdY = height - padding - ((threshold - minVal) / (maxVal - minVal)) * (height - padding * 2);

  return (
    <div style={{ background: 'rgba(0,0,0,0.25)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>{title}</span>
        <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
          Latest: {sorted[sorted.length - 1]?.response_time ?? 0}ms
        </span>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
        {/* Grid lines */}
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="rgba(255,255,255,0.1)" />
        <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="rgba(255,255,255,0.05)" />

        {/* Threshold line */}
        {thresholdY >= padding && (
          <line
            x1={padding}
            y1={thresholdY}
            x2={width - padding}
            y2={thresholdY}
            stroke="rgba(239, 68, 68, 0.5)"
            strokeDasharray="4 4"
          />
        )}

        {/* Area fill */}
        {points.length > 1 && (
          <path
            d={`${pathD} L ${points[points.length - 1].x},${height - padding} L ${points[0].x},${height - padding} Z`}
            fill="url(#gradient-chart)"
            opacity="0.25"
          />
        )}

        {/* Telemetry line */}
        <path d={pathD} fill="none" stroke="var(--accent-cyan)" strokeWidth="2.5" strokeLinecap="round" />

        {/* Data points & anomaly pulses */}
        {points.map((p, i) => {
          const isAnomaly = p.record.anomaly || p.record.error > 0;
          return (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={isAnomaly ? 5 : 2.5}
              fill={isAnomaly ? "var(--accent-critical)" : "var(--accent-cyan)"}
              stroke="#0a0d14"
              strokeWidth="1.5"
            >
              <title>{`${new Date(p.record.timestamp).toLocaleTimeString()}: ${p.record.response_time}ms (${p.record.status_code})`}</title>
            </circle>
          );
        })}

        <defs>
          <linearGradient id="gradient-chart" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent-cyan)" />
            <stop offset="100%" stopColor="transparent" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}
