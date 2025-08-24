import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTestApi } from '../hooks/useTestApi';
import TestForm from '../components/TestForm';
import TestCaseEditor from '../components/TestCaseEditor';
import './AuthoringPage.css';

function AuthoringPage() {
  const navigate = useNavigate();
  const {
    isLoading,
    isExecuting,
    error,
    statusMessage,
    testCase,
    generateTest,
    runTest,
    setTestCase,
  } = useTestApi();

  const handleRunTest = (testCaseToRun, isLiveView = false) => {
      runTest(testCaseToRun, navigate, isLiveView);
  };

  return (
    <div className="authoring-container">
      {/* --- THE FIX: Updated Titles --- */}
      <h1>Test Studio</h1>
      <p>Design, generate, and edit your automated tests in one place.</p>
      
      <div className="authoring-workspace">
        {testCase ? (
          <TestCaseEditor
            testCase={testCase}
            isExecuting={isExecuting}
            onRunTest={handleRunTest}
            onGoBack={() => setTestCase(null)}
          />
        ) : (
          <TestForm
            isLoading={isLoading}
            error={error}
            statusMessage={statusMessage}
            onGenerate={generateTest}
          />
        )}
      </div>
    </div>
  );
}

export default AuthoringPage;