import React from 'react';

export default function PersonaTable({ personas, onSelectPersona }) {
  if (!personas || !Array.isArray(personas) || personas.length === 0) {
    return (
      <section className="section">
        <h2 className="section-title">Personas</h2>
        <p className="section-subtitle">
          Each persona represents one synthetic student agent.
        </p>
        <p className="text-muted" style={{ padding: '16px 0' }}>
          No persona data available. Run simulation to populate.
        </p>
      </section>
    );
  }

  const formatOutcome = (state, isEligible) => {
    if (!isEligible) return 'Not eligible';
    switch (state) {
      case 'APPLIED':
      case 'COMPLETED':
        return 'Benefit Received';
      case 'INTENDING':
        return 'Intending to Apply';
      case 'CONSIDERING':
        return 'Considering';
      case 'AWARE':
        return 'Aware of Scheme';
      case 'UNAWARE':
        return 'Unaware';
      case 'DROPPED_OUT':
        return 'Dropped Out';
      default:
        return state || 'Unaware';
    }
  };

  return (
    <section className="section">
      <h2 className="section-title">Personas</h2>
      <p className="section-subtitle">
        Each persona represents one synthetic student agent. Click any row to view AI reasoning.
      </p>

      <div className="table-wrapper">
        <table className="persona-table">
          <thead>
            <tr>
              <th>Persona</th>
              <th>Course</th>
              <th>Eligible</th>
              <th>Awareness</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {personas.map((p) => {
              const personaId = p.persona_id || 'ID';
              const name = p.name || 'Student';
              const course = p.course_name || p.course || 'General Degree';
              const isEligible = p.is_statutorily_eligible ?? p.statutory_eligibility ?? false;
              const awareness = Number(p.final_awareness ?? p.awareness ?? 0);
              const state = p.final_state || p.current_state || 'UNAWARE';
              const outcomeText = formatOutcome(state, isEligible);

              return (
                <tr key={personaId} onClick={() => onSelectPersona(p)}>
                  <td>
                    <strong>{name}</strong>{' '}
                    <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                      ({personaId})
                    </span>
                  </td>
                  <td>{course}</td>
                  <td>
                    {isEligible ? (
                      <span className="badge badge-eligible">✓ Eligible</span>
                    ) : (
                      <span className="badge badge-ineligible">✕ Not eligible</span>
                    )}
                  </td>
                  <td>{(awareness * 100).toFixed(0)}%</td>
                  <td>
                    <span className="badge badge-outcome">{outcomeText}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
