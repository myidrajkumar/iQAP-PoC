import React from 'react';

const TestStep = ({ step }) => {
  return (
    <div className="step-card">
      <div className="step-number">{step.step}</div>
      <div className="step-details">
        <p>
          <span className="action">{step.action}: </span>
          {step.action === 'CLICK' && (
            <span>
              Click on element <span className="target">{step.target_element}</span>
            </span>
          )}
          {step.action === 'ENTER_TEXT' && (
            <span>
              Enter text from dataset key{' '}
              <span className="target">{step.data_key}</span> into element{' '}
              <span className="target">{step.target_element}</span>
            </span>
          )}
          {step.action === 'VERIFY_ELEMENT_VISIBLE' && (
            <span>
              Verify element <span className="target">{step.target_element}</span> is visible
            </span>
          )}
        </p>
      </div>
    </div>
  );
};

export default TestStep;