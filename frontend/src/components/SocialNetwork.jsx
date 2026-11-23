import React from 'react';

const shortenText = (text, maxLength = 180) => {
  if (!text) return '';
  const cleaned = text.trim();
  if (cleaned.length <= maxLength) return cleaned;

  // Try to cut at first sentence boundary if reasonable
  const firstSentenceEnd = cleaned.search(/[.!?]\s/);
  if (firstSentenceEnd > 60 && firstSentenceEnd <= maxLength) {
    return cleaned.slice(0, firstSentenceEnd + 1);
  }

  // Otherwise cut at nearest word boundary
  const cut = cleaned.slice(0, maxLength);
  const lastSpace = cut.lastIndexOf(' ');
  const truncated = lastSpace > 90 ? cut.slice(0, lastSpace) : cut;
  return truncated.replace(/[,;:]$/, '') + '…';
};

export default function SocialNetwork({ interactions }) {
  const interactionList = Array.isArray(interactions) ? interactions : [];

  return (
    <section className="section" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', marginBottom: '4px' }}>
        <h2 className="section-title" style={{ margin: 0 }}>AI Persona Interactions</h2>
        {interactionList.length > 0 && (
          <span className="ps-chip ps-chip-support" style={{ fontSize: '11px', padding: '2px 10px' }}>
            {interactionList.length} Exchange{interactionList.length === 1 ? '' : 's'} Logged
          </span>
        )}
      </div>
      <p className="section-subtitle">
        Peer-to-peer dialogue and information diffusion between student personas.
      </p>

      {interactionList.length === 0 ? (
        <div style={{ padding: '24px', textAlign: 'center', background: 'var(--bg-card-subtle, #FAFAFA)', borderRadius: 'var(--radius-md, 8px)', border: '1px solid var(--border-light, #E2E8F0)', marginTop: '16px' }}>
          <p className="text-muted" style={{ margin: 0, fontSize: '13px' }}>
            No peer interactions occurred in this simulation run.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '16px' }}>
          {interactionList.map((item, idx) => {
            const senderName = item.sender_name || item.sender_id || 'Persona A';
            const senderId = item.sender_id || '';
            const receiverName = item.receiver_name || item.receiver_id || 'Persona B';
            const receiverId = item.receiver_id || '';
            const msg = item.sender_message || item.message || '';
            const resp = item.receiver_response || item.response || '';
            const stateChanges = item.state_changes || {};

            return (
              <div
                key={idx}
                style={{
                  background: 'var(--bg-card-subtle, #FAFAFA)',
                  border: '1px solid var(--border-light, #E2E8F0)',
                  borderRadius: 'var(--radius-md, 8px)',
                  padding: '16px 20px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)'
                }}
              >
                {/* Header: Participants and Round */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', paddingBottom: '10px', borderBottom: '1px solid var(--border-light, #E2E8F0)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary-light, #0F172A)', fontSize: '13px' }}>
                      {senderName}
                    </span>
                    {senderId && (
                      <span style={{ fontSize: '11px', color: 'var(--text-muted-light, #64748B)', background: '#EDF2F7', padding: '1px 6px', borderRadius: '4px' }}>
                        {senderId}
                      </span>
                    )}
                    <span style={{ color: 'var(--accent-terracotta, #C25E38)', fontWeight: 700, fontSize: '14px', padding: '0 2px' }}>
                      →
                    </span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary-light, #0F172A)', fontSize: '13px' }}>
                      {receiverName}
                    </span>
                    {receiverId && (
                      <span style={{ fontSize: '11px', color: 'var(--text-muted-light, #64748B)', background: '#EDF2F7', padding: '1px 6px', borderRadius: '4px' }}>
                        {receiverId}
                      </span>
                    )}
                  </div>
                  <span className="ps-chip ps-chip-neutral" style={{ fontSize: '11px', padding: '2px 10px' }}>
                    Round {item.simulation_step ?? item.step ?? 1}
                  </span>
                </div>

                {/* Short Sections & Clear Labels */}
                <div style={{ display: 'grid', gridTemplateColumns: resp ? 'repeat(auto-fit, minmax(280px, 1fr))' : '1fr', gap: '12px' }}>
                  {msg && (
                    <div style={{ background: '#FFFFFF', padding: '10px 14px', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
                      <div style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--accent-terracotta, #C25E38)', marginBottom: '4px' }}>
                        Information Shared
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--text-primary-light, #1E293B)', lineHeight: 1.5 }}>
                        &ldquo;{shortenText(msg)}&rdquo;
                      </div>
                    </div>
                  )}

                  {resp && (
                    <div style={{ background: '#FFFFFF', padding: '10px 14px', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
                      <div style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#0369A1', marginBottom: '4px' }}>
                        Response
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--text-primary-light, #1E293B)', lineHeight: 1.5 }}>
                        &ldquo;{shortenText(resp)}&rdquo;
                      </div>
                    </div>
                  )}
                </div>

                {/* Impact on Receiver Section */}
                {stateChanges && Object.keys(stateChanges).length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', paddingTop: '2px' }}>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary-light, #64748B)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Impact on {receiverName}:
                    </span>
                    {Object.entries(stateChanges).map(([key, val]) => {
                      const label = key.replace(/_/g, ' ');
                      const formattedVal = typeof val === 'number'
                        ? (val > 0 ? `+${(val * 100).toFixed(0)}%` : `${(val * 100).toFixed(0)}%`)
                        : String(val);
                      return (
                        <span
                          key={key}
                          className="ps-chip ps-chip-support"
                          style={{ fontSize: '11px', padding: '2px 8px', fontWeight: 600 }}
                        >
                          {label}: {formattedVal}
                        </span>
                      );
                    })}
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
