import React from 'react';

export default function Controls({
  district,
  setDistrict,
  cohortSize,
  setCohortSize,
  numSteps,
  setNumSteps,
  useGemini,
  setUseGemini,
  loading,
  onRunSimulation
}) {
  return (
    <section className="section">
      <h2 className="section-title">Simulation Setup</h2>
      <p className="section-subtitle">
        Configure cohort parameters and simulation execution mode.
      </p>

      <div className="controls-grid">
        <div className="control-field">
          <label htmlFor="select-district" className="control-label">District</label>
          <select
            id="select-district"
            className="control-select"
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
            disabled={loading}
          >
            <option value="Dhule">Dhule</option>
          </select>
        </div>

        <div className="control-field">
          <label htmlFor="input-personas" className="control-label">Personas</label>
          <input
            id="input-personas"
            type="number"
            min="1"
            max="30"
            className="control-input"
            value={cohortSize}
            onChange={(e) => setCohortSize(parseInt(e.target.value, 10) || 10)}
            disabled={loading}
          />
        </div>

        <div className="control-field">
          <label htmlFor="input-steps" className="control-label">Simulation Steps</label>
          <input
            id="input-steps"
            type="number"
            min="1"
            max="5"
            className="control-input"
            value={numSteps}
            onChange={(e) => setNumSteps(parseInt(e.target.value, 10) || 2)}
            disabled={loading}
          />
        </div>

        <div className="control-field">
          <label htmlFor="select-mode" className="control-label">Mode</label>
          <select
            id="select-mode"
            className="control-select"
            value={useGemini ? 'ai' : 'offline'}
            onChange={(e) => setUseGemini(e.target.value === 'ai')}
            disabled={loading}
          >
            <option value="offline">Offline / Stub</option>
            <option value="ai">AI / Gemini LLM</option>
          </select>
        </div>

        <div>
          <button
            type="button"
            className="btn-primary"
            onClick={onRunSimulation}
            disabled={loading}
          >
            {loading ? 'Running simulation...' : 'Run Simulation'}
          </button>
        </div>
      </div>
    </section>
  );
}
