import React from 'react';

export default function KPICards({ aggregates, scope, scopeLabel, scope_label }) {
  if (!aggregates) return null;

  const totalPersonas = aggregates.total_personas ?? aggregates.cohort_size ?? 0;
  const eligibleCount = aggregates.eligible_count ?? 0;
  const meanAwareness = aggregates.mean_awareness ?? 0;
  const expectedUptake = aggregates.expected_uptake_probability ?? aggregates.expected_uptake ?? 0;
  const realizedUptake = aggregates.realized_uptake_count ?? aggregates.realized_uptake ?? 0;
  const totalFeeRelief = aggregates.total_estimated_fee_relief_inr ?? aggregates.total_fee_relief_inr ?? null;
  const avgFeeRelief = aggregates.average_fee_relief_per_eligible_inr ?? aggregates.average_fee_relief_inr ?? null;

  const resolvedScopeLabel = scopeLabel || scope_label || (
    scope === 'statewide'
      ? 'Maharashtra Statewide (36 Districts)'
      : scope === 'drilldown'
        ? (aggregates.district_name ? `District Drill-Down (${aggregates.district_name})` : 'District Drill-Down')
        : (aggregates.district_name
            ? `District Drill-Down (${aggregates.district_name})`
            : (totalPersonas > 36 ? 'Maharashtra Statewide (36 Districts)' : null))
  );

  const formatINR = (val) => {
    const num = Number(val);
    if (isNaN(num)) return '₹0';
    return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 0 });
  };

  return (
    <section className="section">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <h2 className="section-title" style={{ margin: 0 }}>Simulation Results</h2>
        {resolvedScopeLabel && (
          <span className="ps-chip ps-chip-support" style={{ fontSize: '12px' }}>
            {resolvedScopeLabel}
          </span>
        )}
      </div>
      <p className="section-subtitle">
        {resolvedScopeLabel
          ? `Aggregated outcomes across the ${resolvedScopeLabel} cohort.`
          : 'Aggregated outcomes across the simulated cohort.'}
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
            Model-estimated probability of uptake.
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Benefit Received</div>
          <div className="kpi-value">{realizedUptake} / {totalPersonas}</div>
          <div className="kpi-desc">
            Synthetic personas that reached the benefit-received state in this run.
          </div>
        </div>

        {totalFeeRelief != null && (
          <div className="kpi-card">
            <div className="kpi-label">Estimated Fee Relief</div>
            <div className="kpi-value" style={{ color: 'var(--accent-terracotta)' }}>
              {formatINR(totalFeeRelief)}
            </div>
            <div className="kpi-desc">
              {avgFeeRelief != null && avgFeeRelief > 0
                ? `Total 50% statutory fee waiver (${formatINR(avgFeeRelief)} avg/eligible student).`
                : 'Total estimated 50% statutory fee waiver for eligible students.'}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
