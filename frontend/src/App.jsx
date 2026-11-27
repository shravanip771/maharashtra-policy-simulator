import React, { useState, useEffect, Component } from 'react';
import Header from './components/Header.jsx';
import DistrictMap from './components/DistrictMap.jsx';
import KPICards from './components/KPICards.jsx';
import PersonaTable from './components/PersonaTable.jsx';
import PersonaDetail from './components/PersonaDetail.jsx';
import SocialNetwork from './components/SocialNetwork.jsx';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="ps-main-container">
          <div className="ps-card" style={{ borderLeft: '4px solid #b91c1c' }}>
            <h3 style={{ color: '#b91c1c', marginBottom: '8px' }}>Simulation Shell Notice</h3>
            <p style={{ color: 'var(--text-secondary-light)' }}>
              {this.state.error?.message || 'An unexpected rendering error occurred.'}
            </p>
            <button
              type="button"
              className="ps-btn-primary"
              style={{ marginTop: '16px' }}
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const STATEWIDE_SCOPE = {
  id: 'statewide',
  name: 'Maharashtra (Statewide)',
  shortName: 'Statewide',
  region: 'Statewide',
  regionKey: 'ALL'
};

const normalizeDistrictName = (cityName) => {
  if (!cityName) return '';
  const lower = cityName.toLowerCase().trim();
  if (lower === 'mumbai') return 'Mumbai City';
  if (lower === 'ahmednagar') return 'Ahilyanagar';
  return cityName;
};

