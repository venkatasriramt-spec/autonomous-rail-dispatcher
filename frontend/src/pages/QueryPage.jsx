import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { 
  Navigation, 
  MapPin, 
  Calendar, 
  Briefcase, 
  Grid, 
  ArrowLeftRight, 
  Search, 
  FileText, 
  CheckSquare, 
  Train, 
  Clock, 
  ArrowRight, 
  ShieldCheck, 
  CheckCircle2, 
  Sparkles,
  ChevronDown,
  ChevronUp,
  Activity,
  Layers,
  Info,
  Zap,
  Radio
} from 'lucide-react';
import './QueryPage.css';

const STATIONS = [
  'City_1',
  'City_2',
  'City_4',
  'City_5',
  'City_6',
  'Depot_1',
  'Depot_2',
  'Depot_3',
  'Town_9'
];

const CLASSES = [
  { id: 'ALL', name: 'All Travel Classes' },
  { id: 'EC', name: 'Executive Express (EC)' },
  { id: '1A', name: 'First Class Sleeper (1A)' },
  { id: '2A', name: 'Standard Sleeper (2A)' },
  { id: '3A', name: 'Economy Sleeper (3A)' },
  { id: 'CC', name: 'AC Chair Car (CC)' },
  { id: '2S', name: 'Regional Second Class (2S)' }
];

const QUOTAS = [
  'GENERAL',
  'PRIORITY EXPRESS',
  'COMMUTER PASS',
  'ASSISTED MOBILITY',
  'DUTY TRANSIT',
  'EXPEDITED ALLOCATION'
];

