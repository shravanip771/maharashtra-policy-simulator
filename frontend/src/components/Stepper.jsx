import React from 'react';

/**
 * 3-Step Process Stepper
 * Directly mirrors the step indicators from the original prototype reference.
 */
export default function Stepper({ currentStep = 1 }) {
  const steps = [
    { num: 1, label: 'Set terms and run the policy' },
    { num: 2, label: 'Read the overall result' },
    { num: 3, label: 'Click a city for its personas' }
  ];

  return (
    <ol aria-label="Simulation Steps" className="ps-stepper">
      {steps.map((step) => {
        const isActive = step.num === currentStep;
        const isDone = step.num < currentStep;
        const itemClass = isActive || isDone ? 'ps-step-item is-active' : 'ps-step-item is-pending';

        return (
          <li key={step.num} className={itemClass}>
            <span aria-hidden="true" className="ps-step-num">
              {isDone ? '✓' : step.num}
            </span>
            <span>{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
