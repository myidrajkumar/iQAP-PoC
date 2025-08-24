import React from 'react';
import { Link } from 'react-router-dom';

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
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {results.length > 0 ? results.map((result) => (
            <tr key={result.id} className={result.status === 'RUNNING' ? 'row-running' : ''}>
              <td>{result.id}</td>
              <td>{result.objective}</td>
              <td>
                {result.status === 'RUNNING' ? (
                    <span className="status-badge status-running">RUNNING</span>
                ) : (
                    <span className={`status-badge status-${result.status?.toLowerCase()}`}>{result.status}</span>
                )}
              </td>
              <td><span className={`status-badge status-${result.visual_status?.toLowerCase()?.replace(/_/g, '-').replace('/', '-') || 'n-a'}`}>{result.visual_status || 'N/A'}</span></td>
              <td>{new Date(result.timestamp).toLocaleString()}</td>
              <td>
                {result.status === 'FAIL' || result.visual_status === 'FAIL' ? (
                  <Link to={`/results/${result.id}`}>View</Link>
                ) : (
                  '--'
                )}
              </td>
            </tr>
          )) : (
            <tr><td colSpan="6">No results found. Run a test to see history.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  </div>
);

export default ResultsTable;