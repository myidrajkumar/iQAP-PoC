import React from 'react';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

// Register the necessary components for Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const DailyTrendChart = ({ data }) => {
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: 'Daily Test Executions (Last 7 Days)',
        font: { size: 16 }
      },
    },
    scales: {
      x: {
        stacked: true,
      },
      y: {
        stacked: true,
        beginAtZero: true,
      },
    },
  };

  const chartData = {
    labels: data.map(d => new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })),
    datasets: [
      {
        label: 'Pass',
        data: data.map(d => d.pass),
        backgroundColor: '#28a745',
      },
      {
        label: 'Fail',
        data: data.map(d => d.fail),
        backgroundColor: '#dc3545',
      },
    ],
  };

  return (
    <div className="chart-container">
      <Bar options={options} data={chartData} />
    </div>
  );
};

export default DailyTrendChart;