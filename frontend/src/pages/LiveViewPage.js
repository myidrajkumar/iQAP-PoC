import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import './LiveViewPage.css';

const websocketUrl = process.env.REACT_APP_WEBSOCKET_URL || 'ws://localhost:8003';

const LiveViewPage = () => {
    const { runId } = useParams();
    const [steps, setSteps] = useState([]);
    const [stepStatuses, setStepStatuses] = useState({});
    const [finalStatus, setFinalStatus] = useState('RUNNING');
    const [failureReason, setFailureReason] = useState(null);
    const [connectionStatus, setConnectionStatus] = useState('Connecting...');
    const ws = useRef(null);

    useEffect(() => {
        ws.current = new WebSocket(`${websocketUrl}/ws/${runId}`);
        ws.current.onopen = () => setConnectionStatus('Connected');
        ws.current.onclose = () => setConnectionStatus('Disconnected');
        ws.current.onerror = () => setConnectionStatus('Error');

        ws.current.onmessage = (event) => {
            const message = JSON.parse(event.data);

            if (message.type === 'run_start') {
                setSteps(message.steps || []);
            }
            if (message.type === 'step_result') {
                setStepStatuses(prev => ({ ...prev, [message.step]: message.status }));
            }
            if (message.type === 'run_end') {
                setFinalStatus(message.status);
                if(message.status === 'FAIL') {
                    setFailureReason(message.reason);
                }
                ws.current.close();
            }
        };

        const socket = ws.current;
        return () => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.close();
            }
        };
    }, [runId]);

    const renderStep = (step) => {
        const status = stepStatuses[step.step] || 'PENDING';
        return (
             <div key={step.step} className={`live-step ${status.toLowerCase()}`}>
                <div className="live-step-number">{step.step}</div>
                <div className="live-step-details">
                    <span className="live-step-action">{step.action}: </span>
                    <span>{step.target_element}</span>
                </div>
                <div className="live-step-status">{status}</div>
            </div>
        );
    };

    return (
        <div className="live-view-container">
            <div className="live-view-header">
                <h1>Live Test View (Run ID: {runId})</h1>
                <p><strong>Connection:</strong> {connectionStatus}</p>
                <div className="live-overall-status">
                    <strong>Overall Status:</strong>
                    <span className={`status-badge status-${finalStatus.toLowerCase()}`}>{finalStatus}</span>
                </div>
            </div>
            
            {failureReason && (
                <div className="live-failure-reason">
                    <strong>Failure Reason:</strong> {failureReason}
                </div>
            )}

            <div className="steps-wrapper">
                {steps.length > 0 ? steps.map(renderStep) : <p>Waiting for test to start...</p>}
            </div>

            {finalStatus !== 'RUNNING' && (
                <Link to="/runs" className="back-to-runs-btn">Back to Test Runs</Link>
            )}
        </div>
    );
};

export default LiveViewPage;