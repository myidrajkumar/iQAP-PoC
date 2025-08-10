import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [requirement, setRequirement] = useState("Verify a user can log in with valid credentials and see the dashboard.");
  const [testCase, setTestCase] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleGenerate = async () => {
    setIsLoading(true);
    setError('');
    setTestCase(null);
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await axios.post(`${apiUrl}/generate-test-case`, {
        requirement: requirement
      });
      setTestCase(response.data);
    } catch (err) {
      setError("Failed to generate test case. Is the backend running? Check terminal logs for details.");
      console.error(err);
    }
    setIsLoading(false);
  };

  return (
    <div className="container">
      <header>
        <h1>iQAP - Intelligent Quality Assurance Platform (PoC)</h1>
      </header>
      <main>
        <div className="form">
          <label htmlFor="requirement-input">Enter Business Requirement:</label>
          <textarea
            id="requirement-input"
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            rows="4"
          />
          <button onClick={handleGenerate} disabled={isLoading}>
            {isLoading ? 'Generating...' : 'Generate Test Case'}
          </button>
        </div>
        {error && <div className="error">{error}</div>}
        {testCase && (
          <div className="result">
            <h2>Generated Test Case (JSON)</h2>
            <pre>{JSON.stringify(testCase, null, 2)}</pre>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;