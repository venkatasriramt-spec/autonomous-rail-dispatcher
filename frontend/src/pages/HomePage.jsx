import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  Play, 
  Search, 
  Activity, 
  ShieldCheck, 
  Cpu, 
  Zap, 
  GitBranch, 
  Clock, 
  TrendingUp, 
  ArrowRight, 
  CheckCircle2, 
  Radio, 
  BarChart3, 
  Layers,
  Sparkles
} from 'lucide-react';
import './HomePage.css';
import Footer from '../components/Footer';

export default function HomePage() {
  const [stats, setStats] = useState({
    activeTrains: 0,
    model: 'Centralized_PPO',
    simTime: '06:00:00',
    punctuality: 99.4,
    avgDelay: 12.4,
    totalServices: 242,
    online: false
  });

  useEffect(() => {
    let mounted = true;
    const fetchSimState = async () => {
      try {
        const res = await fetch('/api/sim/status');
        if (res.ok) {
          const data = await res.json();
          if (mounted) {
            setStats(prev => ({
              ...prev,
              activeTrains: data.active_trains_count || 0,
              model: data.current_model || 'Centralized_PPO',
              simTime: data.sim_time_formatted || '06:00:00',
              online: true
            }));
          }
        }
      } catch (err) {
        // Backend offline or reconnecting
      }
    };
    fetchSimState();
    const interval = setInterval(fetchSimState, 3000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="home-page">
      {/* Background ambient lighting */}
      <div className="home-ambient-glow glow-cyan" />
      <div className="home-ambient-glow glow-blue" />
      <div className="home-ambient-glow glow-purple" />

      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-container">
          <div className="hero-badge">
            <Sparkles size={14} className="hero-badge-sparkle" />
            <span>Autonomous Rail Traffic Management & Interlocking Platform</span>
          </div>

          <h1 className="hero-title">
            Next-Gen Multi-Agent <br />
            <span className="text-gradient-cyan">Autonomous Rail Dispatcher</span>
          </h1>

          <p className="hero-description">
            An end-to-end microscopic railway orchestration platform integrating 
            <strong> Eclipse SUMO</strong> physics with <strong>Deep Reinforcement Learning (PPO / MAPPO)</strong>. 
            Eliminating cascade bottlenecks, optimizing platform assignments, and guaranteeing 
            conflict-free scheduling across 776 track segments.
          </p>

          {/* Dual Action CTAs */}
          <div className="hero-cta-group">
            <Link to="/simulation" className="btn btn-primary hero-btn-main">
              <Play size={18} fill="currentColor" />
              <span>Launch Live Simulation</span>
              <ArrowRight size={16} />
            </Link>

            <Link to="/query" className="btn btn-secondary hero-btn-sub">
              <Search size={18} />
              <span>Timetable & Train Query</span>
            </Link>

            <Link to="/about" className="btn btn-secondary hero-btn-sub">
              <BarChart3 size={18} />
              <span>Benchmark Results</span>
            </Link>
          </div>

          {/* Quick HUD Metrics Strip */}
          <div className="hero-metrics-strip glass-panel">
            <div className="metric-item">
              <div className="metric-header">
                <Layers size={16} className="metric-icon cyan" />
                <span className="metric-label">Network Topology</span>
              </div>
              <div className="metric-value">776 <span className="metric-unit">Lanes</span></div>
              <span className="metric-detail">18 Stations • 116 Platforms</span>
            </div>

            <div className="metric-divider" />

            <div className="metric-item">
              <div className="metric-header">
                <Cpu size={16} className="metric-icon purple" />
                <span className="metric-label">AI Dispatch Engine</span>
              </div>
              <div className="metric-value">{stats.model}</div>
              <span className="metric-detail">8 Paradigms Evaluated</span>
            </div>

            <div className="metric-divider" />

            <div className="metric-item">
              <div className="metric-header">
                <TrendingUp size={16} className="metric-icon emerald" />
                <span className="metric-label">RL Punctuality</span>
              </div>
              <div className="metric-value">99.4%</div>
              <span className="metric-detail">vs 73.1% SUMO Default</span>
            </div>

            <div className="metric-divider" />

            <div className="metric-item">
              <div className="metric-header">
                <Clock size={16} className="metric-icon amber" />
                <span className="metric-label">Commercial Fleet</span>
              </div>
              <div className="metric-value">242 <span className="metric-unit">Services</span></div>
              <span className="metric-detail">31 Continuous Rakes</span>
            </div>
          </div>
        </div>
      </section>

      {/* Core Architectural Pillars */}
      <section className="pillars-section">
        <div className="section-container">
          <div className="section-header">
            <span className="section-subtitle">Engineered for Microscopic Fidelity</span>
            <h2 className="section-title">Four Core Engineering Pillars</h2>
            <p className="section-lead">
              Built from the ground up to bridge academic Deep RL with real-world railway dispatching constraints.
            </p>
          </div>

          <div className="pillars-grid">
            {/* Pillar 1 */}
            <div className="pillar-card glass-panel-interactive">
              <div className="pillar-icon-box cyan-bg">
                <Activity size={24} className="pillar-icon cyan" />
              </div>
              <h3 className="pillar-title">TraCI Microscopic Simulation</h3>
              <p className="pillar-text">
                Native TraCI coupling runs Eclipse SUMO at 10 Hz, realistically simulating train deceleration, 
                cant resistance, speed limits, block signalling, and headway buffers across all corridors.
              </p>
              <ul className="pillar-bullets">
                <li><CheckCircle2 size={14} /> Full multi-track junction kinematics</li>
                <li><CheckCircle2 size={14} /> Real-time telemetry streaming via WebSockets</li>
              </ul>
            </div>

            {/* Pillar 2 */}
            <div className="pillar-card glass-panel-interactive">
              <div className="pillar-icon-box purple-bg">
                <Cpu size={24} className="pillar-icon purple" />
              </div>
              <h3 className="pillar-title">PPO & MAPPO Multi-Agent AI</h3>
              <p className="pillar-text">
                State-of-the-art Deep Reinforcement Learning agents learn topological conflict resolution, 
                overtakes, and dynamic dwell pacing, reducing mean passenger delay by over 82%.
              </p>
              <ul className="pillar-bullets">
                <li><CheckCircle2 size={14} /> 56-run 7-day 24-hr verified benchmark</li>
                <li><CheckCircle2 size={14} /> Graph representation of track occupancy</li>
              </ul>
            </div>

            {/* Pillar 3 */}
            <div className="pillar-card glass-panel-interactive">
              <div className="pillar-icon-box orange-bg">
                <Search size={24} className="pillar-icon orange" />
              </div>
              <h3 className="pillar-title">Commercial Timetable & Fleet</h3>
              <p className="pillar-text">
                Complete SQLite commercial database modeling 7 rolling stock types (including 16-coach High-Speed EMUs), 
                31 physical rakes, operating days, and platform allocation constraints.
              </p>
              <ul className="pillar-bullets">
                <li><CheckCircle2 size={14} /> Interactive passenger timetable portal</li>
                <li><CheckCircle2 size={14} /> Intermediate station halts and duty cycles</li>
              </ul>
            </div>

            {/* Pillar 4 */}
            <div className="pillar-card glass-panel-interactive">
              <div className="pillar-icon-box emerald-bg">
                <Zap size={24} className="pillar-icon emerald" />
              </div>
              <h3 className="pillar-title">Human-in-the-Loop Overrides</h3>
              <p className="pillar-text">
                Operators can inject real-time stress incidents—including track closures, signal failures, 
                and speed restrictions—or issue manual dispatch commands to reroute and hold trains.
              </p>
              <ul className="pillar-bullets">
                <li><CheckCircle2 size={14} /> Live incident injection and rollback</li>
                <li><CheckCircle2 size={14} /> Seamless human-AI co-dispatching</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Dispatcher Model Comparison Highlight */}
      <section className="models-overview-section">
        <div className="section-container">
          <div className="models-card glass-panel">
            <div className="models-header-row">
              <div>
                <span className="section-subtitle">Authoritative Benchmark</span>
                <h3 className="models-headline">8 Dispatcher Paradigms Cross-Evaluated</h3>
              </div>
              <Link to="/about#56-run-benchmark" className="btn btn-secondary">
                <span>View Full 56-Run Matrix</span>
                <ArrowRight size={14} />
              </Link>
            </div>

            <div className="models-table-wrapper">
              <table className="models-preview-table">
                <thead>
                  <tr>
                    <th>Dispatcher Paradigm</th>
                    <th>Architecture</th>
                    <th>Mean Delay (s)</th>
                    <th>Max Delay (s)</th>
                    <th>Punctuality Rate</th>
                    <th>Conflict Avoidance</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="highlight-row">
                    <td>
                      <div className="model-name-cell">
                        <span className="pulse-dot" />
                        <strong>Centralized PPO (Our Lead)</strong>
                        <span className="badge badge-category-hs">Recommended</span>
                      </div>
                    </td>
                    <td>Actor-Critic Deep RL</td>
                    <td className="text-emerald"><strong>11.8 s</strong></td>
                    <td>68.2 s</td>
                    <td className="text-emerald"><strong>99.4%</strong></td>
                    <td>Zero Deadlock</td>
                  </tr>
                  <tr>
                    <td>
                      <div className="model-name-cell">
                        <strong>MAPPO (Multi-Agent PPO)</strong>
                      </div>
                    </td>
                    <td>Cooperative Decentralized</td>
                    <td className="text-emerald">14.2 s</td>
                    <td>84.0 s</td>
                    <td className="text-emerald">99.1%</td>
                    <td>Zero Deadlock</td>
                  </tr>
                  <tr>
                    <td>
                      <div className="model-name-cell">
                        <strong>Decentralized DQN</strong>
                      </div>
                    </td>
                    <td>Deep Q-Learning</td>
                    <td>24.5 s</td>
                    <td>142.0 s</td>
                    <td>96.8%</td>
                    <td>Minimal Knock-on</td>
                  </tr>
                  <tr>
                    <td>
                      <div className="model-name-cell">
                        <strong>Dynamic Priority Heuristic</strong>
                      </div>
                    </td>
                    <td>Weighted Delay Penalty</td>
                    <td>38.6 s</td>
                    <td>210.5 s</td>
                    <td>93.2%</td>
                    <td>Rule-Bounded</td>
                  </tr>
                  <tr>
                    <td>
                      <div className="model-name-cell">
                        <strong>Rule-Based FIFO</strong>
                      </div>
                    </td>
                    <td>First-In First-Out</td>
                    <td>54.1 s</td>
                    <td>340.0 s</td>
                    <td>87.4%</td>
                    <td>Frequent Queues</td>
                  </tr>
                  <tr className="lowlight-row">
                    <td>
                      <div className="model-name-cell">
                        <strong>SUMO Default (No Dispatcher)</strong>
                      </div>
                    </td>
                    <td>Raw Junction Interlock</td>
                    <td className="text-rose">184.2 s</td>
                    <td className="text-rose">1240.0 s</td>
                    <td className="text-rose">73.1%</td>
                    <td>Gridlock Susceptible</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      {/* Banner Call to Action */}
      <section className="cta-banner-section">
        <div className="section-container">
          <div className="cta-card">
            <div className="cta-content">
              <h2 className="cta-title">Ready to Experience Live Autonomous Dispatching?</h2>
              <p className="cta-desc">
                Step into the simulation command center to visualize real-time train movements, 
                test PPO against peak diurnal traffic, and inject stress disruptions.
              </p>
              <div className="cta-buttons">
                <Link to="/simulation" className="btn btn-primary btn-cta-large">
                  <Play size={18} fill="currentColor" />
                  <span>Open Simulation Canvas</span>
                </Link>
                <Link to="/query" className="btn btn-secondary btn-cta-large">
                  <Search size={18} />
                  <span>Search Scheduled Rail Services</span>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Global Project Footer */}
      <Footer />
    </div>
  );
}
