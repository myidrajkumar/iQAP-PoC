import React from 'react';

const TestStep = ({ index, step, onStepChange, onDeleteStep }) => {
  const availableActions = ['CLICK', 'ENTER_TEXT', 'VERIFY_ELEMENT_VISIBLE'];

  return (
    <div className="step-card-editor">
      <div className="step-number">{step.step}</div>
      <div className="step-form">
        <div className="form-row">
          <label>Action</label>
          <select
            value={step.action}
            onChange={(e) => onStepChange(index, 'action', e.target.value)}
          >
            {availableActions.map((action) => (
              <option key={action} value={action}>
                {action}
              </option>
            ))}
          </select>
        </div>

        <div className="form-row">
          <label>Target Element</label>
          <input
            type="text"
            placeholder="e.g., login-button"
            value={step.target_element || ''}
            onChange={(e) => onStepChange(index, 'target_element', e.target.value)}
          />
        </div>

        {/* Conditionally render the Data Key input only if the action is ENTER_TEXT */}
        {step.action === 'ENTER_TEXT' && (
          <div className="form-row">
            <label>Data Key</label>
            <input
              type="text"
              placeholder="e.g., username"
              value={step.data_key || ''}
              onChange={(e) => onStepChange(index, 'data_key', e.target.value)}
            />
          </div>
        )}
      </div>
      <button onClick={() => onDeleteStep(index)} className="delete-step-btn" title="Delete Step">
        &times;
      </button>
    </div>
  );
};

export default TestStep;