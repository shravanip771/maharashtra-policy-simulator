import React from 'react';

export default function DistrictInspector({ profile, loading, error }) {
  if (loading) {
    return (
      <div className="section district-inspector-container">
        <h3 className="section-title">District Baseline Inspector</h3>
        <p className="text-muted" style={{ padding: '12px 0' }}>
          Loading district baseline profile...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="section district-inspector-container">
        <h3 className="section-title">District Baseline Inspector</h3>
        <p style={{ color: 'var(--danger-text)', padding: '12px 0' }}>
          Failed to load district information: {error}
        </p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="section district-inspector-container">
        <h3 className="section-title">District Baseline Inspector</h3>
        <p className="text-muted" style={{ padding: '12px 0' }}>
          Select a district to inspect its empirical baseline or provisional parameters.
        </p>
      </div>
    );
  }

  const isEmpirical = profile.provenance_tier === 'empirical_observed';
  const tierLabel = isEmpirical
    ? 'Tier 1 — Verified Empirical Baseline'
    : 'Provisional / Synthetic Baseline';
  const tierBadgeClass = isEmpirical
    ? 'badge badge-tier-empirical'
    : 'badge badge-tier-provisional';

  const talukas = profile.talukas || [];
  const assumptions = profile.assumptions_and_fallbacks || [];
  const missingData = profile.missing_data || [];
  const stats = profile.available_statistics || {};

  return (
    <section className="section district-inspector-container">
      <div className="inspector-header">
        <div>
          <div className="inspector-title-row">
            <h3 className="inspector-district-name">{profile.district_name}</h3>
            <span className={tierBadgeClass}>{tierLabel}</span>
          </div>
          <p className="inspector-sub">
            Division: <strong>{profile.division}</strong> &bull; Region:{' '}
            <span>{profile.region_type || 'Standard Administrative'}</span>
          </p>
        </div>
      </div>

      <div className="inspector-grid">
        <div className="inspector-card">
          <div className="inspector-card-label">Reference Dataset</div>
          <div className="inspector-card-value">{profile.reference_dataset || 'Not specified'}</div>
          {profile.reference_year && (
            <div className="inspector-card-desc">Reference Period: {profile.reference_year}</div>
          )}
        </div>

        <div className="inspector-card">
          <div className="inspector-card-label">Data Provenance Tier</div>
          <div className="inspector-card-value">
            {isEmpirical ? 'Observed Ground Truth (Tier 1)' : 'Calibrated Provisional Model'}
          </div>
          <div className="inspector-card-desc">
            {isEmpirical
              ? 'Derived directly from official educational survey census records.'
              : 'Synthesized using regional distributions and division-level calibration.'}
          </div>
        </div>

        <div className="inspector-card">
          <div className="inspector-card-label">Administrative Talukas ({talukas.length})</div>
          <div className="taluka-chips">
            {talukas.slice(0, 10).map((t, idx) => (
              <span key={idx} className="taluka-chip">
                {t}
              </span>
            ))}
            {talukas.length > 10 && (
              <span className="taluka-chip taluka-chip-more">
                +{talukas.length - 10} more
              </span>
            )}
          </div>
        </div>

        {Object.keys(stats).length > 0 && (
          <div className="inspector-card">
            <div className="inspector-card-label">Baseline Statistics</div>
            <div className="stats-list">
              {Object.entries(stats).map(([k, v]) => (
                <div key={k} className="stat-entry">
                  <span className="stat-key">{k.replace(/_/g, ' ')}:</span>{' '}
                  <span className="stat-val">
                    {typeof v === 'number' ? v.toLocaleString('en-IN') : String(v)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Assumptions & Fallbacks */}
      {assumptions.length > 0 && (
        <div className="inspector-notes-box">
          <div className="inspector-notes-title">Assumptions & Fallbacks:</div>
          <ul className="inspector-notes-list">
            {assumptions.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Missing Data Warning if provisional */}
      {!isEmpirical && missingData.length > 0 && (
        <div className="inspector-missing-box">
          <div className="inspector-missing-title">Data Limitations & Proxies:</div>
          <p className="inspector-missing-text">
            Missing district-specific primary survey for: {missingData.join(', ')}. Division-level
            calibration applied. Do not treat as real-world census verification.
          </p>
        </div>
      )}
    </section>
  );
}
