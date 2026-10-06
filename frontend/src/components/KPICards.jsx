import React from 'react';

export default function KPICards({ aggregates }) {
  if (!aggregates) return null;

  const totalPersonas = aggregates.total_personas ?? aggregates.cohort_size ?? 0;
  const eligibleCount = aggregates.eligible_count ?? 0;
  const meanAwareness = aggregates.mean_awareness ?? 0;
  const expectedUptake = aggregates.expected_uptake_probability ?? aggregates.expected_uptake ?? 0;
  const realizedUptake = aggregates.realized_uptake_count ?? aggregates.realized_uptake ?? 0;

  return (
    <section className="section">
      <h2 className="section-title">Simulation Results</h2>
      <p className="section-subtitle">
        Aggregated outcomes across the simulated cohort.
      </p>

      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Personas</div>
          <div className="kpi-value">{totalPersonas}</div>
          <div className="kpi-desc">
            Number of synthetic student agents in this simulation.
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Eligible</div>
          <div className="kpi-value">{eligibleCount}</div>
          <div className="kpi-desc">
            Number of synthetic personas satisfying deterministic policy eligibility rules.
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Average Awareness</div>
          <div className="kpi-value">{(Number(meanAwareness) * 100).toFixed(0)}%</div>
          <div className="kpi-desc">
            Average simulated awareness of the scheme across personas.
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Expected Uptake</div>
          <div className="kpi-value">{(Number(expectedUptake) * 100).toFixed(0)}%</div>
          <div className="kpi-desc">
            Model-estimated probability of uptake (not a real-world prediction).
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Benefit Received</div>
          <div className="kpi-value">{realizedUptake} / {totalPersonas}</div>
          <div className="kpi-desc">
            Synthetic personas that reached the benefit-received state in this run.
          </div>
        </div>
      </div>

      <p className="disclaimer-note">
        Results are based on synthetic personas and are not real-world population statistics.
      </p>
    </section>
  );
}
