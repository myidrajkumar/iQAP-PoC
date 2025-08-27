import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import './TestResultDetailPage.css';

const reportingApiUrl = process.env.REACT_APP_REPORTING_URL || 'http://localhost:8002';
const minioBaseUrl = 'http://localhost:9000/test-artifacts'; // Your MinIO bucket URL

const TestResultDetailPage = () => {
  const { runId } = useParams();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchResult = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${reportingApiUrl}/results/${runId}`);
        setResult(response.data);
      } catch (err) {
        setError('Failed to fetch test result details.');
      } finally {
        setLoading(false);
      }
    };
    fetchResult();
  }, [runId]);

  if (loading) return <div>Loading...</div>;
  if (error) return <div className="error">{error}</div>;
  if (!result) return <div>Test result not found.</div>;

  const screenshotUrl = `${minioBaseUrl}/${result.artifacts_path}/failure.png`;
  const traceUrl = `${minioBaseUrl}/${result.artifacts_path}/trace.zip`;

  return (
    <div className="detail-container">
      <Link to="/runs" className="back-link">&larr; Back to Test Runs</Link>
      <h2>Test Run Details (ID: {result.id})</h2>
      
      <div className="detail-grid">
        <div className="detail-item">
          <strong>Objective:</strong>
          <p>{result.objective}</p>
        </div>
        <div className="detail-item">
          <strong>Test Case ID:</strong>
          <p>{result.test_case_id}</p>
        </div>
        <div className="detail-item">
          <strong>Timestamp:</strong>
          <p>{new Date(result.timestamp).toLocaleString()}</p>
        </div>
        <div className="detail-item">
          <strong>Status:</strong>
          <p>
            <span className={`status-badge status-${result.status?.toLowerCase()}`}>{result.status}</span>
            <span className={`status-badge status-${result.visual_status?.toLowerCase()?.replace(/_/g, '-') || 'n-a'}`}>{result.visual_status || 'N/A'}</span>
          </p>
        </div>
      </div>

      {result.status === 'FAIL' && (
        <div className="failure-section">
          <h3>Failure Analysis</h3>
          <div className="failure-reason">
            <strong>Reason:</strong>
            <pre>{result.failure_reason}</pre>
          </div>
          <h4>Debugging Artifacts:</h4>
          <div className="artifacts">
            <a href={screenshotUrl} target="_blank" rel="noopener noreferrer" className="artifact-link">View Failure Screenshot</a>
            <a href={traceUrl} target="_blank" rel="noopener noreferrer" className="artifact-link">Download Playwright Trace</a>
          </div>
        </div>
      )}

      {result.visual_status === 'FAIL' && result.visual_artifacts && result.visual_artifacts.length > 0 && (
        <div className="failure-section">
            <h3>Visual Failure Analysis</h3>
            <p>The following visual checks failed because they did not match their approved baselines.</p>
            <div className="artifacts">
              {result.visual_artifacts.map((artifactName, index) => (
                <a 
                  key={index}
                  href={`${minioBaseUrl}/${result.artifacts_path}/${artifactName}`} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="artifact-link"
                >
                  View Failure: {artifactName.replace(/_/g, ' ').replace('.png', '')}
                </a>
              ))}
            </div>
        </div>
      )}
    </div>
  );
};

export default TestResultDetailPage;