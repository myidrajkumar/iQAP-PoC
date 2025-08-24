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
            Dashboard
          </NavLink>
        </li>
        <li>
          <NavLink to="/author">
            Test Studio
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