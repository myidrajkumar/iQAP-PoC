import React from 'react';
import { NavLink } from 'react-router-dom';
import './Sidebar.css';

const Sidebar = () => {
  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <h2>iQAP</h2>
      </div>
      <ul className="sidebar-nav">
        <li>
          <NavLink to="/" end>
            {/* We can add icons later */}
            Dashboard
          </NavLink>
        </li>
        <li>
          <NavLink to="/author">
            Author New Test
          </NavLink>
        </li>
        <li>
          <NavLink to="/runs">
            Test Runs
          </NavLink>
        </li>
      </ul>
    </nav>
  );
};

export default Sidebar;