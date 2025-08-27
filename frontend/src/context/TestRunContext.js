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
    const [error, setError] = useState('');
    const [statusMessage, setStatusMessage] = useState('');
    const navigate = useNavigate();

    const fetchResults = useCallback(async () => {
        try {
            const response = await axios.get(`${reportingApiUrl}/results`);
            setResults(response.data);
        } catch (err) {
            console.error("Failed to fetch results", err);
            setError("Could not load test results.");
        }
    }, []);

    useEffect(() => {
        fetchResults();
    }, [fetchResults]);

    useEffect(() => {
        const socket = new WebSocket(`${websocketUrl}/ws/notifications`);
        socket.onopen = () => console.log("Notification WebSocket connected.");
        socket.onclose = () => console.log("Notification WebSocket disconnected.");

        socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            
            if (message.objective) { // A new run object
                console.log("Received new run notification:", message);
                setResults(prevResults => [message, ...prevResults.filter(r => r.id !== message.id)]);
            } else if (message.id) { // A final status update
                console.log("Received final status update:", message);
                setResults(prevResults => 
                    prevResults.map(run =>
                        run.id === message.id
                            ? { ...run, status: message.status, failure_reason: message.failure_reason }
                            : run
                    )
                );
            }
        };

        return () => socket.close();
    }, []);

    const startTestJourney = async (objective, targetUrl, isLiveView) => {
        setIsLoading(true);
        setError('');
        setStatusMessage('Starting AI Test Agent...');
        try {
            const payload = {
                objective,
                target_url: targetUrl,
                is_live_view: isLiveView,
                parameters: [{
                    dataset_name: "valid_credentials",
                    data: { "Username": "standard_user", "Password": "secret_sauce" }
                }]
            };
            // The API call returns the initial 'RUNNING' record, which is added via WebSocket
            await axios.post(`${orchestratorApiUrl}/api/v1/start-test-journey`, payload);
            
            setStatusMessage('Agent has started the journey. See history for live updates.');
            navigate('/runs');
            
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to start test journey.");
            setStatusMessage('');
        } finally {
            setIsLoading(false);
        }
    };

    const value = {
        results,
        isLoading,
        error,
        statusMessage,
        fetchResults,
        startTestJourney, // The new unified function
    };

    return (
        <TestRunContext.Provider value={value}>
            {children}
        </TestRunContext.Provider>
    );
};