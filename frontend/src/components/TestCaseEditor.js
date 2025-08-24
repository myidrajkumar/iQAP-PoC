import React, { useState, useEffect } from 'react';
import TestStep from './TestStep';

const TestCaseEditor = ({ testCase, isExecuting, onRunTest, onGoBack }) => {
  const [editableTestCase, setEditableTestCase] = useState(testCase);

  useEffect(() => {
    setEditableTestCase(testCase);
  }, [testCase]);

  const handleStepChange = (index, field, value) => {
    const updatedSteps = [...editableTestCase.steps];
    updatedSteps[index] = { ...updatedSteps[index], [field]: value };
    setEditableTestCase({ ...editableTestCase, steps: updatedSteps });
  };

  const handleDeleteStep = (index) => {
    const updatedSteps = editableTestCase.steps.filter((_, i) => i !== index);
    const renumberedSteps = updatedSteps.map((step, i) => ({ ...step, step: i + 1 }));
    setEditableTestCase({ ...editableTestCase, steps: renumberedSteps });
  };

  const handleAddStep = () => {
    const newStep = {
      step: editableTestCase.steps.length + 1,
      action: 'CLICK',
      target_element: '',
      data_key: '',
    };
    setEditableTestCase({
      ...editableTestCase,
      steps: [...editableTestCase.steps, newStep],
    });
  };

  const handleObjectiveChange = (e) => {
    setEditableTestCase({ ...editableTestCase, objective: e.target.value });
  };

  if (!editableTestCase) return null;

  return (
    <div className="test-case-editor">
      <div className="editor-header">
        <h3>Edit & Review Test Case</h3>
        <label htmlFor="objective-input">Objective:</label>
        <input
          id="objective-input"
          type="text"
          value={editableTestCase.objective}
          onChange={handleObjectiveChange}
          className="objective-input"
        />
      </div>

      <div className="steps-container">
        {editableTestCase.steps.map((step, index) => (
          <TestStep
            key={index}
            index={index}
            step={step}
            onStepChange={handleStepChange}
            onDeleteStep={handleDeleteStep}
          />
        ))}
      </div>

      <button onClick={handleAddStep} className="add-step-btn">
        + Add New Step
      </button>

      <div className="editor-actions">
        <button onClick={() => onRunTest(editableTestCase, false)} disabled={isExecuting}>
          {isExecuting ? 'Publishing...' : 'Approve & Run Test'}
        </button>
        
        <button onClick={() => onRunTest(editableTestCase, true)} className="secondary-btn" disabled={isExecuting}>
          Run with Live View
        </button>

        <button onClick={onGoBack} className="secondary-btn" disabled={isExecuting}>
          Cancel
        </button>
      </div>
    </div>
  );
};

export default TestCaseEditor;