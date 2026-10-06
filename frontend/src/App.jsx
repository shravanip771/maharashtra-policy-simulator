import React, { useState, Component } from 'react';
import Header from './components/Header.jsx';
import Controls from './components/Controls.jsx';
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
        <div className="app-container">
          <div className="alert-box">
            <strong>Simulation could not be loaded.</strong>
            <p style={{ marginTop: '4px' }}>
              {this.state.error?.message || 'An unexpected rendering error occurred.'}
            </p>
            <button
              type="button"
              className="btn-primary"
              style={{ marginTop: '12px' }}
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

function MainDashboard() {
  const [district, setDistrict] = useState('Dhule');
  const [cohortSize, setCohortSize] = useState(10);
  const [numSteps, setNumSteps] = useState(2);
  const [useGemini, setUseGemini] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [simulationData, setSimulationData] = useState(null);
  const [selectedPersona, setSelectedPersona] = useState(null);

  const runSimulation = async () => {
    if (loading) return;
    setLoading(true);
    setError(null);
    setSelectedPersona(null);

    try {
      const response = await fetch('/api/simulate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          district: district,
          cohort_size: cohortSize,
          simulation_steps: numSteps,
          seed: 42,
          use_gemini: useGemini
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      setSimulationData(data);
    } catch (err) {
      console.error('Simulation run failed:', err);
      setSimulationData(null);
      setError(err.message || 'Simulation could not be loaded.');
    } finally {
      setLoading(false);
    }
  };

  const aggregates = simulationData?.aggregate_metrics || null;
  const personas = simulationData?.personas || [];
  const interactions =
    simulationData?.interactions || simulationData?.interaction_history || [];

  return (
    <div className="app-container">
      {/* 1. HEADER */}
      <Header />

      {/* ERROR NOTICE */}
      {error && (
        <div className="alert-box">
          <strong>Simulation could not be loaded:</strong> {error}
        </div>
      )}

      {/* LOADING NOTICE */}
      {loading && (
        <div className="alert-loading">
          Running simulation...
        </div>
      )}

      {/* 2. SIMULATION SETUP */}
      <Controls
        district={district}
        setDistrict={setDistrict}
        cohortSize={cohortSize}
        setCohortSize={setCohortSize}
        numSteps={numSteps}
        setNumSteps={setNumSteps}
        useGemini={useGemini}
        setUseGemini={setUseGemini}
        loading={loading}
        onRunSimulation={runSimulation}
      />

      {/* INITIAL EMPTY STATE */}
      {!simulationData && !loading && !error && (
        <div className="section" style={{ textAlign: 'center', padding: '32px 20px', color: 'var(--text-secondary)' }}>
          <p style={{ fontSize: '14px', fontWeight: '500' }}>
            Configure the simulation and click Run Simulation to begin.
          </p>
        </div>
      )}

      {/* 3. SIMULATION RESULTS (Only displayed after simulation run) */}
      {simulationData && (
        <>
          {aggregates && <KPICards aggregates={aggregates} />}

          {/* 4. PERSONAS */}
          <PersonaTable
            personas={personas}
            onSelectPersona={(p) => setSelectedPersona(p)}
          />

          {/* 5. AI INTERACTIONS */}
          <SocialNetwork interactions={interactions} />
        </>
      )}

      {/* PERSONA DETAIL MODAL */}
      {selectedPersona && (
        <PersonaDetail
          persona={selectedPersona}
          onClose={() => setSelectedPersona(null)}
        />
      )}
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
