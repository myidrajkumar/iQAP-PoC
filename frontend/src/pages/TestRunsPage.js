import React from 'react';
import { useTestApi } from '../hooks/useTestApi'; // We can reuse the same hook for now
import ResultsTable from '../components/ResultsTable';

function TestRunsPage() {
    const { results, fetchResults } = useTestApi();

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