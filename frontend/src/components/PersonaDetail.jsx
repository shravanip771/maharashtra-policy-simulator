import React from 'react';

export default function PersonaDetail({ persona, onClose }) {
  if (!persona) return null;

  const formatINR = (val) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(val || 0);
  };

  const personaId = persona.persona_id || 'ID';
  const name = persona.name || 'Student';
  const course = persona.course_name || persona.course || 'General Degree';
  const age = persona.age || 19;
  const district = persona.district || 'Dhule';
  const income = Number(persona.family_income ?? persona.annual_family_income_inr ?? 0);
  const isEligible = persona.is_statutorily_eligible ?? persona.statutory_eligibility ?? false;
  const awareness = Number(persona.final_awareness ?? persona.awareness ?? 0);
  const state = persona.final_state || persona.current_state || 'UNAWARE';
  const reasoning = persona.inner_monologue || persona.stated_intention || 'No reasoning trace recorded.';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">{name} ({personaId})</h3>
          <button type="button" className="btn-close" onClick={onClose}>×</button>
        </div>

        <div className="detail-grid">
          <div className="detail-item">
            <span className="detail-label">Persona ID</span>
            <span className="detail-value">{personaId}</span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Course</span>
            <span className="detail-value">{course}</span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Age</span>
            <span className="detail-value">{age} years</span>
          </div>

          <div className="detail-item">
            <span className="detail-label">District</span>
            <span className="detail-value">{district}</span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Family Income</span>
            <span className="detail-value">{formatINR(income)} / year</span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Eligibility</span>
            <span className="detail-value">
              {isEligible ? '✓ Eligible' : '✕ Not eligible'}
            </span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Awareness</span>
            <span className="detail-value">{(awareness * 100).toFixed(0)}%</span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Current Outcome</span>
            <span className="detail-value">{state}</span>
          </div>
        </div>

        <div className="reasoning-box">
          <div className="reasoning-title">AI reasoning</div>
          <div className="reasoning-text">"{reasoning}"</div>
        </div>
      </div>
    </div>
  );
}
