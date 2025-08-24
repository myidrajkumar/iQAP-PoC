import React, { useState, useEffect } from 'react';
import TestStep from './TestStep';

const TestCaseEditor = ({ testCase, isExecuting, onRunTest, onGoBack }) => {
  // Create a local, editable copy of the test case
  const [editableTestCase, setEditableTestCase] = useState(testCase);

  // If the parent component provides a new test case, update our local copy
  useEffect(() => {
    setEditableTestCase(testCase);
  }, [testCase]);

  // Handler to update a specific field of a step
  const handleStepChange = (index, field, value) => {
    const updatedSteps = [...editableTestCase.steps];
    updatedSteps[index] = { ...updatedSteps[index], [field]: value };
    setEditableTestCase({ ...editableTestCase, steps: updatedSteps });
  };

  // Handler to delete a step
  const handleDeleteStep = (index) => {
    const updatedSteps = editableTestCase.steps.filter((_, i) => i !== index);
    // Re-number the steps after deletion
    const renumberedSteps = updatedSteps.map((step, i) => ({ ...step, step: i + 1 }));
    setEditableTestCase({ ...editableTestCase, steps: renumberedSteps });
  };

  // Handler to add a new, blank step at the end
  const handleAddStep = () => {
    const newStep = {
      step: editableTestCase.steps.length + 1,
      action: 'CLICK', // Default action
      target_element: '',
      data_key: '',
    };
    setEditableTestCase({
      ...editableTestCase,
      steps: [...editableTestCase.steps, newStep],
    });
  };

  // Handler to update the main objective
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
            key={index} // Using index as key is acceptable here as we are managing the array
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
        {/* Run the test with the MODIFIED version */}
        <button onClick={() => onRunTest(editableTestCase)} disabled={isExecuting}>
          {isExecuting ? 'Publishing...' : 'Approve & Run Test'}
        </button>
        <button onClick={onGoBack} className="secondary-btn" disabled={isExecuting}>
          Cancel
        </button>
      </div>
    </div>
  );
};

export default TestCaseEditor;