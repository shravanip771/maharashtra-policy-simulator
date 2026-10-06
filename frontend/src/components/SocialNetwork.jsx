import React from 'react';

export default function SocialNetwork({ interactions }) {
  const interactionList = Array.isArray(interactions) ? interactions : [];

  return (
    <section className="section">
      <h2 className="section-title">AI Persona Interactions</h2>
      <p className="section-subtitle">
        Personas can influence each other's awareness and behaviour.
      </p>

      {interactionList.length === 0 ? (
        <p className="text-muted" style={{ padding: '12px 0' }}>
          No interactions occurred in this simulation.
        </p>
      ) : (
        <div className="interaction-feed">
          {interactionList.map((item, idx) => {
            const senderName = item.sender_name || item.sender_id || 'Persona A';
            const senderId = item.sender_id || '';
            const receiverName = item.receiver_name || item.receiver_id || 'Persona B';
            const receiverId = item.receiver_id || '';
            const msg = item.sender_message || item.message || '';
            const resp = item.receiver_response || item.response || '';
            const stateChanges = item.state_changes || {};

            return (
              <div key={idx} className="interaction-item">
                <div className="interaction-header">
                  <span>
                    {senderName} ({senderId}) → {receiverName} ({receiverId})
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Round {item.simulation_step ?? item.step ?? 1}
                  </span>
                </div>

                {msg && (
                  <div className="interaction-dialogue">
                    "{msg}"
                  </div>
                )}

                {resp && (
                  <div className="interaction-dialogue" style={{ color: 'var(--text-secondary)' }}>
                    ↪ "{resp}"
                  </div>
                )}

                {stateChanges && Object.keys(stateChanges).length > 0 && (
                  <div className="interaction-delta">
                    Impact on receiver: {Object.entries(stateChanges).map(([k, v]) => (
                      <span key={k} style={{ marginRight: '8px' }}>
                        {k}: {typeof v === 'number' && v > 0 ? `+${(v * 100).toFixed(0)}%` : String(v)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
