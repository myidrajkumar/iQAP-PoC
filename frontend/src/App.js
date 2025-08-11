import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [requirement, setRequirement] = useState("Verify a user can log in with valid credentials and see the dashboard.");
  const [targetUrl, setTargetUrl] = useState("https://www.saucedemo.com");
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');

  const reportingApiUrl = process.env.REACT_APP_REPORTING_URL || 'http://localhost:8002';
  const orchestratorApiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const fetchResults = useCallback(async () => {
    try {
      const response = await axios.get(`${reportingApiUrl}/results`);
      setResults(response.data);
    } catch (err) {
      console.error("Failed to fetch results", err);
      setError("Could not load test results. Is the reporting service running?");
    }
  }, [reportingApiUrl]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  const handleGenerate = async () => {
    setIsLoading(true);
    setError('');
    setStatusMessage('Generating test case...');
    try {
      const response = await axios.post(`${orchestratorApiUrl}/generate-test-case`, {
        requirement: requirement,
        target_url: targetUrl,
      });
      setStatusMessage(response.data.message || "Job published successfully!");
      // Poll for results after a short delay
      setTimeout(fetchResults, 3000); // Refresh results after 3 seconds
    } catch (err) {
      const errorMessage = err.response?.data?.detail || "Failed to publish job.";
      setError(`Error: ${errorMessage}`);
      setStatusMessage('');
    }
    setIsLoading(false);
  };

  return (
    <div className="container">
      <header><h1>iQAP - Intelligent Quality Assurance Platform v2.0</h1></header>
      <main>
        <div className="form-grid">
          <div className="form-left">
            <label htmlFor="target-url-input">Target URL:</label>
            <input id="target-url-input" type="text" value={targetUrl} onChange={(e) => setTargetUrl(e.target.value)} />
            <label htmlFor="requirement-input">Business Requirement:</label>
            <textarea id="requirement-input" value={requirement} onChange={(e) => setRequirement(e.target.value)} rows="4" />
            <button onClick={handleGenerate} disabled={isLoading}>
              {isLoading ? 'Processing...' : 'Generate & Run Test'}
            </button>
            {statusMessage && <div className="status">{statusMessage}</div>}
            {error && <div className="error">{error}</div>}
          </div>
          <div className="form-right">
            <h3>Test Run History</h3>
            <button className="refresh-btn" onClick={fetchResults}>Refresh Results</button>
            <div className="results-table-container">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Objective</th>
                    <th>Status</th>
                    <th>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {results.length > 0 ? results.map((result) => (
                    <tr key={result.id}>
                      <td>{result.id}</td>
                      <td>{result.objective}</td>
                      <td><span className={`status-badge status-${result.status?.toLowerCase()}`}>{result.status}</span></td>
                      <td>{new Date(result.timestamp).toLocaleString()}</td>
                    </tr>
                  )) : (
                    <tr><td colSpan="4">No results found.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;