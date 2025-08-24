import React, { createContext, useState, useEffect, useCallback, useRef, useContext } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const reportingApiUrl = process.env.REACT_APP_REPORTING_URL || 'http://localhost:8002';
const orchestratorApiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const POLLING_INTERVAL = 3000;
const POLLING_ATTEMPTS = 20;

const TestRunContext = createContext();

export const useTestRun = () => {
    return useContext(TestRunContext);
};

export const TestRunProvider = ({ children }) => {
    const [results, setResults] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isExecuting, setIsExecuting] = useState(false);
    const [error, setError] = useState('');
    const [statusMessage, setStatusMessage] = useState('');
    const [testCase, setTestCase] = useState(null);
    const pollingRef = useRef(null);
    const navigate = useNavigate();

    const stopPolling = () => {
        if (pollingRef.current) {
            clearInterval(pollingRef.current);
            console.log("Polling stopped.");
        }
    };

    const fetchResults = useCallback(async () => {
        try {
            const response = await axios.get(`${reportingApiUrl}/results`);
            setResults(response.data);
            return response.data;
        } catch (err) {
            console.error("Failed to fetch results", err);
            setError("Could not load test results.");
            return null;
        }
    }, []);

    const startPolling = useCallback(() => {
        stopPolling(); // Ensure no multiple polls are running
        let attempts = 0;
        pollingRef.current = setInterval(async () => {
            console.log(`Polling for results... Attempt ${attempts + 1}`);
            const currentResults = await fetchResults();
            attempts++;
            const isStillRunning = currentResults?.some(r => r.status === 'RUNNING');
            if (!isStillRunning || attempts >= POLLING_ATTEMPTS) {
                stopPolling();
            }
        }, POLLING_INTERVAL);
    }, [fetchResults]);

    useEffect(() => {
        fetchResults(); // Initial fetch on load
        return stopPolling; // Cleanup on unmount
    }, [fetchResults]);

    const generateTest = async (requirement, targetUrl) => {
        setIsLoading(true);
        setError('');
        setTestCase(null);
        setStatusMessage('Generating test case via Gemini...');
        try {
            const response = await axios.post(`${orchestratorApiUrl}/api/v1/generate-test-case`, { requirement, target_url: targetUrl });
            setTestCase(response.data);
            setStatusMessage('');
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to generate test case.");
            setStatusMessage('');
        } finally {
            setIsLoading(false);
        }
    };

    const runTest = async (testCaseToRun, isLiveView = false) => {
        setIsExecuting(true);
        setError('');
        setStatusMessage('Publishing job for execution...');
        try {
            const payload = { ...testCaseToRun, is_live_view: isLiveView };
            await axios.post(`${orchestratorApiUrl}/api/v1/publish-test-case`, payload);
            
            setStatusMessage('Job published successfully!');
            setTestCase(null);
            
            navigate('/runs');
            // Give the backend a moment to create the "RUNNING" record
            setTimeout(startPolling, 500);
            
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to publish job.");
            setStatusMessage('');
        } finally {
            setIsExecuting(false);
        }
    };

    const value = {
        results,
        isLoading,
        isExecuting,
        error,
        statusMessage,
        testCase,
        fetchResults,
        generateTest,
        runTest,
        setTestCase,
    };

    return (
        <TestRunContext.Provider value={value}>
            {children}
        </TestRunContext.Provider>
    );
};