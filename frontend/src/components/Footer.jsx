import React from 'react';
import { Link } from 'react-router-dom';
import { Train, Cpu, ShieldCheck, ExternalLink, Heart, Award, ArrowUpRight } from 'lucide-react';
import './Footer.css';

function GithubIcon({ size = 16, className = "" }) {
  return (
    <svg 
      width={size} 
      height={size} 
      viewBox="0 0 24 24" 
      fill="currentColor" 
      className={className}
      aria-hidden="true"
    >
      <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

const CONTRIBUTORS = [
  {
    name: 'Venkata Sriram Topalli',
    github: 'https://github.com/venkatasriramt-spec',
    handle: '@venkatasriramt-spec'
  },
  {
    name: 'Ayush M Singh',
    github: 'https://github.com/AYUSHMSINGH2004',
    handle: '@AYUSHMSINGH2004'
  },
  {
    name: 'Avanish Kushwaha',
    github: 'https://github.com/avanish06',
    handle: '@avanish06'
  }
];

export default function Footer() {
  const handleScrollToTop = () => {
    const prefersReducedMotion = typeof window !== 'undefined' && 
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: prefersReducedMotion ? 'instant' : 'smooth'
    });
  };

  return (
    <footer className="site-footer">
      <div className="footer-glow-divider" />
      
      <div className="footer-container">
        {/* Top Section: Contributors */}
        <div className="footer-contributors-section">
          <div className="contributors-header">
            <div className="contributors-badge">
              <Award size={14} />
              <span>Project Core Team</span>
            </div>
            <h3 className="contributors-title">Engineering & Research Contributors</h3>
            <p className="contributors-desc">
              Developed as an autonomous, self-healing railway traffic management system powered by Deep Reinforcement Learning.
            </p>
          </div>

          <div className="contributors-grid">
            {CONTRIBUTORS.map((contributor) => (
              <a 
                key={contributor.name}
                href={contributor.github}
                target="_blank"
                rel="noopener noreferrer"
                className="contributor-card"
              >
                <div className="contributor-avatar">
                  <span className="avatar-initials">
                    {contributor.name.split(' ').map(n => n[0]).slice(0, 2).join('')}
                  </span>
                  <div className="avatar-github-badge">
                    <GithubIcon size={12} />
                  </div>
                </div>

                <div className="contributor-info">
                  <div className="contributor-name-row">
                    <h4 className="contributor-name">{contributor.name}</h4>
                    <ArrowUpRight size={15} className="external-arrow" />
                  </div>
                  <div className="contributor-meta">
                    <span className="contributor-handle">{contributor.handle}</span>
                  </div>
                </div>
              </a>
            ))}
          </div>
        </div>

        {/* Middle Section: Links & Tech */}
        <div className="footer-details-grid">
          <div className="footer-col brand-col">
            <Link to="/" onClick={handleScrollToTop} className="footer-brand">
              <Train className="footer-brand-icon" size={22} />
              <span className="footer-brand-text">Autonomous Rail Dispatcher</span>
            </Link>
            <p className="footer-bio">
              A high-precision multi-agent simulation testbed and production-grade interlocking controller 
              designed to resolve dense-corridor bottlenecks, eliminate cascade delays, and guarantee zero-deadlock scheduling.
            </p>
            <div className="footer-tech-stack">
              <span className="tech-badge">Python 3.10</span>
              <span className="tech-badge">FastAPI</span>
              <span className="tech-badge">Eclipse SUMO</span>
              <span className="tech-badge">PyTorch PPO/MAPPO</span>
              <span className="tech-badge">React 19</span>
            </div>
          </div>

          <div className="footer-col">
            <h4 className="footer-heading">Platform Pages</h4>
            <ul className="footer-links-list">
              <li><Link to="/" onClick={handleScrollToTop}>Project Overview & Dashboard</Link></li>
              <li><Link to="/simulation" onClick={handleScrollToTop}>2D Real-Time Simulation Canvas</Link></li>
              <li><Link to="/query" onClick={handleScrollToTop}>Fleet & Timetable Directory</Link></li>
              <li><Link to="/about" onClick={handleScrollToTop}>System Architecture & 56-Run Benchmark</Link></li>
            </ul>
          </div>

          <div className="footer-col">
            <h4 className="footer-heading">System Capabilities</h4>
            <ul className="footer-links-list">
              <li><span className="feature-item">776 Track Segments & 18 Stations</span></li>
              <li><span className="feature-item">8 Dispatcher AI & Heuristic Models</span></li>
              <li><span className="feature-item">Dynamic Signal & Overtake Logic</span></li>
              <li><span className="feature-item">Human-in-the-Loop Dispatch Overrides</span></li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="footer-bottom-bar">
          <div className="footer-copyright">
            © {new Date().getFullYear()} Autonomous Rail Traffic Management System. Released for Academic & Research Excellence.
          </div>
          <div className="footer-bottom-badges">
            <span className="safety-badge">
              <ShieldCheck size={14} className="safety-icon" />
              Safety • Security • Punctuality
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
