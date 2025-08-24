import React from 'react';
import { useDashboardApi } from '../hooks/useDashboardApi';
import KpiCard from '../components/KpiCard';
import DailyTrendChart from '../components/DailyTrendChart';
import './DashboardPage.css';

function DashboardPage() {
  const { kpis, dailyData, loading: dashboardLoading } = useDashboardApi();

  return (
    <div className="dashboard-layout">
      <h1>Dashboard</h1>
      
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
    </div>
  );
}

export default DashboardPage;