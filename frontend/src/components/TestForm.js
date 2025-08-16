import React, { useState } from 'react';

const TestForm = ({ isLoading, error, statusMessage, onGenerate }) => {
  const [requirement, setRequirement] = useState("Verify a user can log in with valid credentials, and then log out.");
  const [targetUrl, setTargetUrl] = useState("https://www.saucedemo.com");

  const handleSubmit = (e) => {
    e.preventDefault();
    onGenerate(requirement, targetUrl);
  };

  return (
    <div className="form-left">
      <h3>Generate New Test</h3>
      <form onSubmit={handleSubmit}>
        <label htmlFor="target-url-input">Target URL:</label>
        <input id="target-url-input" type="text" value={targetUrl} onChange={(e) => setTargetUrl(e.target.value)} />
        <label htmlFor="requirement-input">Business Requirement:</label>
        <textarea id="requirement-input" value={requirement} onChange={(e) => setRequirement(e.target.value)} rows="4" />
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Processing...' : 'Generate & Run Test'}
        </button>
      </form>
      {statusMessage && <div className="status">{statusMessage}</div>}
      {error && <div className="error">{error}</div>}
    </div>
  );
};

export default TestForm;