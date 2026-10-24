import React from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { Train, Activity, Info, Play, Zap } from 'lucide-react';
import './Navbar.css';

export default function Navbar() {
  const location = useLocation();

  return (
    <header className="navbar-header">
      <div className="navbar-container">
        {/* Brand Logo */}
        <Link to="/" className="navbar-brand">
          <div className="navbar-logo-icon">
            <Train className="logo-train-svg" size={24} />
            <Zap className="logo-spark-svg" size={14} />
          </div>
          <div className="navbar-brand-text">
            <div className="brand-title">
              <span className="brand-rail">RAIL</span>
              <span className="brand-dispatch">DISPATCH</span>
              <span className="brand-badge-ai">AI</span>
            </div>
            <span className="brand-subtitle">Autonomous Interlocking Engine</span>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="navbar-nav">
          <NavLink 
            to="/" 
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
            end
          >
            <span>Home</span>
          </NavLink>

          <NavLink 
            to="/simulation" 
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
          >
            <Activity size={16} />
            <span>Simulation</span>
            <span className="nav-live-chip">LIVE</span>
          </NavLink>

          <NavLink 
            to="/query" 
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
          >
            <Train size={16} />
            <span>Fleet & Timetables</span>
          </NavLink>

          <NavLink 
            to="/about" 
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
          >
            <Info size={16} />
            <span>Architecture & Metrics</span>
          </NavLink>
        </nav>

        {/* Action Controls */}
        <div className="navbar-actions">
          {location.pathname !== '/simulation' && (
            <Link to="/simulation" className="btn btn-primary btn-nav-sim">
              <Play size={16} fill="currentColor" />
              <span>Launch Sim</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
