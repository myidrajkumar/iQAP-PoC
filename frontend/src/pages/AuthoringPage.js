import React from 'react';
import { useTestRun } from '../context/TestRunContext'; // <-- Use the new context hook
import TestForm from '../components/TestForm';
import TestCaseEditor from '../components/TestCaseEditor';
import './AuthoringPage.css';

function AuthoringPage() {
  const {
    isLoading,
    isExecuting,
    error,
    statusMessage,
    testCase,
    generateTest,
    runTest,
    setTestCase,
  } = useTestRun(); // <-- Use the new context hook

  return (
    <div className="authoring-container">
      <h1>Test Studio</h1>
      <p>Design, generate, and edit your automated tests in one place.</p>
      
      <div className="authoring-workspace">
        {testCase ? (
          <TestCaseEditor
            testCase={testCase}
            isExecuting={isExecuting}
            onRunTest={runTest} // Pass runTest directly
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