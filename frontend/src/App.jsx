import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import OverviewCards from './components/OverviewCards';
import ServicesList from './components/ServicesList';
import IncidentList from './components/IncidentList';
import ServiceDetailModal from './components/ServiceDetailModal';
import AIIncidentDrawer from './components/AIIncidentDrawer';
import AIAssistantModal from './components/AIAssistantModal';
import AddServiceModal from './components/AddServiceModal';
import OperationsPanel from './components/OperationsPanel';
import { api } from './services/api';
import { Globe, AlertTriangle, Sparkles, Activity } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('services');
  const [overview, setOverview] = useState(null);
  const [services, setServices] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [token, setToken] = useState(sessionStorage.getItem('isms-token') || '');
  const [checkingIds, setCheckingIds] = useState({});

  // Modals & Drawers state
  const [selectedService, setSelectedService] = useState(null);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [isAddServiceOpen, setIsAddServiceOpen] = useState(false);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [assistantContext, setAssistantContext] = useState({ incidentId: null, serviceId: null });

  useEffect(() => {
    loadAllData();
    const interval = setInterval(loadAllData, 15000); // 15s auto-refresh
    return () => clearInterval(interval);
  }, []);

  async function loadAllData() {
    setIsRefreshing(true);
    try {
      const [overviewData, servicesData, incidentsData] = await Promise.all([
        api.getOverview(),
        api.getServices(),
        api.getIncidents(),
      ]);

      if (overviewData) setOverview(overviewData);
      if (servicesData) setServices(servicesData);
      if (incidentsData) setIncidents(incidentsData);
      setError(null);
    } catch (err) {
      console.error('Failed to refresh data', err);
      setError(err.message);
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleCheckNow(serviceId) {
    setCheckingIds((prev) => ({ ...prev, [serviceId]: true }));
    try {
      await api.triggerCheck(serviceId);
      await loadAllData();
    } catch (err) {
      alert(`Check failed: ${err.message}`);
    } finally {
      setCheckingIds((prev) => ({ ...prev, [serviceId]: false }));
    }
  }

  async function handleDeleteService(serviceId) {
    if (!confirm('Are you sure you want to delete this monitored service?')) return;
    try {
      await api.deleteService(serviceId);
      await loadAllData();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  }

  async function handleResolveIncident(incidentId) {
    try {
      await api.updateIncident(incidentId, { status: 'ACKNOWLEDGED', resolution_notes: 'Acknowledged through dashboard' });
      await loadAllData();
    } catch (err) {
      alert(`Acknowledgement failed: ${err.message}`);
    }
  }

  function handleOpenAssistantForContext(incidentId, serviceId) {
    setAssistantContext({ incidentId, serviceId });
    setIsAssistantOpen(true);
  }

  return (
    <div>
      <div className="ambient-glow-1" />
      <div className="ambient-glow-2" />

      <div className="app-container">
        <form className="access-bar" onSubmit={(e) => { e.preventDefault(); sessionStorage.setItem('isms-token', token); loadAllData(); }}>
          <label htmlFor="admin-token">Administrator access</label>
          <input id="admin-token" type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" placeholder="Bearer token (required in production)" />
          <button className="btn btn-secondary" type="submit">Connect</button>
          <button className="btn btn-secondary" type="button" onClick={() => { sessionStorage.removeItem('isms-token'); setToken(''); setServices([]); setIncidents([]); setOverview(null); }}>Sign out</button>
        </form>
        {error && <div className="error-banner" role="alert">ISMS data unavailable: {error}. Previously loaded data may be stale.</div>}
        <Navbar
          onOpenAddService={() => setIsAddServiceOpen(true)}
          onOpenAssistant={() => handleOpenAssistantForContext(null, null)}
          onRefresh={loadAllData}
          isRefreshing={isRefreshing}
          openIncidentsCount={incidents.filter((i) => i.status === 'OPEN').length}
        />

        {/* Top-level Executive Stats */}
        <OverviewCards overview={overview} />
        <OperationsPanel services={services} incidents={incidents} onRefresh={loadAllData} />

        {/* Tabs Navigation */}
        <div className="tabs-nav">
          <button
            className={`tab-btn ${activeTab === 'services' ? 'active' : ''}`}
            onClick={() => setActiveTab('services')}
            id="tab-services"
          >
            <Globe size={16} />
            <span>Monitored Services ({services.length})</span>
          </button>

          <button
            className={`tab-btn ${activeTab === 'incidents' ? 'active' : ''}`}
            onClick={() => setActiveTab('incidents')}
            id="tab-incidents"
          >
            <AlertTriangle size={16} />
            <span>Incidents & AI Triage ({incidents.filter((i) => i.status !== 'RESOLVED').length})</span>
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'services' && (
          <ServicesList
            services={services}
            onSelectService={(s) => setSelectedService(s)}
            onCheckNow={handleCheckNow}
            onDeleteService={handleDeleteService}
            checkingIds={checkingIds}
          />
        )}

        {activeTab === 'incidents' && (
          <IncidentList
            incidents={incidents}
            onSelectIncident={async (inc) => { try { setSelectedIncident(await api.getIncident(inc.incident_id)); } catch (err) { setError(err.message); } }}
            onResolveIncident={handleResolveIncident}
          />
        )}

        {/* Modals & Drawers */}
        {isAddServiceOpen && (
          <AddServiceModal
            onClose={() => setIsAddServiceOpen(false)}
            onCreated={loadAllData}
          />
        )}

        {selectedService && (
          <ServiceDetailModal
            service={selectedService}
            onClose={() => setSelectedService(null)}
            onRefreshList={loadAllData}
          />
        )}

        {selectedIncident && (
          <AIIncidentDrawer
            incident={selectedIncident}
            onClose={() => setSelectedIncident(null)}
            onAskAssistant={handleOpenAssistantForContext}
          />
        )}

        {isAssistantOpen && (
          <AIAssistantModal
            onClose={() => setIsAssistantOpen(false)}
            initialIncidentId={assistantContext.incidentId}
            initialServiceId={assistantContext.serviceId}
          />
        )}
      </div>
    </div>
  );
}
