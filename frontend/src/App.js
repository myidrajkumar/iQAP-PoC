import React from 'react';
import { useTestApi } from './hooks/useTestApi';
import Header from './components/Header';
import TestForm from './components/TestForm';
import ResultsTable from './components/ResultsTable';
import './App.css';

function App() {
  const { results, isLoading, error, statusMessage, fetchResults, generateTest } = useTestApi();

  return (
    <div className="container">
      <Header />
      <main>
        <div className="form-grid">
          <TestForm
            isLoading={isLoading}
            error={error}
            statusMessage={statusMessage}
            onGenerate={generateTest}
          />
          <ResultsTable results={results} onRefresh={fetchResults} />
        </div>
      </main>
    </div>
  );
}

export default App;