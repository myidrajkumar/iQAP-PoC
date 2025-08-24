import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Sidebar from './components/Sidebar'; // <-- NEW
import DashboardPage from './pages/DashboardPage';
import TestResultDetailPage from './pages/TestResultDetailPage';
import AuthoringPage from './pages/AuthoringPage'; // <-- NEW
import TestRunsPage from './pages/TestRunsPage'; // <-- NEW
import './App.css';

function App() {
  return (
    <div className="app-layout">
      {/* --- NEW: Persistent Sidebar --- */}
      <Sidebar />

      {/* --- Main Content Area --- */}
      <div className="main-content">
        <Header />
        <main>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/author" element={<AuthoringPage />} />
            <Route path="/runs" element={<TestRunsPage />} />
            <Route path="/results/:runId" element={<TestResultDetailPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default App;