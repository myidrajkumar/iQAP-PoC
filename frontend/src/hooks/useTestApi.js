import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const reportingApiUrl = process.env.REACT_APP_REPORTING_URL || 'http://localhost:8002';
const orchestratorApiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const useTestApi = () => {
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false); // For generation
  const [isExecuting, setIsExecuting] = useState(false); // For execution
  const [error, setError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [testCase, setTestCase] = useState(null); // <-- Holds the generated test case JSON

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
    setTestCase(null);
    setStatusMessage('Generating test case via Gemini...');
    try {
      const response = await axios.post(`${orchestratorApiUrl}/api/v1/generate-test-case`, {
        requirement: requirement,
        target_url: targetUrl,
      });
      setTestCase(response.data); // <-- Store the returned JSON
      setStatusMessage('');
    } catch (err) {
      const errorMessage = err.response?.data?.detail || "Failed to generate test case.";
      setError(`Error: ${errorMessage}`);
      setStatusMessage('');
    } finally {
      setIsLoading(false);
    }
  };

  const runTest = async (testCaseToRun) => {
    setIsExecuting(true);
    setError('');
    setStatusMessage('Publishing job for execution...');
    try {
      const response = await axios.post(`${orchestratorApiUrl}/api/v1/publish-test-case`, testCaseToRun);
      setStatusMessage(response.data.message || "Job published successfully!");
      setTestCase(null); // <-- Return to the main form screen
      setTimeout(fetchResults, 5000); // Poll for results after a delay
    } catch (err) {
        const errorMessage = err.response?.data?.detail || "Failed to publish job.";
        setError(`Error: ${errorMessage}`);
        setStatusMessage('');
    } finally {
        setIsExecuting(false);
    }
  };


  return { results, isLoading, isExecuting, error, statusMessage, testCase, fetchResults, generateTest, runTest, setTestCase };
};