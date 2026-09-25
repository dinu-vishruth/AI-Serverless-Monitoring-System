import React from 'react';
import { Activity, Bot, Plus, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react';

export default function Navbar({
  onOpenAddService,
  onOpenAssistant,
  onRefresh,
  isRefreshing,
  openIncidentsCount = 0,
}) {
  return (
    <header className="navbar">
      <div className="nav-brand">
        <div className="brand-icon">
          <Sparkles size={22} color="#ffffff" />
        </div>
        <div>
          <h1 className="brand-title">AegisAI</h1>
          <p className="brand-subtitle">AI-Driven Serverless Event Monitoring</p>
        </div>
      </div>

      <div className="nav-actions">
        <button
          className="btn btn-secondary btn-icon-only"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh telemetry"
          id="btn-refresh"
        >
          <RefreshCw size={17} className={isRefreshing ? 'spin' : ''} />
        </button>

        <button
          className="btn btn-secondary"
          onClick={onOpenAssistant}
          id="btn-ai-assistant"
          style={{ borderColor: 'rgba(99, 102, 241, 0.4)' }}
        >
          <Bot size={17} color="#a5b4fc" />
          <span>AI Assistant</span>
        </button>

        <button
          className="btn btn-primary"
          onClick={onOpenAddService}
          id="btn-add-service"
        >
          <Plus size={17} />
          <span>Register Service</span>
        </button>
      </div>
    </header>
  );
}
