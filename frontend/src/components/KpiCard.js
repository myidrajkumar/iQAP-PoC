import React from 'react';
import './KpiCard.css';

const KpiCard = ({ title, value, suffix }) => (
  <div className="kpi-card">
    <div className="kpi-value">
      {value}
      <span className="kpi-suffix">{suffix}</span>
    </div>
    <div className="kpi-title">{title}</div>
  </div>
);

export default KpiCard;