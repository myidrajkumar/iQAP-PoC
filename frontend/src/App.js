import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import DashboardPage from './pages/DashboardPage'; // <-- NEW
import TestResultDetailPage from './pages/TestResultDetailPage'; // <-- NEW
import './App.css';

function App() {
  return (
    <div className="container">
      <Header />
      <main>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/results/:runId" element={<TestResultDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;