function MainDashboard() {
  // Selected district state tracking target: defaults to Maharashtra Statewide
  const [selectedDistrict, setSelectedDistrict] = useState(STATEWIDE_SCOPE);

  // Dynamic districts list fetched from GET /api/districts
  const [districtsList, setDistrictsList] = useState([]);

  useEffect(() => {
    fetch('/api/districts')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setDistrictsList(data);
        }
      })
      .catch((err) => console.error('Failed to load districts from API:', err));
  }, []);

  // Existing engine parameter states preserved for full backward compatibility
  const [district, setDistrict] = useState('STATEWIDE');
  const [cohortSize, setCohortSize] = useState(10);
  const [numSteps, setNumSteps] = useState(2);
  const [useGemini, setUseGemini] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [simulationData, setSimulationData] = useState(null);
  const [statewideSimulationData, setStatewideSimulationData] = useState(null);
  const [selectedPersona, setSelectedPersona] = useState(null);

  const isStatewideTarget = !selectedDistrict || selectedDistrict.id === 'statewide' || district.toUpperCase() === 'STATEWIDE';
  const isStatewideLoaded = Boolean(simulationData?.is_statewide);
  const isDrillDownActive = Boolean(isStatewideLoaded && selectedDistrict && selectedDistrict.id !== 'statewide');
  const isViewingIndividualDistrictSimulation = Boolean(simulationData && !simulationData.is_statewide);
  const canReturnToStatewide = Boolean(isViewingIndividualDistrictSimulation && statewideSimulationData);

  const activeDistrictMeta = !isStatewideTarget
    ? districtsList.find((d) =>
        d.district_name.toLowerCase() === (selectedDistrict.name || '').toLowerCase() ||
        d.district_id.toLowerCase() === (selectedDistrict.id || '').toLowerCase() ||
        (normalizeDistrictName(d.district_name).toLowerCase() === normalizeDistrictName(selectedDistrict.name || '').toLowerCase())
      )
    : null;

  const isEmpiricalSelected = !isStatewideTarget && (activeDistrictMeta
    ? activeDistrictMeta.is_empirical
    : (selectedDistrict.id === 'dhule' || selectedDistrict.name === 'Dhule' || selectedDistrict.name === 'Mumbai City'));

  const handleSelectDistrict = (city) => {
    if (!city || city.id === 'statewide') {
      setSelectedDistrict(STATEWIDE_SCOPE);
      setDistrict('STATEWIDE');
      setSelectedPersona(null);
      return;
    }
    const resolvedName = normalizeDistrictName(city.name);
    const updatedCity = { ...city, name: resolvedName };

    setSelectedDistrict(updatedCity);
    setDistrict(resolvedName);
    setSelectedPersona(null);

    // If loaded data is single-district, clear it so user can run the new district.
    // If loaded data is statewide, DO NOT clear simulationData; keep it for instant local drill-down!
    if (simulationData && !simulationData.is_statewide) {
      setSimulationData(null);
    }
  };

  const handleReturnToStatewide = () => {
    setSelectedDistrict(STATEWIDE_SCOPE);
    setDistrict('STATEWIDE');
    setSelectedPersona(null);
  };

  const handleRestoreStatewideSimulation = () => {
    if (!statewideSimulationData) return;
    setSimulationData(statewideSimulationData);
    setSelectedDistrict(STATEWIDE_SCOPE);
    setDistrict('STATEWIDE');
    setSelectedPersona(null);
  };

  const runSimulation = async () => {
    if (loading) return;
    setLoading(true);
    setError(null);
    setSelectedPersona(null);

    try {
      const payload = isStatewideTarget
        ? {
            district: 'STATEWIDE',
            simulation_steps: numSteps,
            seed: 42,
            use_gemini: false
          }
        : {
            district: selectedDistrict.name,
            simulation_steps: numSteps,
            seed: 42,
            use_gemini: useGemini
          };

      const response = await fetch(isStatewideTarget ? '/api/simulate/statewide' : '/api/simulate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      setSimulationData(data);
      if (data?.is_statewide) {
        setStatewideSimulationData(data);
      }
    } catch (err) {
      console.error('Simulation run failed:', err);
      setSimulationData(null);
      setError(err.message || 'Simulation could not be loaded.');
    } finally {
      setLoading(false);
    }
  };

  // Resolve active aggregates, personas, and interactions (statewide vs district drill-down)
  let aggregates = simulationData?.aggregate_metrics || null;
  let personas = simulationData?.personas || [];
  let interactions = simulationData?.interactions || simulationData?.interaction_history || [];

  if (isDrillDownActive && simulationData?.district_summaries) {
    const drillDownName = normalizeDistrictName(selectedDistrict.name);
    const summary = simulationData.district_summaries[drillDownName] ||
      Object.entries(simulationData.district_summaries).find(
        ([k]) => normalizeDistrictName(k).toLowerCase() === drillDownName.toLowerCase()
      )?.[1];

    if (summary) {
      aggregates = summary;
    }

    personas = (simulationData.personas || []).filter(
      (p) => normalizeDistrictName(p.district).toLowerCase() === drillDownName.toLowerCase()
    );

    const districtPersonaIds = new Set(personas.map((p) => p.persona_id));
    interactions = (simulationData.interactions || []).filter(
      (i) => districtPersonaIds.has(i.sender_id) || districtPersonaIds.has(i.receiver_id)
    );
  }

  return (
    <div className="ps-shell">
      {/* 1. GLOBAL HEADER / NAVIGATION SHELL */}
      <Header userInitial="M" userName="Govt of Maharashtra" />

      {/* 2. MAIN APPLICATION SHELL */}
      <main className="ps-main-container">
        {/* Global Error Notice */}
        {error && (
          <div className="ps-card" style={{ borderLeft: '4px solid #b91c1c', marginBottom: '16px' }}>
            <strong style={{ color: '#b91c1c' }}>Notice:</strong> {error}
          </div>
        )}

        {/* Global Loading Banner */}
        {loading && (
          <div className="ps-card" style={{ borderLeft: '4px solid var(--accent-terracotta)', marginBottom: '16px' }}>
            <span style={{ fontWeight: 600, color: 'var(--accent-terracotta)' }}>
              {isStatewideTarget
                ? 'Simulating statewide policy cohort across all 36 districts (1,000 synthetic personas)...'
                : `Simulating policy cohort for ${selectedDistrict.name} District...`}
            </span>
          </div>
        )}

        {/* SECTION A: POLICY CONTROL BAR (Prototype Layout Foundation) */}
        <section id="policy-controls-section" className="ps-card" aria-label="Policy Controls Foundation">
          <div style={{ marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <h2 className="ps-section-title">Policy Terms & Scope</h2>
              {isStatewideTarget ? (
                <span className="ps-chip ps-chip-support">Statewide Composite (36 Districts)</span>
              ) : (
                <span className="ps-chip ps-chip-support">{selectedDistrict.name}</span>
              )}
            </div>
            <p className="ps-section-subtitle">
              Configure scheme parameters, reimbursement rate, and target cohort rules across all 36 Maharashtra districts.
            </p>
          </div>

          {/* Prototype Policy Bar Grid Primitives */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', alignItems: 'flex-start' }}>
            <div className="control-field">
              <label className="control-label">Target District / Scope</label>
              <div style={{ height: '42px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px', background: 'var(--bg-card-subtle)', border: '1.5px solid var(--border-light)', borderRadius: 'var(--radius-md)', fontSize: '13px' }}>
                <strong style={{ color: 'var(--text-primary-light)' }}>
                  {isStatewideTarget ? 'Maharashtra' : selectedDistrict.name}
                </strong>
                {isStatewideTarget && (
                  <span style={{ fontSize: '11px', color: '#15803d', fontWeight: 600 }}>Composite 36</span>
                )}
              </div>
            </div>

            <div className="control-field">
              <label className="control-label">Active Scheme</label>
              <div style={{ height: '42px', display: 'flex', alignItems: 'center', padding: '0 12px', background: 'var(--bg-card-subtle)', border: '1.5px solid var(--border-light)', borderRadius: 'var(--radius-md)', fontSize: '13px', fontWeight: 600 }}>
                RCSMS EBC Scheme (DTE)
              </div>
            </div>

            <div className="control-field">
              <label className="control-label">Reimbursement Rate</label>
              <div style={{ height: '42px', display: 'flex', alignItems: 'center', padding: '0 12px', background: 'var(--bg-card-subtle)', border: '1.5px solid var(--border-light)', borderRadius: 'var(--radius-md)', fontSize: '13px' }}>
                <span style={{ fontWeight: 700, color: 'var(--accent-terracotta)', marginRight: '6px' }}>50%</span>
                <span style={{ color: 'var(--text-muted-light)' }}>(Statutory Baseline)</span>
              </div>
            </div>

            <div className="control-field">
              <label className="control-label">Income Ceiling</label>
              <div style={{ height: '42px', display: 'flex', alignItems: 'center', padding: '0 12px', background: 'var(--bg-card-subtle)', border: '1.5px solid var(--border-light)', borderRadius: 'var(--radius-md)', fontSize: '13px' }}>
                <span style={{ fontWeight: 600 }}>≤ ₹8,00,000 / year</span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignSelf: 'flex-end' }}>
              <button
                type="button"
                className="ps-btn-primary"
                style={{
                  width: '100%',
                  opacity: 1,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  background: 'var(--accent-terracotta)'
                }}
                onClick={runSimulation}
                disabled={loading}
                title={
                  isStatewideTarget
                    ? 'Run statewide simulation across all 36 districts'
                    : `Run simulation for ${selectedDistrict.name} District`
                }
              >
                {loading
                  ? 'Simulating...'
                  : isStatewideTarget
                    ? 'Run Statewide Simulation'
                    : `Run Simulation (${selectedDistrict.name})`}
              </button>
            </div>
          </div>
        </section>

        {/* SECTION B: INTERACTIVE MAHARASHTRA DISTRICT MAP (STEP 3) */}
        <DistrictMap
          selectedDistrictId={selectedDistrict.id}
          onSelectDistrict={handleSelectDistrict}
          apiDistricts={districtsList}
          district_summaries={simulationData?.district_summaries}
        />

        {/* SECTION C: RESULTS & PERSONA ARCHITECTURE (Preserves Functional Components) */}
        {simulationData ? (
          <>
            {/* Banner: Return to Maharashtra Statewide Simulation (when viewing individual district run after statewide run) */}
            {canReturnToStatewide && (
              <div
                className="ps-card"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                  background: '#F8FAFC',
                  borderLeft: '4px solid var(--accent-terracotta)',
                  marginBottom: '16px'
                }}
              >
                <div>
                  <span
                    style={{
                      fontSize: '11px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      color: 'var(--text-secondary-light)',
                      fontWeight: 600
                    }}
                  >
                    Individual District Simulation Active
                  </span>
                  <h3
                    style={{
                      fontSize: '18px',
                      fontWeight: 700,
                      color: 'var(--text-primary-light)',
                      margin: '2px 0 0'
                    }}
                  >
                    {selectedDistrict.name} District Results ({personas.length} synthetic personas)
                  </h3>
                  <p
                    style={{
                      fontSize: '13px',
                      color: 'var(--text-secondary-light)',
                      margin: '4px 0 0'
                    }}
                  >
                    Viewing individually executed district simulation. Your previous statewide simulation results are preserved in memory.
                  </p>
                </div>
                <button
                  type="button"
                  className="ps-btn-primary"
                  style={{
                    fontSize: '13px',
                    height: '36px',
                    padding: '0 16px',
                    background: 'var(--accent-terracotta)'
                  }}
                  onClick={handleRestoreStatewideSimulation}
                >
                  ← Back to Maharashtra Simulation
                </button>
              </div>
            )}

            {/* Local District Drill-Down Banner */}
            {isDrillDownActive && (
              <div
                className="ps-card"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                  background: '#F8FAFC',
                  borderLeft: '4px solid var(--accent-terracotta)',
                  marginBottom: '16px'
                }}
              >
                <div>
                  <span
                    style={{
                      fontSize: '11px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      color: 'var(--text-secondary-light)',
                      fontWeight: 600
                    }}
                  >
                    Local District Drill-Down
                  </span>
                  <h3
                    style={{
                      fontSize: '18px',
                      fontWeight: 700,
                      color: 'var(--text-primary-light)',
                      margin: '2px 0 0'
                    }}
                  >
                    {selectedDistrict.name} District Outcomes ({aggregates?.total_personas ?? aggregates?.cohort_size ?? personas.length} synthetic personas)
                  </h3>
                  <p
                    style={{
                      fontSize: '13px',
                      color: 'var(--text-secondary-light)',
                      margin: '4px 0 0'
                    }}
                  >
                    {personas.length > 0
                      ? `Displaying ${personas.length} featured persona(s) sampled from ${selectedDistrict.name} during the statewide simulation.`
                      : `Statewide metrics aggregated from the 1,000-persona cohort. Click "Run Simulation (${selectedDistrict.name})" above to simulate this district's full cohort.`}
                  </p>
                </div>
                <button
                  type="button"
                  className="ps-btn-primary"
                  style={{
                    fontSize: '13px',
                    height: '36px',
                    padding: '0 16px',
                    background: 'var(--accent-terracotta)'
                  }}
                  onClick={handleReturnToStatewide}
                >
                  ← Return to Statewide Overview
                </button>
              </div>
            )}

            {aggregates && <KPICards aggregates={aggregates} />}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', marginTop: '20px' }}>
              <div>
                <PersonaTable
                  personas={personas}
                  onSelectPersona={(p) => setSelectedPersona(p)}
                />
              </div>
              <div>
                <SocialNetwork interactions={interactions} />
              </div>
            </div>
          </>
        ) : (
          <section className="ps-card" style={{ textAlign: 'center', padding: '36px 20px', color: 'var(--text-secondary-light)' }}>
            <p style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary-light)' }}>
              Maharashtra 36-District Policy Simulation Engine Active
            </p>
            <p style={{ fontSize: '13px', marginTop: '6px', maxWidth: '540px', margin: '6px auto 0' }}>
              Click &ldquo;Run Statewide Simulation&rdquo; above to simulate the policy cohort across all 36 districts of Maharashtra (1,000 personas), or select a district on the map for single-district analysis.
            </p>
          </section>
        )}

        {/* Modal Persona Detail */}
        {selectedPersona && (
          <PersonaDetail
            persona={selectedPersona}
            onClose={() => setSelectedPersona(null)}
          />
        )}
      </main>

      {/* 3. SHELL FOOTER WITH OFFICIAL EPISTEMIC PROVENANCE */}
      <footer className="ps-footer">
        <div className="ps-footer-inner">
          <div className="ps-footer-disclaimer">
            <strong>Data & Regulatory Authority:</strong> Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulk Shishyavrutti Yojna,
            administered by the Directorate of Technical Education (DTE), Maharashtra.{' '}
            {isStatewideTarget || isStatewideLoaded
              ? 'Statewide simulation spans all 36 Maharashtra districts. Demographics grounded in empirical Census & DES data for Dhule and Mumbai City, combined with calibrated provisional demographic baselines across 34 districts.'
              : isEmpiricalSelected
                ? `Demographics grounded in ${activeDistrictMeta?.source_reference || 'official empirical census tables'} for ${selectedDistrict.name} District (${activeDistrictMeta?.reference_year || 'Verified'}).`
                : `Demographics for ${selectedDistrict.name} District use calibrated provisional synthetic baselines (${activeDistrictMeta?.reference_year || 'Census'}).`}
          </div>
          <div>
            <span>Version: 2024.1-provisional</span> · <span>Branch: feature/frontend-design-system-shell</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <MainDashboard />
    </ErrorBoundary>
  );
}
