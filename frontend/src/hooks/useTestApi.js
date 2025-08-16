import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const reportingApiUrl = process.env.REACT_APP_REPORTING_URL || 'http://localhost:8002';
const orchestratorApiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const useTestApi = () => {
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');

  const fetchResults = useCallback(async () => {
    try {
      const response = await axios.get(`${reportingApiUrl}/results`);
      setResults(response.data);
    } catch (err) {
      console.error("Failed to fetch results", err);
      setError("Could not load test results. Is the reporting service running?");
    }
  }, []);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  const generateTest = async (requirement, targetUrl) => {
    setIsLoading(true);
    setError('');
    setStatusMessage('Generating test case via Gemini...');
    try {
      const response = await axios.post(`${orchestratorApiUrl}/generate-test-case`, {
        requirement: requirement,
        target_url: targetUrl,
      });
      setStatusMessage(response.data.message || "Job published successfully!");
      setTimeout(fetchResults, 5000); // Poll for results after a delay
    } catch (err) {
      const errorMessage = err.response?.data?.detail || "Failed to publish job.";
      setError(`Error: ${errorMessage}`);
      setStatusMessage('');
    } finally {
      setIsLoading(false);
    }
  };

  return { results, isLoading, error, statusMessage, fetchResults, generateTest };
};