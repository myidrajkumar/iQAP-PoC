import React from 'react';
import TestStep from './TestStep';

const TestCaseViewer = ({ testCase, isExecuting, onRunTest, onGoBack }) => {
  if (!testCase) return null;

  return (
    <div className="test-case-viewer">
      <div className="viewer-header">
        <h3>Generated Test Case for Review</h3>
        <p>{testCase.objective}</p>
      </div>

      <div className="steps-container">
        {testCase.steps.map((step) => (
          <TestStep key={step.step} step={step} />
        ))}
      </div>

      <div className="viewer-actions">
        <button onClick={() => onRunTest(testCase)} disabled={isExecuting}>
          {isExecuting ? 'Publishing...' : 'Approve & Run Test'}
        </button>
        <button onClick={onGoBack} className="secondary-btn" disabled={isExecuting}>
          Go Back & Edit
        </button>
      </div>
    </div>
  );
};

export default TestCaseViewer;