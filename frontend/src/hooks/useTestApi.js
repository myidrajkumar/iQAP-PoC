import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';

const reportingApiUrl = process.env.REACT_APP_REPORTING_URL || 'http://localhost:8002';
const orchestratorApiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Polling configuration
const POLLING_INTERVAL = 4000; // Check every 4 seconds
const POLLING_ATTEMPTS = 15;   // Stop after 15 attempts (1 minute)

export const useTestApi = () => {
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [testCase, setTestCase] = useState(null);

  // Use a ref to hold the polling interval ID so it persists across re-renders
  const pollingRef = useRef(null);

  const fetchResults = useCallback(async () => {
    try {
      const response = await axios.get(`${reportingApiUrl}/results`);
      setResults(response.data);
      return response.data; // Return data for polling logic
    } catch (err) {
      console.error("Failed to fetch results", err);
      setError("Could not load test results. Is the reporting service running?");
      return null;
    }
  }, []);

  // Stop polling when the component unmounts to prevent memory leaks
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  const runTest = async (testCaseToRun) => {
    // Stop any previous polling before starting a new one
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }
      
    setIsExecuting(true);
    setError('');
    setStatusMessage('Publishing job for execution...');

    try {
      const initialResultsCount = results.length;
      const response = await axios.post(`${orchestratorApiUrl}/api/v1/publish-test-case`, testCaseToRun);
      
      setStatusMessage('Job published! Waiting for results...');
      setTestCase(null);

      // --- NEW POLLING LOGIC ---
      let attempts = 0;
      pollingRef.current = setInterval(async () => {
        console.log(`Polling for results... Attempt ${attempts + 1}/${POLLING_ATTEMPTS}`);
        const currentResults = await fetchResults();
        attempts++;

        // Stop polling if we find a new result or we run out of attempts
        if ((currentResults && currentResults.length > initialResultsCount) || attempts >= POLLING_ATTEMPTS) {
          clearInterval(pollingRef.current);
          console.log("Polling stopped.");
          if (currentResults && currentResults.length > initialResultsCount) {
              setStatusMessage('New result received!');
              setTimeout(() => setStatusMessage(''), 3000); // Clear message after 3s
          } else {
              setStatusMessage('Polling timed out. Please refresh manually.');
          }
        }
      }, POLLING_INTERVAL);
      
    } catch (err) {
        const errorMessage = err.response?.data?.detail || "Failed to publish job.";
        setError(`Error: ${errorMessage}`);
        setStatusMessage('');
    } finally {
        setIsExecuting(false);
    }
  };

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
      setTestCase(response.data);
      setStatusMessage('');
    } catch (err) {
      const errorMessage = err.response?.data?.detail || "Failed to generate test case.";
      setError(`Error: ${errorMessage}`);
      setStatusMessage('');
    } finally {
      setIsLoading(false);
    }
  };

  return { results, isLoading, isExecuting, error, statusMessage, testCase, fetchResults, generateTest, runTest, setTestCase };
};