export default function QueryPage() {
  const navigate = useNavigate();

  // Active Tab: 'book' | 'pnr' | 'charts'
  const [activeTab, setActiveTab] = useState('book');

  // Booking Form State
  const [fromStation, setFromStation] = useState('City_1');
  const [toStation, setToStation] = useState('City_4');
  const [travelDate, setTravelDate] = useState('2026-10-23');
  const [selectedClass, setSelectedClass] = useState('ALL');
  const [selectedQuota, setSelectedQuota] = useState('GENERAL');

  // Concession Checkboxes
  const [disabilityConcession, setDisabilityConcession] = useState(false);
  const [flexibleDate, setFlexibleDate] = useState(false);
  const [passConcession, setPassConcession] = useState(false);

  // Search Results
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [results, setResults] = useState([]);
  const [expandedTrain, setExpandedTrain] = useState(null);
  const [trainStops, setTrainStops] = useState({});

  // PNR Tab State
  const [pnrInput, setPnrInput] = useState('');
  const [pnrResult, setPnrResult] = useState(null);

  // Swap Stations
  const handleSwap = () => {
    const temp = fromStation;
    setFromStation(toStation);
    setToStation(temp);
  };

  // Search Trains from Backend Timetable API
  const handleSearchTrains = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setHasSearched(true);
    setResults([]);

    try {
      // Determine day of week from travelDate (e.g. Mon, Tue, etc.)
      const dateObj = new Date(travelDate);
      const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
      const dayOfWeek = dayNames[dateObj.getDay()] || 'Mon';

      // Query timetable services
      const res = await fetch(`/api/timetable/services?day=${dayOfWeek}`);
      if (res.ok) {
        const services = await res.json();
        
        // Filter by From and To stations if matching, otherwise show available corridor services
        let matched = services.filter(s => 
          (s.origin_station === fromStation && s.dest_station === toStation) ||
          (s.origin_station === fromStation) ||
          (s.dest_station === toStation)
        );

        if (matched.length === 0) {
          matched = services;
        }

        setResults(matched);
      }
    } catch (err) {
      console.error('Timetable search error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Load stops when expanding a train
  const toggleExpandTrain = async (trainNumber) => {
    if (expandedTrain === trainNumber) {
      setExpandedTrain(null);
      return;
    }

    setExpandedTrain(trainNumber);

    if (!trainStops[trainNumber]) {
      try {
        const res = await fetch(`/api/timetable/services/${trainNumber}`);
        if (res.ok) {
          const detail = await res.json();
          setTrainStops(prev => ({ ...prev, [trainNumber]: detail.stops || [] }));
        }
      } catch (err) {
        console.error('Failed to fetch train stops:', err);
      }
    }
  };

  // PNR Search simulation
  const handleSearchPNR = (e) => {
    e.preventDefault();
    if (!pnrInput || pnrInput.length < 5) return;

    setPnrResult({
      pnr: pnrInput,
      trainNumber: '32025',
      trainName: 'Nord-Sud InterCity Spine 32025',
      from: 'City_1',
      to: 'City_4',
      date: travelDate,
      bookingStatus: 'CONFIRMED (ALLOCATED)',
      coach: 'Car-04',
      berth: 'Seat 28 (Window Forward)',
      chartStatus: 'DISPATCH SCHEDULE READY',
      quota: selectedQuota
    });
  };

  return (
    <div className="query-page">
      {/* Top Banner Tagline */}
      <div className="query-top-tagline-bar">
        <div className="tagline-container">
          <div className="network-brand-chip">
            <Train size={16} />
            <span>TRANS-CORRIDOR AUTONOMOUS RAIL NETWORK</span>
          </div>
          <div className="network-motto">
            <span>High Speed</span>
            <span className="motto-pipe">|</span>
            <span>Autonomous Interlocking</span>
            <span className="motto-pipe">|</span>
            <span className="motto-punctuality">Precision Dispatch</span>
          </div>
        </div>
      </div>

      {/* Main Booking Section with Sleek Digital Backdrop */}
      <div className="query-hero-banner">
        <div className="query-ambient-glow glow-1" />
        <div className="query-ambient-glow glow-2" />
        <div className="query-grid-overlay" />

        <div className="query-container">
          {/* Fictional Network Booking Card */}
          <div className="custom-booking-card">
            {/* Top Navigation Tabs */}
            <div className="card-tabs">
              <button 
                type="button"
                className={`tab-btn ${activeTab === 'book' ? 'active' : ''}`}
                onClick={() => setActiveTab('book')}
              >
                <Train size={16} className="tab-icon" />
                <span>BOOK TICKET</span>
              </button>

              <button 
                type="button"
                className={`tab-btn ${activeTab === 'pnr' ? 'active' : ''}`}
                onClick={() => setActiveTab('pnr')}
              >
                <CheckSquare size={16} className="tab-icon" />
                <span>PNR STATUS</span>
              </button>

              <button 
                type="button"
                className={`tab-btn ${activeTab === 'charts' ? 'active' : ''}`}
                onClick={() => setActiveTab('charts')}
              >
                <FileText size={16} className="tab-icon" />
                <span>CHARTS / VACANCY</span>
              </button>
            </div>

            {/* Tab 1: BOOK TICKET Form */}
            {activeTab === 'book' && (
              <div className="tab-body">
                <div className="card-header-badge">
                  <Radio size={14} className="pulse-icon" />
                  <span>Interactive Timetable Engine</span>
                </div>
                <h2 className="card-title">BOOK TICKET</h2>

                <form onSubmit={handleSearchTrains} className="booking-form">
                  {/* From & To Station Row */}
                  <div className="station-row">
                    {/* From Station */}
                    <div className="input-group station-group">
                      <label className="field-label">From</label>
                      <div className="input-box">
                        <Navigation size={18} className="field-icon arrow-icon" />
                        <select 
                          value={fromStation}
                          onChange={(e) => setFromStation(e.target.value)}
                          className="field-select"
                        >
                          {STATIONS.map(st => (
                            <option key={st} value={st}>{st}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Swap Button */}
                    <button 
                      type="button" 
                      onClick={handleSwap} 
                      className="station-swap-btn"
                      title="Swap Origin and Destination"
                    >
                      <ArrowLeftRight size={18} />
                    </button>

                    {/* To Station */}
                    <div className="input-group station-group">
                      <label className="field-label">To</label>
                      <div className="input-box">
                        <MapPin size={18} className="field-icon pin-icon" />
                        <select 
                          value={toStation}
                          onChange={(e) => setToStation(e.target.value)}
                          className="field-select"
                        >
                          {STATIONS.map(st => (
                            <option key={st} value={st}>{st}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Date & Class Row */}
                  <div className="row-two-col">
                    {/* Date Picker */}
                    <div className="input-group">
                      <label className="field-label">DD/MM/YYYY *</label>
                      <div className="input-box">
                        <Calendar size={18} className="field-icon cal-icon" />
                        <input 
                          type="date" 
                          value={travelDate}
                          onChange={(e) => setTravelDate(e.target.value)}
                          className="date-input"
                        />
                      </div>
                    </div>

                    {/* Classes Dropdown */}
                    <div className="input-group">
                      <label className="field-label">Class</label>
                      <div className="input-box">
                        <Briefcase size={18} className="field-icon suit-icon" />
                        <select 
                          value={selectedClass}
                          onChange={(e) => setSelectedClass(e.target.value)}
                          className="field-select"
                        >
                          {CLASSES.map(c => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Quota Row */}
                  <div className="input-group quota-group">
                    <label className="field-label">Allocation Quota</label>
                    <div className="input-box">
                      <Grid size={18} className="field-icon grid-icon" />
                      <select 
                        value={selectedQuota}
                        onChange={(e) => setSelectedQuota(e.target.value)}
                        className="field-select"
                      >
                        {QUOTAS.map(q => (
                          <option key={q} value={q}>{q}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Concession Checkboxes */}
                  <div className="checkbox-grid">
                    <label className="checkbox-label">
                      <input 
                        type="checkbox" 
                        checked={disabilityConcession}
                        onChange={(e) => setDisabilityConcession(e.target.checked)}
                      />
                      <span>Person With Disability Concession</span>
                    </label>

                    <label className="checkbox-label">
                      <input 
                        type="checkbox" 
                        checked={flexibleDate}
                        onChange={(e) => setFlexibleDate(e.target.checked)}
                      />
                      <span>Flexible With Date</span>
                    </label>

                    <label className="checkbox-label">
                      <input 
                        type="checkbox" 
                        checked={passConcession}
                        onChange={(e) => setPassConcession(e.target.checked)}
                      />
                      <span>Railway Pass Concession</span>
                    </label>
                  </div>

                  {/* Action CTA Button */}
                  <div className="submit-wrapper">
                    <button type="submit" className="btn btn-search-action">
                      <Search size={18} />
                      <span>Search Trains</span>
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* Tab 2: PNR STATUS */}
            {activeTab === 'pnr' && (
              <div className="tab-body">
                <div className="tab-back-header">
                  <button onClick={() => setActiveTab('book')} className="btn-tab-back">
                    ← Back to Book Ticket
                  </button>
                  <h2 className="card-title">PNR STATUS ENQUIRY</h2>
                </div>

                <form onSubmit={handleSearchPNR} className="pnr-form">
                  <p className="pnr-instruction">Enter your 10-digit Reservation PNR number to check real-time consist allocation:</p>
                  <div className="input-box pnr-input-box">
                    <input 
                      type="text" 
                      placeholder="e.g. 8492018471"
                      maxLength={10}
                      value={pnrInput}
                      onChange={(e) => setPnrInput(e.target.value)}
                      className="pnr-input-field"
                    />
                    <button type="submit" className="btn btn-pnr-submit">
                      Check Status
                    </button>
                  </div>
                </form>

                {pnrResult && (
                  <div className="pnr-result-box">
                    <div className="pnr-badge-row">
                      <span className="pnr-badge-status">{pnrResult.bookingStatus}</span>
                      <span className="pnr-badge-chart">{pnrResult.chartStatus}</span>
                    </div>

                    <div className="pnr-info-grid">
                      <div><strong>Train Service:</strong> #{pnrResult.trainNumber} {pnrResult.trainName}</div>
                      <div><strong>Corridor Route:</strong> {pnrResult.from} → {pnrResult.to}</div>
                      <div><strong>Assigned Coach / Seat:</strong> {pnrResult.coach} • {pnrResult.berth}</div>
                      <div><strong>Scheduled Date:</strong> {pnrResult.date}</div>
                    </div>

                    <Link to="/simulation" className="btn btn-primary btn-sm btn-pnr-track">
                      <Activity size={14} />
                      <span>Track Train on Live Simulation Map</span>
                    </Link>
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: CHARTS / VACANCY */}
            {activeTab === 'charts' && (
              <div className="tab-body">
                <div className="tab-back-header">
                  <button onClick={() => setActiveTab('book')} className="btn-tab-back">
                    ← Back to Book Ticket
                  </button>
                  <h2 className="card-title">FLEET CHARTS & CAPACITY</h2>
                </div>

                <p className="pnr-instruction">Real-time Physical Rake Composition & Seat Availability across Network Corridors:</p>
                
                <div className="charts-rake-preview">
                  <div className="rake-item">
                    <h4>High-Speed EMU 300 Consist (Rake_HSE_01)</h4>
                    <span className="badge badge-category-hs">High-Speed EMU (300 km/h)</span>
                    <p className="rake-desc">16-Car aerodynamic distributed traction consist. Total capacity: 1,128 seats with dynamic regenerative braking.</p>
                    <div className="vacancy-pill-row">
                      <span className="vac-pill">Executive (EC): 24 Available</span>
                      <span className="vac-pill">Standard AC (CC): 142 Available</span>
                      <span className="vac-pill">First Class (1A): 8 Available</span>
                    </div>
                  </div>

                  <div className="rake-item">
                    <h4>Regional Commuter EMU 120 (Rake_EMU_04)</h4>
                    <span className="badge badge-category-reg">Regional Commuter EMU (120 km/h)</span>
                    <p className="rake-desc">8-Car high-acceleration suburban transit rake operating dense local multi-stop services.</p>
                    <div className="vacancy-pill-row">
                      <span className="vac-pill">Standard (2S): 280 Available</span>
                      <span className="vac-pill">AC Chair Car (CC): 64 Available</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Timetable Search Results Section */}
      {hasSearched && (
        <section className="query-results-section">
          <div className="section-container">
            <div className="results-header-row">
              <div>
                <h3 className="results-headline">
                  Available Scheduled Services ({results.length})
                </h3>
                <span className="results-subheadline">
                  {fromStation} → {toStation} • Date: {travelDate} • Allocation Quota: {selectedQuota}
                </span>
              </div>

              <Link to="/simulation" className="btn btn-secondary">
                <Activity size={16} />
                <span>Open Live 2D Simulation</span>
              </Link>
            </div>

            {loading ? (
              <div className="results-loading">
                <Train size={36} className="loader-train" />
                <span>Fetching scheduled trains from commercial timetable database...</span>
              </div>
            ) : results.length === 0 ? (
              <div className="no-results-card glass-panel">
                <h4>No direct scheduled services found for this pair on this date.</h4>
                <p>Try switching to another corridor or click "Search Trains" with default stations.</p>
              </div>
            ) : (
              <div className="trains-results-grid">
                {results.map((service) => {
                  const isExpanded = expandedTrain === service.train_number;
                  const isHighSpeed = service.service_class === 'HighSpeed';

                  return (
                    <div key={service.train_number} className="train-result-card glass-panel">
                      {/* Train Header */}
                      <div className="result-card-top">
                        <div className="train-id-badge">
                          <Train size={18} className={isHighSpeed ? 'icon-cyan' : 'icon-emerald'} />
                          <div>
                            <h4 className="result-train-name">{service.train_name}</h4>
                            <span className="result-train-num">#{service.train_number}</span>
                          </div>
                        </div>

                        <div className="result-badges">
                          <span className={`badge badge-category-${isHighSpeed ? 'hs' : service.service_class === 'Regional' ? 'reg' : 'frt'}`}>
                            {service.service_class}
                          </span>
                          <span className="badge badge-model">
                            {service.rolling_stock_type || 'EMU'}
                          </span>
                        </div>
                      </div>

                      {/* Schedule & Route Timeline */}
                      <div className="result-schedule-row">
                        <div className="schedule-node origin">
                          <span className="node-time">{service.departure_time}</span>
                          <span className="node-station">{service.origin_station}</span>
                        </div>

                        <div className="schedule-middle">
                          <span className="schedule-dist">{service.total_distance_km ? `${service.total_distance_km} km` : 'Direct'}</span>
                          <div className="schedule-track-line">
                            <span className="track-point start" />
                            <span className="track-bar" />
                            <span className="track-point end" />
                          </div>
                          <span className="schedule-corridor">{service.corridor}</span>
                        </div>

                        <div className="schedule-node dest">
                          <span className="node-time">{service.arrival_time}</span>
                          <span className="node-station">{service.dest_station}</span>
                        </div>
                      </div>

                      {/* Card Footer Actions */}
                      <div className="result-card-bottom">
                        <div className="result-rake-info">
                          <Layers size={14} className="rake-icon" />
                          <span>Rake Consist: <strong>{service.assigned_rake || 'Standard Consist'}</strong></span>
                        </div>

                        <div className="result-action-buttons">
                          <button 
                            onClick={() => toggleExpandTrain(service.train_number)} 
                            className="btn btn-secondary btn-sm"
                          >
                            <span>{isExpanded ? 'Hide Route' : 'View Halts & Platform'}</span>
                            {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                          </button>

                          <button 
                            onClick={() => navigate('/simulation')} 
                            className="btn btn-primary btn-sm btn-track-sim"
                          >
                            <Activity size={14} />
                            <span>Track on Simulation</span>
                          </button>
                        </div>
                      </div>

                      {/* Intermediate Stops Accordion */}
                      {isExpanded && (
                        <div className="stops-accordion">
                          <h5 className="stops-title">Commercial Route & Station Halts</h5>
                          {trainStops[service.train_number] && trainStops[service.train_number].length > 0 ? (
                            <table className="stops-table">
                              <thead>
                                <tr>
                                  <th>#</th>
                                  <th>Station Name</th>
                                  <th>Arrival</th>
                                  <th>Departure</th>
                                  <th>Track / Platform</th>
                                </tr>
                              </thead>
                              <tbody>
                                {trainStops[service.train_number].map((stop, sIdx) => (
                                  <tr key={sIdx}>
                                    <td>{stop.stop_sequence || sIdx + 1}</td>
                                    <td><strong>{stop.station_name}</strong></td>
                                    <td>{stop.scheduled_arrival || '--'}</td>
                                    <td>{stop.scheduled_departure || '--'}</td>
                                    <td><span className="platform-tag">{stop.platform_assigned || 'Platform 1'}</span></td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          ) : (
                            <div className="stops-empty">Direct service connecting {service.origin_station} and {service.dest_station}.</div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
