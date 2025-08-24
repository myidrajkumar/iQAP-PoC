import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const reportingApiUrl = process.env.REACT_APP_REPORTING_URL || 'http://localhost:8002';

export const useDashboardApi = () => {
  const [kpis, setKpis] = useState({ total_runs: 0, pass_rate: 0 });
  const [dailyData, setDailyData] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch both sets of data in parallel
      const kpiResponse = await axios.get(`${reportingApiUrl}/stats/kpis`);
      const dailyResponse = await axios.get(`${reportingApiUrl}/stats/daily_summary`);
      
      setKpis(kpiResponse.data);
      setDailyData(dailyResponse.data);
    } catch (error) {
      console.error("Failed to fetch dashboard data", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { kpis, dailyData, loading, refreshData: fetchData };
};