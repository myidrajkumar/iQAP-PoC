import React from 'react';
import { useTestRun } from '../context/TestRunContext'; // <-- Use the new context hook
import ResultsTable from '../components/ResultsTable';

function TestRunsPage() {
    const { results, fetchResults } = useTestRun(); // <-- Use the new context hook

    return (
        <div>
            <h1>Test Run History</h1>
            <p>A complete log of all test executions. Click 'View' for failure details.</p>
            <div className="results-container">
                 <ResultsTable results={results} onRefresh={fetchResults} />
            </div>
        </div>
    );
}

export default TestRunsPage;