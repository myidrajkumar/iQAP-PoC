import React from 'react';
import { useTestApi } from './hooks/useTestApi';
import Header from './components/Header';
import TestForm from './components/TestForm';
import TestCaseViewer from './components/TestCaseViewer'; // <-- Import new component
import ResultsTable from './components/ResultsTable';
import './App.css';

function App() {
  const {
    results,
    isLoading,
    isExecuting, // <-- New state for execution phase
    error,
    statusMessage,
    testCase, // <-- New state to hold the generated test case
    fetchResults,
    generateTest,
    runTest, // <-- New function to run the test
    setTestCase, // <-- New function to go back
  } = useTestApi();

  return (
    <div className="container">
      <Header />
      <main>
        <div className="form-grid">
          {/* --- Conditionally render Form or Viewer --- */}
          {testCase ? (
            <TestCaseViewer
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
      </main>
    </div>
  );
}

export default App;