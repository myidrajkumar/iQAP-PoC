import React from 'react';
import { useTestApi } from '../hooks/useTestApi';
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
  } = useTestApi();

  return (
    <div className="authoring-container">
      <h1>Author New Test</h1>
      <p>Generate a test case from a business requirement or build one from scratch.</p>
      
      <div className="authoring-workspace">
        {testCase ? (
          <TestCaseEditor
            testCase={testCase}
            isExecuting={isExecuting}
            onRunTest={runTest}
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