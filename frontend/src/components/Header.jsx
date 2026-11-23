import React from 'react';

/**
 * Global Header / Navigation Shell
 * Matches the visual design and typography from the original prototype reference.
 */
export default function Header({ userInitial = 'M', userName = 'Govt of Maharashtra' }) {
  return (
    <header className="ps-header">
      <div className="ps-header-inner">
        {/* Brand Treatment */}
        <div className="ps-brand-group">
          {/* Authentic Amber Brand Logo Icon from Prototype */}
          <svg
            className="ps-brand-icon"
            viewBox="0 0 32 32"
            aria-hidden="true"
          >
            <rect width="32" height="32" rx="9" fill="#F2A65A" />
            <path
              d="M8 21l5-6 4 3 7-9"
              fill="none"
              stroke="#05070A"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx="24" cy="9" r="2.2" fill="#05070A" />
          </svg>
          <div>
            <div className="ps-brand-title">Policy Simulator</div>
            <div className="ps-brand-subtitle">Maharashtra · city-level reaction testing</div>
          </div>
        </div>

        {/* Global Controls / User Status */}
        <div className="ps-header-actions">
          <div className="ps-user-badge">
            <span className="ps-avatar-initial" aria-hidden="true">
              {userInitial}
            </span>
            <span className="ps-user-name">{userName}</span>
          </div>

          <span
            className="ps-chip ps-chip-provisional"
            title="DTE Rajarshi Shahu EBC Baseline Configuration"
          >
            Stage 2.4 Baseline
          </span>
        </div>
      </div>
    </header>
  );
}
