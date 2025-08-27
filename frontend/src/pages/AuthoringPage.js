import React, { useState } from 'react';
import { useTestRun } from '../context/TestRunContext';
import './AuthoringPage.css';

function AuthoringPage() {
  const { isLoading, error, statusMessage, startTestJourney } = useTestRun();
  const [objective, setObjective] = useState("Verify a user can log in with valid credentials, and then log out.");
  const [targetUrl, setTargetUrl] = useState("https://www.saucedemo.com");

  const handleRun = (isLiveView) => {
    startTestJourney(objective, targetUrl, isLiveView);
  };

  return (
    <div className="authoring-container">
      <h1>Test Studio</h1>
      <p>Define an objective and let the AI agent autonomously execute the test journey.</p>
      
      <div className="authoring-workspace">
          <div className="form-left">
              <h3>Start New Test Journey</h3>
              <form onSubmit={(e) => e.preventDefault()}>
                  <label htmlFor="target-url-input">Target URL:</label>
                  <input id="target-url-input" type="text" value={targetUrl} onChange={(e) => setTargetUrl(e.target.value)} />
                  <label htmlFor="objective-input">Test Objective:</label>
                  <textarea id="objective-input" value={objective} onChange={(e) => setObjective(e.target.value)} rows="4" />
                  
                  <div className="editor-actions">
                      <button onClick={() => handleRun(false)} disabled={isLoading}>
                          {isLoading ? 'Starting...' : 'Run Journey'}
                      </button>
                      
                      <button onClick={() => handleRun(true)} className="secondary-btn" disabled={isLoading}>
                          Run with Live View
                      </button>
                  </div>
              </form>
              {statusMessage && <div className="status">{statusMessage}</div>}
              {error && <div className="error">{error}</div>}
          </div>
      </div>
    </div>
  );
}

export default AuthoringPage;