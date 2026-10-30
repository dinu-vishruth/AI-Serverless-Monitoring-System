import React, { useState } from 'react';
import { X, Send, Bot, User, Sparkles, HelpCircle } from 'lucide-react';
import { api } from '../services/api';

const QUICK_PROMPTS = [
  "Summarize overall system health & risks",
  "Why is the response time elevated on the slowest service?",
  "Explain the Isolation Forest anomaly detection logic",
  "Recommend mitigation steps for current open incidents"
];

export default function AIAssistantModal({ onClose, initialIncidentId, initialServiceId }) {
  const [messages, setMessages] = useState([
    {
      sender: 'ai',
      text: "Hello! I answer questions about the services, telemetry, anomalies, and incidents available in this monitoring system. I won't answer unrelated questions or guess when the data is missing."
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSend(queryText = input) {
    const textToSend = queryText.trim();
    if (!textToSend || loading) return;

    const userMsg = { sender: 'user', text: textToSend };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.chatAI(textToSend, initialServiceId, initialIncidentId);
      const aiMsg = {
        sender: 'ai',
        text: res.answer,
        actions: res.suggested_actions,
        provider: res.provider !== 'Context filter' ? res.provider : null
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { sender: 'ai', text: `Sorry, I encountered an error: ${err.message}` }
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '700px', height: '80vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '1rem', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div className="brand-icon" style={{ width: '32px', height: '32px' }}>
              <Bot size={18} color="#ffffff" />
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>AI SRE Assistant</h3>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Explainable AI telemetry intelligence</p>
            </div>
          </div>
          <button className="btn btn-secondary btn-icon-only" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Quick prompt chips */}
        <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.75rem', marginBottom: '0.5rem' }}>
          {QUICK_PROMPTS.map((p, i) => (
            <button
              key={i}
              className="badge"
              style={{
                background: 'rgba(255,255,255,0.05)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-subtle)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                textTransform: 'none',
                fontWeight: 500
              }}
              onClick={() => handleSend(p)}
            >
              <Sparkles size={11} color="var(--accent-ai)" />
              {p}
            </button>
          ))}
        </div>

        {/* Message Log */}
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem', paddingRight: '0.5rem' }}>
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                gap: '0.75rem',
                alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%'
              }}
            >
              {m.sender === 'ai' && (
                <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: 'var(--accent-ai-gradient)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Sparkles size={14} color="#fff" />
                </div>
              )}
              <div
                style={{
                  background: m.sender === 'user' ? 'var(--accent-ai-gradient)' : 'rgba(255,255,255,0.05)',
                  border: m.sender === 'user' ? 'none' : '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.85rem 1.1rem',
                  fontSize: '0.875rem',
                  lineHeight: '1.5',
                  color: '#ffffff'
                }}
              >
                <div>{m.text}</div>
                {m.provider && (
                  <div style={{ marginTop: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    Answered by {m.provider}
                  </div>
                )}
                {m.actions?.length > 0 && (
                  <div style={{ marginTop: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#a5b4fc', marginBottom: '0.25rem' }}>Suggested Actions:</div>
                    {m.actions.map((act, idx) => (
                      <div key={idx} style={{ fontSize: '0.775rem', color: 'var(--text-secondary)' }}>• {act}</div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              <Sparkles size={14} className="spin" color="var(--accent-ai)" />
              Checking monitoring context...
            </div>
          )}
        </div>

        {/* Input area */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)' }}
        >
          <input
            type="text"
            className="form-input"
            placeholder="Ask about incidents, latency anomalies, or recommendations..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={loading || !input.trim()}>
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
