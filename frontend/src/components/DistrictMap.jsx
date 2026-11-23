import React, { useState, useMemo } from 'react';
import { buildMaharashtraMapGeometry, ADMINISTRATIVE_REGIONS, MAP_WIDTH, MAP_HEIGHT } from '../assets/maharashtraMapData.js';

/**
 * Interactive Maharashtra District Map Component (Step 3)
 *
 * Requirements:
 * 1. Reuses authentic 35 Voronoi cells and 46-vertex Maharashtra state outline.
 * 2. Every district is clickable, hoverable, and selectable.
 * 3. Dhule is explicitly highlighted as the ONLY live, verified simulation district.
 * 4. All other 34 districts display an honest "Data Pending / Coming Soon" status.
 * 5. Visual styling preserves the dark showcase aesthetic, amber glow, and responsive scaling.
 */
export default function DistrictMap({
  selectedDistrictId = 'dhule',
  onSelectDistrict,
  apiDistricts = [],
  district_summaries = null,
  districtSummaries = null,
  simulationData = null
}) {
  const [hoveredId, setHoveredId] = useState(null);

  // Compute authentic geometry memoized once
  const mapGeo = useMemo(() => {
    try {
      return buildMaharashtraMapGeometry();
    } catch (err) {
      console.error('Failed to construct Maharashtra geometry:', err);
      return null;
    }
  }, []);

  const summaries = districtSummaries || district_summaries || simulationData?.district_summaries || null;
  const hasStatewideResults = Boolean(summaries && typeof summaries === 'object' && Object.keys(summaries).length > 0);

  const formatINR = (val) => {
    const num = Number(val);
    if (isNaN(num)) return '₹0';
    return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 0 });
  };

  const getDistrictSummary = (cityName, cityId) => {
    if (!summaries || typeof summaries !== 'object') return null;

    // Direct exact match
    if (summaries[cityName]) return summaries[cityName];

    const nameLower = (cityName || '').toLowerCase().trim();
    const idLower = (cityId || '').toLowerCase().trim();

    // 1. Ahmednagar / Ahilyanagar normalization
    if (nameLower === 'ahmednagar' || nameLower === 'ahilyanagar' || idLower === 'ahmednagar') {
      return summaries['Ahilyanagar'] || summaries['Ahmednagar'] || null;
    }

    // 2. Preserve existing Mumbai City / Mumbai Suburban distinction; do not merge or invent metrics
    if (nameLower === 'mumbai' || idLower === 'mumbai') {
      return summaries['Mumbai City'] || summaries['Mumbai'] || null;
    }

    // 3. Case-insensitive key match
    const entry = Object.entries(summaries).find(([key]) => {
      const kLower = key.toLowerCase().trim();
      return kLower === nameLower || kLower === idLower;
    });

    return entry ? entry[1] : null;
  };

  const getDistrictMeta = (cityName, cityId) => {
    if (!apiDistricts || apiDistricts.length === 0) return null;
    const nameLower = (cityName || '').toLowerCase();
    const idLower = (cityId || '').toLowerCase();
    return apiDistricts.find(
      (d) => d.district_name.toLowerCase() === nameLower ||
             d.district_id.toLowerCase() === idLower ||
             (nameLower === 'mumbai' && (d.district_id === 'MUMBAI_CITY' || d.district_id === 'MUMBAI_SUBURBAN'))
    );
  };

  if (!mapGeo) {
    return (
      <div className="ps-card-dark" style={{ textAlign: 'center', padding: '40px' }}>
        <p style={{ color: 'var(--text-secondary-dark)' }}>Maharashtra map geometry could not be loaded.</p>
      </div>
    );
  }

  const { outlineD, cities } = mapGeo;

  // Selected district object: default to statewide scope when no district is explicitly selected
  const isStatewide = !selectedDistrictId || selectedDistrictId.toLowerCase() === 'statewide';
  const activeCity = !isStatewide ? (cities.find((c) => c.id === selectedDistrictId) || null) : null;
  const activeApiMeta = activeCity ? getDistrictMeta(activeCity.name, activeCity.id) : null;
  const activeSummary = activeCity ? getDistrictSummary(activeCity.name, activeCity.id) : null;

  // Group cities by administrative region for the accessible dropdown
  const citiesByRegion = useMemo(() => {
    const map = {};
    Object.entries(ADMINISTRATIVE_REGIONS).forEach(([code, name]) => {
      map[name] = cities.filter((c) => c.regionKey === code);
    });
    return map;
  }, [cities]);

  return (
    <div className="ps-card-dark ps-map-wrapper" aria-label="Interactive Maharashtra District Map">
      {/* 1. Header with Selection Status */}
      <div className="ps-map-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '6px' }}>
            <span className="ps-chip ps-chip-neutral">Interactive Map</span>
            <span className="ps-chip ps-chip-support">
              Selected: {isStatewide ? 'Maharashtra' : activeCity.name}
            </span>
          </div>
          <h2 className="ps-section-title-dark">Maharashtra Statewide District Map</h2>
          <p className="ps-section-subtitle-dark">
            Explore all 35 administrative districts. Click any district cell or pin to inspect its demographic baseline status.
          </p>
        </div>

        {/* Accessible Quick-Select Dropdown */}
        <div className="ps-map-dropdown-group">
          <label htmlFor="district-quick-select" className="control-label" style={{ color: 'var(--text-secondary-dark)' }}>
            Jump to District:
          </label>
          <select
            id="district-quick-select"
            className="control-select"
            style={{
              background: '#151B24',
              color: '#FFFFFF',
              borderColor: 'var(--border-dark)',
              height: '38px',
              fontSize: '13px'
            }}
            value={activeCity ? activeCity.id : 'statewide'}
            onChange={(e) => {
              if (e.target.value === 'statewide') {
                if (onSelectDistrict) onSelectDistrict({ id: 'statewide', name: 'Maharashtra (Statewide)', shortName: 'Statewide', region: 'Statewide', regionKey: 'ALL' });
              } else {
                const target = cities.find((c) => c.id === e.target.value);
                if (target && onSelectDistrict) onSelectDistrict(target);
              }
            }}
          >
            <option value="statewide">Maharashtra (Statewide)</option>
            {Object.entries(citiesByRegion).map(([regionName, dList]) => (
              <optgroup key={regionName} label={regionName}>
                {dList.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
      </div>

      {/* 2. Interactive SVG Map Canvas */}
      <div className="ps-map-stage">
        {/* Geographic Watermarks */}
        <span className="ps-watermark ps-wm-sea">Arabian Sea</span>
        <span className="ps-watermark ps-wm-gujarat">GUJARAT</span>
        <span className="ps-watermark ps-wm-mp">MADHYA PRADESH</span>
        <span className="ps-watermark ps-wm-cg">CHHATTISGARH</span>
        <span className="ps-watermark ps-wm-tg">TELANGANA</span>
        <span className="ps-watermark ps-wm-ka">KARNATAKA</span>

        {/* Compass Rose */}
        <div aria-hidden="true" className="ps-compass">
          <svg width="18" height="26" viewBox="0 0 18 26">
            <path d="M9 1l6 16-6-4-6 4z" fill="#9AA1AE" />
          </svg>
          <span>N</span>
        </div>

        {/* SVG Drawing Layer */}
        <svg
          viewBox="0 0 860 650"
          className="ps-map-svg"
          role="img"
          aria-label="Map of Maharashtra with 35 interactive district cells"
        >
          <defs>
            <filter id="psMapGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* State Boundary Outer Glow Stroke */}
          <path
            d={outlineD}
            fill="none"
            stroke="#F2A65A"
            strokeWidth="12"
            strokeOpacity="0.25"
            filter="url(#psMapGlow)"
          />

          {/* State Boundary Fill Base */}
          <path
            d={outlineD}
            fill="#0A0E14"
            stroke="#FFD9A8"
            strokeWidth="2.4"
            strokeLinejoin="round"
          />

          {/* 35 Voronoi Clipped District Polygon Paths */}
          {cities.map((city) => {
            const isSelected = activeCity ? city.id === activeCity.id : false;
            const isHovered = city.id === hoveredId;

            let cellFill = 'rgba(255, 255, 255, 0.02)';
            let cellStroke = 'rgba(255, 255, 255, 0.12)';
            let strokeWidth = 1;

            if (isSelected) {
              cellFill = 'rgba(242, 166, 90, 0.28)';
              cellStroke = '#F2A65A';
              strokeWidth = 2.2;
            } else if (isHovered) {
              cellFill = 'rgba(242, 166, 90, 0.16)';
              cellStroke = 'rgba(242, 166, 90, 0.7)';
              strokeWidth = 1.6;
            }

            return (
              <path
                key={city.id}
                d={city.d}
                fill={cellFill}
                stroke={cellStroke}
                strokeWidth={strokeWidth}
                strokeLinejoin="round"
                className="ps-district-cell"
                onClick={() => onSelectDistrict && onSelectDistrict(city)}
                onMouseEnter={() => setHoveredId(city.id)}
                onMouseLeave={() => setHoveredId(null)}
                role="button"
                tabIndex={0}
                aria-label={`${city.name} District (${city.region})`}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    if (onSelectDistrict) onSelectDistrict(city);
                  }
                }}
              />
            );
          })}
        </svg>

        {/* 35 Interactive District Pin Buttons */}
        {cities.map((city) => {
          const isSelected = activeCity ? city.id === activeCity.id : false;
          const isHovered = city.id === hoveredId;

          const leftPercent = (city.x / MAP_WIDTH) * 100;
          const topPercent = (city.y / MAP_HEIGHT) * 100;

          // Side alignment for label chip matching authentic prototype
          const SIDE_STYLES = {
            r: { left: '100%', top: '50%', transform: 'translateY(-50%)', marginLeft: '6px' },
            l: { right: '100%', top: '50%', transform: 'translateY(-50%)', marginRight: '6px' },
            b: { top: '100%', left: '50%', transform: 'translateX(-50%)', marginTop: '6px' }
          };
          const sideStyle = SIDE_STYLES[city.side] || SIDE_STYLES.r;

          // Dot styling - uniform across all districts without glowing or pulsing
          let dotBg = '#8890A0';
          let dotBorder = '#07090D';
          let dotGlow = 'none';

          if (isSelected) {
            dotBg = '#F2A65A';
            dotBorder = '#FFFFFF';
            dotGlow = '0 0 14px rgba(242, 166, 90, 0.8)';
          } else if (isHovered) {
            dotBg = '#FFD9A8';
            dotGlow = '0 0 8px rgba(255, 217, 168, 0.4)';
          }

          const zIndex = isSelected ? 30 : isHovered ? 25 : 10;

          return (
            <button
              key={city.id}
              type="button"
              className={`ps-map-pin-btn ${isSelected ? 'is-active-pin' : ''}`}
              style={{
                left: `${leftPercent.toFixed(2)}%`,
                top: `${topPercent.toFixed(2)}%`,
                zIndex
              }}
              onClick={() => onSelectDistrict && onSelectDistrict(city)}
              onMouseEnter={() => setHoveredId(city.id)}
              onMouseLeave={() => setHoveredId(null)}
              aria-label={`${city.name} District`}
              title={city.name}
            >
              <span
                className="ps-pin-dot"
                style={{
                  background: dotBg,
                  border: `2px solid ${dotBorder}`,
                  boxShadow: dotGlow
                }}
              />
              <span
                className={`ps-pin-chip ${isSelected ? 'is-selected' : ''}`}
                style={sideStyle}
              >
                {city.shortName}
              </span>
            </button>
          );
        })}
      </div>

      {/* 3. District Inspector Panel (Statewide Scope or Selected District) */}
      {isStatewide ? (
        <div className="ps-district-inspector">
          <div className="ps-inspector-main">
            <div className="ps-inspector-title-row">
              <div>
                <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary-dark)' }}>
                  Statewide Scope · 6 Administrative Divisions
                </span>
                <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '24px', fontWeight: 700, color: '#FFFFFF', marginTop: '2px' }}>
                  Maharashtra
                </h3>
              </div>

              <div>
                <span className="ps-chip ps-chip-support" style={{ fontSize: '13px', padding: '6px 14px' }}>
                  36 Districts
                </span>
              </div>
            </div>

            <p style={{ fontSize: '14px', color: 'var(--text-secondary-dark)', lineHeight: 1.5, marginTop: '8px' }}>
              Statewide simulation spans all 36 administrative districts. Click any district pin or boundary on the map to inspect its demographic baseline, local outcomes, and constituent talukas.
            </p>
          </div>
        </div>
      ) : activeCity ? (
        <div className="ps-district-inspector">
          <div className="ps-inspector-main">
            <div className="ps-inspector-title-row">
              <div>
                <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary-dark)' }}>
                  {activeCity.region} Region · Administrative Division
                </span>
                <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '24px', fontWeight: 700, color: '#FFFFFF', marginTop: '2px' }}>
                  {activeCity.name}
                </h3>
              </div>

              <div>
                <span className="ps-chip ps-chip-neutral" style={{ fontSize: '13px', padding: '6px 14px' }}>
                  {activeCity.region} Division
                </span>
              </div>
            </div>

            <p style={{ fontSize: '14px', color: 'var(--text-secondary-dark)', lineHeight: 1.5, marginTop: '8px' }}>
              {activeCity.name} District demographic baseline is anchored in regional division benchmarks and Census distributions. Multi-step policy simulations are fully supported.
            </p>

            {/* Simulation Metrics Grid (Only when valid simulation results are available) */}
            {activeSummary && (
              <div
                style={{
                  marginTop: '12px',
                  padding: '12px',
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid rgba(242, 166, 90, 0.25)',
                  borderRadius: 'var(--radius-md)'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#F2A65A', fontWeight: 600 }}>
                    Simulated Outcomes (Statewide Run)
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary-dark)' }}>
                    {activeCity.id === 'mumbai' ? 'Mumbai City Division' : activeCity.name}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: '8px' }}>
                  <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '8px 10px', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-secondary-dark)' }}>Personas</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: '#FFFFFF', marginTop: '2px' }}>
                      {activeSummary.total_personas ?? activeSummary.cohort_size ?? 0}
                    </div>
                  </div>

                  <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '8px 10px', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-secondary-dark)' }}>Eligible</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: '#FFFFFF', marginTop: '2px' }}>
                      {activeSummary.eligible_count ?? 0}
                      <span style={{ fontSize: '11px', fontWeight: 400, color: 'var(--text-secondary-dark)', marginLeft: '4px' }}>
                        ({(Number(activeSummary.eligibility_rate ?? 0) * 100).toFixed(0)}%)
                      </span>
                    </div>
                  </div>

                  <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '8px 10px', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-secondary-dark)' }}>Uptake</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: '#FFFFFF', marginTop: '2px' }}>
                      {activeSummary.realized_uptake_count ?? 0}
                      <span style={{ fontSize: '11px', fontWeight: 400, color: 'var(--text-secondary-dark)', marginLeft: '4px' }}>
                        ({(Number(activeSummary.realized_uptake_rate ?? 0) * 100).toFixed(0)}%)
                      </span>
                    </div>
                  </div>

                  <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '8px 10px', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-secondary-dark)' }}>Fee Relief</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: '#F2A65A', marginTop: '2px' }}>
                      {formatINR(activeSummary.total_estimated_fee_relief_inr)}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeApiMeta?.talukas && activeApiMeta.talukas.length > 0 && (
              <div style={{ marginTop: '10px', fontSize: '12px', lineHeight: 1.5 }}>
                <strong style={{ color: 'var(--text-primary-dark)' }}>Constituent Talukas ({activeApiMeta.talukas.length}):</strong>{' '}
                <span style={{ color: 'var(--text-secondary-dark)' }}>
                  {activeApiMeta.talukas.join(', ')}
                </span>
              </div>
            )}
          </div>

          {/* Action Button */}
          <div className="ps-inspector-action">
            <button
              type="button"
              className="ps-btn-primary"
              style={{ minHeight: '40px', fontSize: '13px', width: '100%' }}
              onClick={() => {
                if (onSelectDistrict) onSelectDistrict(activeCity);
                const el = document.getElementById('policy-controls-section');
                if (el) el.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              {hasStatewideResults
                ? `View ${activeCity.name} Results`
                : `Configure ${activeCity.name} Simulation`}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
