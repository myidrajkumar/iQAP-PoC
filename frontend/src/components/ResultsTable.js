import React from 'react';

const ResultsTable = ({ results, onRefresh }) => (
  <div className="form-right">
    <h3>Test Run History</h3>
    <button className="refresh-btn" onClick={onRefresh}>Refresh Results</button>
    <div className="results-table-container">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Objective</th>
            <th>Status</th>
            <th>Visual Status</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {results.length > 0 ? results.map((result) => (
            <tr key={result.id}>
              <td>{result.id}</td>
              <td>{result.objective}</td>
              <td><span className={`status-badge status-${result.status?.toLowerCase()}`}>{result.status}</span></td>
              <td><span className={`status-badge status-${result.visual_status?.toLowerCase()?.replace(/_/g, '-').replace('/', '-') || 'n-a'}`}>{result.visual_status || 'N/A'}</span></td>
              <td>{new Date(result.timestamp).toLocaleString()}</td>
            </tr>
          )) : (
            <tr><td colSpan="5">No results found. Run a test to see history.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  </div>
);

export default ResultsTable;