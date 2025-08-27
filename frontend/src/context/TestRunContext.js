import React, { createContext, useState, useEffect, useCallback, useContext } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const reportingApiUrl = process.env.REACT_APP_REPORTING_URL || 'http://localhost:8002';
const orchestratorApiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const websocketUrl = process.env.REACT_APP_WEBSOCKET_URL || 'ws://localhost:8003';

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
    const navigate = useNavigate();

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

    useEffect(() => {
        fetchResults();
    }, [fetchResults]);

    useEffect(() => {
        const socket = new WebSocket(`${websocketUrl}/ws/notifications`);

        socket.onopen = () => {
            console.log("Notification WebSocket connected.");
        };

        socket.onmessage = (event) => {
            const newRun = JSON.parse(event.data);
            console.log("Received new run notification:", newRun);
            setResults(prevResults => [newRun, ...prevResults]);
        };

        socket.onclose = () => {
            console.log("Notification WebSocket disconnected.");
        };

        return () => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.close();
            }
        };
    }, []);


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
            
            setStatusMessage('Job published successfully! The run will appear in the history shortly.');
            setTestCase(null);
            
            navigate('/runs');
            
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