import React from 'react';
import { useTestApi } from '../hooks/useTestApi';
import { useDashboardApi } from '../hooks/useDashboardApi';
import TestForm from '../components/TestForm';
import TestCaseEditor from '../components/TestCaseEditor';
import ResultsTable from '../components/ResultsTable';
import KpiCard from '../components/KpiCard';
import DailyTrendChart from '../components/DailyTrendChart';
import './DashboardPage.css'; // <-- New CSS for this page

function DashboardPage() {
  const {
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
  } = useTestApi();

  const { kpis, dailyData, loading: dashboardLoading } = useDashboardApi();

  return (
    <div className="dashboard-layout">
      {/* --- New Dashboard Metrics Section --- */}
      <div className="dashboard-metrics">
        <div className="kpi-grid">
          <KpiCard title="Total Runs (7 Days)" value={kpis.total_runs} />
          <KpiCard title="Pass Rate (7 Days)" value={kpis.pass_rate} suffix="%" />
        </div>
        
        {dashboardLoading ? (
            <div>Loading chart...</div>
        ) : (
            <DailyTrendChart data={dailyData} />
        )}
      </div>

      {/* --- Existing Test Generation and Results Section --- */}
      <div className="dashboard-main-content">
        <div className="form-grid">
          {testCase ? (
            <TestCaseEditor
              testCase={testCase}
              isExecuting={isExecuting}
              onRunTest={runTest}
              onGoBack={() => setTestCase(null)}
            />
          ) : (
            <TestForm
              isLoading={isLoading}
              error={error}
              statusMessage={statusMessage}
              onGenerate={generateTest}
            />
          )}
          <ResultsTable results={results} onRefresh={fetchResults} />
        </div>
      </div>
    </div>
  );
}

export default DashboardPage;