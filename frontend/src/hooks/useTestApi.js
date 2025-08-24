import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';

const reportingApiUrl = process.env.REACT_APP_REPORTING_URL || 'http://localhost:8002';
const orchestratorApiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const POLLING_INTERVAL = 3000;
const POLLING_ATTEMPTS = 20;

export const useTestApi = () => {
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [testCase, setTestCase] = useState(null);

  const pollingRef = useRef(null);

  const fetchResults = useCallback(async () => {
    try {
      const response = await axios.get(`${reportingApiUrl}/results`);
      setResults(response.data);
      return response.data;
    } catch (err) {
      console.error("Failed to fetch results", err);
      setError("Could not load test results. Is the reporting service running?");
      return null;
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    let attempts = 0;
    pollingRef.current = setInterval(async () => {
      console.log(`Polling for results... Attempt ${attempts + 1}`);
      const currentResults = await fetchResults();
      attempts++;

      const isStillRunning = currentResults?.some(r => r.status === 'RUNNING');

      if (!isStillRunning || attempts >= POLLING_ATTEMPTS) {
        clearInterval(pollingRef.current);
        console.log("Polling stopped.");
      }
    }, POLLING_INTERVAL);
  }, [fetchResults]);

  // --- THE FIX: This effect now checks sessionStorage on mount ---
  useEffect(() => {
    fetchResults(); // Initial fetch

    // Check if we were redirected here with instructions to start polling
    if (sessionStorage.getItem('startPollingAfterRedirect') === 'true') {
      sessionStorage.removeItem('startPollingAfterRedirect');
      startPolling();
    }
    
    // Cleanup polling on unmount
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [fetchResults, startPolling]);


  const runTest = async (testCaseToRun, navigate, isLiveView = false) => {
    setIsExecuting(true);
    setError('');
    setStatusMessage('Publishing job for execution...');

    try {
      const payload = { ...testCaseToRun, is_live_view: isLiveView };
      await axios.post(`${orchestratorApiUrl}/api/v1/publish-test-case`, payload);
      
      setStatusMessage('Job published successfully!');
      setTestCase(null);
      
      // --- THE FIX: Set a flag in sessionStorage before navigating ---
      sessionStorage.setItem('startPollingAfterRedirect', 'true');
      navigate('/runs');
      
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