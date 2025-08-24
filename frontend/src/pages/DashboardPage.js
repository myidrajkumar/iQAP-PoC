import React from 'react';
import { useTestApi } from '../hooks/useTestApi';
import TestForm from '../components/TestForm';
import TestCaseEditor from '../components/TestCaseEditor';
import ResultsTable from '../components/ResultsTable';

function DashboardPage() {
  const {
    results,
    isLoading,
    isExecuting,
    error,
    statusMessage,
    testCase,
    fetchResults,
    generateTest,
    runTest,
    setTestCase,
  } = useTestApi();

  return (
    <div className="form-grid">
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
      <ResultsTable results={results} onRefresh={fetchResults} />
    </div>
  );
}

export default DashboardPage;