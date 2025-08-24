import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import DashboardPage from './pages/DashboardPage';
import TestResultDetailPage from './pages/TestResultDetailPage';
import AuthoringPage from './pages/AuthoringPage';
import TestRunsPage from './pages/TestRunsPage';
import { TestRunProvider } from './context/TestRunContext'; // <-- NEW IMPORT
import './App.css';

function App() {
  return (
    // The Provider now wraps the entire layout, making state global
    <TestRunProvider>
      <div className="app-layout">
        <Sidebar />
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
    </TestRunProvider>
  );
}

export default App;