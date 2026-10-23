import React, { useState, useEffect } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { Train, Activity, Search, Info, Play, Radio, ShieldCheck, Zap } from 'lucide-react';
import './Navbar.css';

export default function Navbar() {
  const [backendStatus, setBackendStatus] = useState({ online: false, model: 'Connecting...', day: 'Mon' });
  const location = useLocation();

  useEffect(() => {
    let isMounted = true;
    const checkStatus = async () => {
      try {
        const res = await fetch('/api/sim/status');
        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            setBackendStatus({
              online: true,
              model: data.current_model || 'Centralized_PPO',
              day: data.current_day || 'Mon'
            });
          }
        } else {
          if (isMounted) setBackendStatus(prev => ({ ...prev, online: false }));
        }
      } catch (e) {
        if (isMounted) setBackendStatus(prev => ({ ...prev, online: false }));
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 4000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

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

        {/* Backend & Action Controls */}
        <div className="navbar-actions">
          <div className={`status-indicator-pill ${backendStatus.online ? 'pill-online' : 'pill-offline'}`}>
            <span className={backendStatus.online ? 'pulse-dot' : 'pulse-dot pulse-dot-red'} />
            <span className="status-pill-label">
              {backendStatus.online ? `${backendStatus.model}` : 'Connecting API'}
            </span>
            {backendStatus.online && (
              <span className="status-pill-day">{backendStatus.day}</span>
            )}
          </div>

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
