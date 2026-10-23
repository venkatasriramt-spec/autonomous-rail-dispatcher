import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { 
  Train, 
  Search, 
  Filter, 
  Clock, 
  MapPin, 
  Layers, 
  Cpu, 
  ChevronDown, 
  ChevronUp, 
  ArrowRight, 
  ExternalLink, 
  ShieldCheck, 
  CheckCircle2, 
  Activity, 
  Sparkles, 
  RotateCcw, 
  Gauge, 
  Zap, 
  Calendar,
  ArrowUpDown,
  Building2,
  Navigation
} from 'lucide-react';
import './QueryPage.css';

const CORRIDORS = [
  { id: 'ALL', name: 'All Corridors' },
  { id: 'Corridor_1', name: 'Corridor 1 (High-Speed Trunk)' },
  { id: 'Corridor_2', name: 'Corridor 2 (Valley Feeder)' },
  { id: 'Corridor_3', name: 'Corridor 3 (Alpine Mountain)' },
  { id: 'Corridor_4', name: 'Corridor 4 (Orbital Freight/Regional)' }
];

const SERVICE_CLASSES = [
  { id: 'ALL', name: 'All Service Classes' },
  { id: 'HighSpeed', name: 'High-Speed Express' },
  { id: 'Regional', name: 'Regional Commuter' },
  { id: 'Freight', name: 'Bulk & Intermodal Freight' }
];

const DAYS_OF_WEEK = [
  { id: 'ALL', name: 'All Operating Days' },
  { id: 'Mon', name: 'Monday' },
  { id: 'Tue', name: 'Tuesday' },
  { id: 'Wed', name: 'Wednesday' },
  { id: 'Thu', name: 'Thursday' },
  { id: 'Fri', name: 'Friday' },
  { id: 'Sat', name: 'Saturday' },
  { id: 'Sun', name: 'Sunday' }
];

export default function QueryPage() {
  // Navigation tabs: 'services' | 'station_board' | 'rakes' | 'rolling_stock'
  const [activeTab, setActiveTab] = useState('services');

  // Master Data from API
  const [services, setServices] = useState([]);
  const [rakes, setRakes] = useState([]);
  const [rollingStock, setRollingStock] = useState([]);
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Services Directory Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCorridor, setSelectedCorridor] = useState('ALL');
  const [selectedClass, setSelectedClass] = useState('ALL');
  const [selectedDay, setSelectedDay] = useState('ALL');
  const [selectedOrigin, setSelectedOrigin] = useState('ALL');
  const [selectedDest, setSelectedDest] = useState('ALL');
  const [sortBy, setSortBy] = useState('departure'); // 'departure' | 'train_number' | 'distance' | 'duration'

  // Expanded Service details for stops lookup
  const [expandedTrain, setExpandedTrain] = useState(null);
  const [trainDetailsCache, setTrainDetailsCache] = useState({});
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Station Board State
  const [selectedStation, setSelectedStation] = useState('City_1');
  const [stationMoveFilter, setStationMoveFilter] = useState('ALL'); // 'ALL' | 'DEPARTURES' | 'ARRIVALS'

  // Rakes Filter State
  const [rakeTypeFilter, setRakeTypeFilter] = useState('ALL');

  // 1. Initial Data Fetching
  useEffect(() => {
    let isMounted = true;
    const fetchAllData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [servicesRes, rakesRes, rsRes, stationsRes] = await Promise.all([
          fetch('/api/timetable/services'),
          fetch('/api/timetable/rakes'),
          fetch('/api/timetable/rolling-stock'),
          fetch('/api/network/stations')
        ]);

        if (!servicesRes.ok || !rakesRes.ok || !rsRes.ok) {
          throw new Error('Failed to load railway timetable data from backend API.');
        }

        const [servicesData, rakesData, rsData, stationsData] = await Promise.all([
          servicesRes.json(),
          rakesRes.json(),
          rsRes.json(),
          stationsRes.ok ? stationsRes.json() : Promise.resolve([])
        ]);

        if (isMounted) {
          setServices(servicesData);
          setRakes(rakesData);
          setRollingStock(rsData);
          if (stationsData && stationsData.length > 0) {
            const stNames = Array.from(new Set(stationsData.map(s => s.station_name || s.name || s.id).filter(Boolean)));
            setStations(stNames);
          } else {
            // Fallback list of stations extracted from services
            const uniqueStations = Array.from(new Set([
              ...servicesData.map(s => s.origin_station),
              ...servicesData.map(s => s.dest_station)
            ])).filter(Boolean).sort();
            setStations(uniqueStations);
          }
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || 'Error connecting to timetable database.');
          setLoading(false);
        }
      }
    };

    fetchAllData();
    return () => { isMounted = false; };
  }, []);

  // 2. Fetch specific train stops detail on expand
  const toggleTrainExpand = async (trainNumber) => {
    if (expandedTrain === trainNumber) {
      setExpandedTrain(null);
      return;
    }
    setExpandedTrain(trainNumber);

    if (!trainDetailsCache[trainNumber]) {
      setLoadingDetail(true);
      try {
        const res = await fetch(`/api/timetable/services/${trainNumber}`);
        if (res.ok) {
          const detail = await res.json();
          setTrainDetailsCache(prev => ({ ...prev, [trainNumber]: detail }));
        }
      } catch (e) {
        console.error('Failed to fetch train detail:', e);
      } finally {
        setLoadingDetail(false);
      }
    }
  };

  // 3. Filtered & Sorted Services
  const filteredServices = useMemo(() => {
    return services.filter(service => {
      // Search query (train_number, train_name, assigned_rake, origin, dest)
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesQuery = 
          service.train_number.toLowerCase().includes(q) ||
          service.train_name.toLowerCase().includes(q) ||
          (service.assigned_rake && service.assigned_rake.toLowerCase().includes(q)) ||
          service.origin_station.toLowerCase().includes(q) ||
          service.dest_station.toLowerCase().includes(q);
        if (!matchesQuery) return false;
      }

      // Corridor filter
      if (selectedCorridor !== 'ALL' && service.corridor !== selectedCorridor) {
        return false;
      }

      // Service Class filter
      if (selectedClass !== 'ALL' && service.service_class !== selectedClass) {
        return false;
      }

      // Origin filter
      if (selectedOrigin !== 'ALL' && service.origin_station !== selectedOrigin) {
        return false;
      }

      // Destination filter
      if (selectedDest !== 'ALL' && service.dest_station !== selectedDest) {
        return false;
      }

      return true;
    }).sort((a, b) => {
      if (sortBy === 'departure') return a.departure_sec - b.departure_sec;
      if (sortBy === 'train_number') return a.train_number.localeCompare(b.train_number);
      if (sortBy === 'distance') return (b.total_distance_km || 0) - (a.total_distance_km || 0);
      if (sortBy === 'duration') {
        const durA = (a.arrival_sec || 0) - (a.departure_sec || 0);
        const durB = (b.arrival_sec || 0) - (b.departure_sec || 0);
        return durA - durB;
      }
      return 0;
    });
  }, [services, searchQuery, selectedCorridor, selectedClass, selectedOrigin, selectedDest, sortBy]);

  // 4. Station Movements (Departures & Arrivals)
  const stationMovements = useMemo(() => {
    if (!selectedStation) return [];
    const list = [];

    services.forEach(s => {
      const isOrigin = s.origin_station === selectedStation;
      const isDest = s.dest_station === selectedStation;

      if (isOrigin) {
        list.push({
          type: 'DEPARTURE',
          time: s.departure_time,
          timeSec: s.departure_sec,
          trainNumber: s.train_number,
          trainName: s.train_name,
          bound: s.dest_station,
          track: s.origin_track,
          serviceClass: s.service_class,
          assignedRake: s.assigned_rake,
          rollingStock: s.rolling_stock_type
        });
      }

      if (isDest) {
        list.push({
          type: 'ARRIVAL',
          time: s.arrival_time,
          timeSec: s.arrival_sec,
          trainNumber: s.train_number,
          trainName: s.train_name,
          bound: `From ${s.origin_station}`,
          track: s.dest_track,
          serviceClass: s.service_class,
          assignedRake: s.assigned_rake,
          rollingStock: s.rolling_stock_type
        });
      }
    });

    return list.filter(m => {
      if (stationMoveFilter === 'DEPARTURES') return m.type === 'DEPARTURE';
      if (stationMoveFilter === 'ARRIVALS') return m.type === 'ARRIVAL';
      return true;
    }).sort((a, b) => a.timeSec - b.timeSec);
  }, [services, selectedStation, stationMoveFilter]);

  // 5. Filtered Physical Rakes
  const filteredRakes = useMemo(() => {
    if (rakeTypeFilter === 'ALL') return rakes;
    return rakes.filter(r => r.rolling_stock_type === rakeTypeFilter);
  }, [rakes, rakeTypeFilter]);

  // Format Helper: Seconds to mm:ss or hh:mm:ss
  const formatDuration = (sec) => {
    if (!sec && sec !== 0) return '--';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}m ${s > 0 ? `${s}s` : ''}`.trim();
  };

  // Helper for Class Color Tag
  const getClassBadgeClass = (sClass) => {
    switch (sClass?.toLowerCase()) {
      case 'highspeed': return 'badge-highspeed';
      case 'regional': return 'badge-regional';
      case 'freight': return 'badge-freight';
      default: return 'badge-default';
    }
  };

  return (
    <div className="query-explorer-page">
      {/* Background ambient lighting */}
      <div className="query-ambient-glow glow-cyan" />
      <div className="query-ambient-glow glow-blue" />

      <div className="query-content-container">
        {/* Top Header */}
        <header className="query-header">
          <div className="query-header-badge">
            <Sparkles size={14} />
            <span>Synthetic Railway Fleet Intelligence & Master Timetable</span>
          </div>
          <h1 className="query-title">
            Railway Fleet & <span className="text-gradient-cyan">Timetable Explorer</span>
          </h1>
          <p className="query-subtitle">
            Comprehensive query engine and diagnostic viewer for scheduled services, physical rake duty cycles, 
            station timetable boards, and rolling stock specifications across the 776-lane synthetic rail network.
          </p>

          {/* Quick Metrics Bar */}
          <div className="query-stats-ribbon">
            <div className="ribbon-card">
              <Train size={18} className="ribbon-icon text-cyan" />
              <div className="ribbon-info">
                <span className="ribbon-value">{services.length || 242}</span>
                <span className="ribbon-label">Scheduled Services</span>
              </div>
            </div>

            <div className="ribbon-card">
              <Layers size={18} className="ribbon-icon text-emerald" />
              <div className="ribbon-info">
                <span className="ribbon-value">{rakes.length || 31}</span>
                <span className="ribbon-label">Continuous Rakes</span>
              </div>
            </div>

            <div className="ribbon-card">
              <Cpu size={18} className="ribbon-icon text-amber" />
              <div className="ribbon-info">
                <span className="ribbon-value">{rollingStock.length || 7}</span>
                <span className="ribbon-label">Consist Classes</span>
              </div>
            </div>

            <div className="ribbon-card">
              <Building2 size={18} className="ribbon-icon text-purple" />
              <div className="ribbon-info">
                <span className="ribbon-value">{stations.length || 18}</span>
                <span className="ribbon-label">Stations & Hubs</span>
              </div>
            </div>

            <div className="ribbon-card">
              <Gauge size={18} className="ribbon-icon text-blue" />
              <div className="ribbon-info">
                <span className="ribbon-value">300 km/h</span>
                <span className="ribbon-label">Max Network Speed</span>
              </div>
            </div>
          </div>
        </header>

        {/* Operational View Tabs */}
        <div className="query-tabs-container">
          <div className="query-tabs-nav">
            <button
              type="button"
              className={`query-tab-btn ${activeTab === 'services' ? 'active' : ''}`}
              onClick={() => setActiveTab('services')}
            >
              <Train size={17} />
              <span>Scheduled Train Services</span>
              <span className="tab-count-chip">{services.length}</span>
            </button>

            <button
              type="button"
              className={`query-tab-btn ${activeTab === 'station_board' ? 'active' : ''}`}
              onClick={() => setActiveTab('station_board')}
            >
              <Clock size={17} />
              <span>Station Timetable Board</span>
            </button>

            <button
              type="button"
              className={`query-tab-btn ${activeTab === 'rakes' ? 'active' : ''}`}
              onClick={() => setActiveTab('rakes')}
            >
              <Layers size={17} />
              <span>Physical Rakes & Roster</span>
              <span className="tab-count-chip">{rakes.length}</span>
            </button>

            <button
              type="button"
              className={`query-tab-btn ${activeTab === 'rolling_stock' ? 'active' : ''}`}
              onClick={() => setActiveTab('rolling_stock')}
            >
              <Cpu size={17} />
              <span>Consist Specifications</span>
              <span className="tab-count-chip">{rollingStock.length}</span>
            </button>
          </div>
        </div>

        {/* Loading & Error States */}
        {loading && (
          <div className="query-loading-box">
            <div className="loading-spinner-ring" />
            <p>Querying SQLite Master Timetable Database...</p>
          </div>
        )}

        {error && (
          <div className="query-error-box">
            <p>Unable to connect to timetable database: {error}</p>
          </div>
        )}

        {!loading && !error && (
          <div className="query-views-wrapper">
            {/* ======================================================== */}
            {/* VIEW 1: SCHEDULED TRAIN SERVICES DIRECTORY */}
            {/* ======================================================== */}
            {activeTab === 'services' && (
              <div className="services-directory-view">
                {/* Search & Filter Control Bar */}
                <div className="directory-filters-panel">
                  <div className="filter-row-primary">
                    {/* Free-text Search */}
                    <div className="search-input-group">
                      <Search size={16} className="search-icon" />
                      <input 
                        type="text"
                        placeholder="Search by train # (e.g. 12101, 68402), name, rake, or station..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="directory-search-input"
                      />
                      {searchQuery && (
                        <button 
                          type="button" 
                          onClick={() => setSearchQuery('')}
                          className="clear-search-btn"
                        >
                          ✕
                        </button>
                      )}
                    </div>

                    {/* Corridor Dropdown */}
                    <div className="filter-select-group">
                      <select 
                        value={selectedCorridor} 
                        onChange={(e) => setSelectedCorridor(e.target.value)}
                        className="directory-select"
                      >
                        {CORRIDORS.map(c => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                      </select>
                    </div>

                    {/* Service Class Dropdown */}
                    <div className="filter-select-group">
                      <select 
                        value={selectedClass} 
                        onChange={(e) => setSelectedClass(e.target.value)}
                        className="directory-select"
                      >
                        {SERVICE_CLASSES.map(sc => (
                          <option key={sc.id} value={sc.id}>{sc.name}</option>
                        ))}
                      </select>
                    </div>

                    {/* Sort Selector */}
                    <div className="filter-select-group sort-group">
                      <ArrowUpDown size={15} className="sort-icon" />
                      <select 
                        value={sortBy} 
                        onChange={(e) => setSortBy(e.target.value)}
                        className="directory-select"
                      >
                        <option value="departure">Sort: Departure Time</option>
                        <option value="train_number">Sort: Train Number</option>
                        <option value="distance">Sort: Total Distance</option>
                        <option value="duration">Sort: Travel Duration</option>
                      </select>
                    </div>
                  </div>

                  {/* Secondary Stations & Reset Row */}
                  <div className="filter-row-secondary">
                    <div className="station-filter-pair">
                      <div className="station-select-box">
                        <label>Origin:</label>
                        <select 
                          value={selectedOrigin} 
                          onChange={(e) => setSelectedOrigin(e.target.value)}
                          className="directory-select-sm"
                        >
                          <option value="ALL">Any Origin Station</option>
                          {stations.map(st => (
                            <option key={st} value={st}>{st}</option>
                          ))}
                        </select>
                      </div>

                      <div className="station-select-box">
                        <label>Destination:</label>
                        <select 
                          value={selectedDest} 
                          onChange={(e) => setSelectedDest(e.target.value)}
                          className="directory-select-sm"
                        >
                          <option value="ALL">Any Destination</option>
                          {stations.map(st => (
                            <option key={st} value={st}>{st}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="filter-actions-right">
                      <span className="results-counter">
                        Showing <strong>{filteredServices.length}</strong> of {services.length} services
                      </span>
                      {(searchQuery || selectedCorridor !== 'ALL' || selectedClass !== 'ALL' || selectedOrigin !== 'ALL' || selectedDest !== 'ALL') && (
                        <button 
                          type="button"
                          className="btn-reset-filters"
                          onClick={() => {
                            setSearchQuery('');
                            setSelectedCorridor('ALL');
                            setSelectedClass('ALL');
                            setSelectedOrigin('ALL');
                            setSelectedDest('ALL');
                          }}
                        >
                          <RotateCcw size={14} />
                          <span>Reset Filters</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Services Directory List */}
                {filteredServices.length === 0 ? (
                  <div className="empty-results-box">
                    <Train size={36} className="empty-icon" />
                    <h3>No Train Services Found</h3>
                    <p>No services match your active search filters. Try clearing filters or searching another keyword.</p>
                  </div>
                ) : (
                  <div className="services-grid-list">
                    {filteredServices.map(service => {
                      const isExpanded = expandedTrain === service.train_number;
                      const durationSec = (service.arrival_sec || 0) - (service.departure_sec || 0);
                      const detail = trainDetailsCache[service.train_number];

                      return (
                        <div 
                          key={service.train_number}
                          className={`service-card ${isExpanded ? 'card-expanded' : ''}`}
                        >
                          {/* Card Summary Header */}
                          <div 
                            className="service-card-main"
                            onClick={() => toggleTrainExpand(service.train_number)}
                          >
                            <div className="card-cell cell-id">
                              <span className="train-number-badge">
                                #{service.train_number}
                              </span>
                              <span className={`service-class-badge ${getClassBadgeClass(service.service_class)}`}>
                                {service.service_class}
                              </span>
                            </div>

                            <div className="card-cell cell-name">
                              <h3 className="service-title">{service.train_name}</h3>
                              <div className="service-meta-tags">
                                <span className="meta-tag">{service.corridor.replace('_', ' ')}</span>
                                <span className="meta-tag meta-rake">Rake: {service.assigned_rake}</span>
                                <span className="meta-tag meta-vtype">{service.rolling_stock_type}</span>
                              </div>
                            </div>

                            <div className="card-cell cell-route">
                              <div className="route-endpoints">
                                <div className="endpoint-col">
                                  <span className="endpoint-time">{service.departure_time}</span>
                                  <span className="endpoint-station">{service.origin_station}</span>
                                  <span className="endpoint-track">Track {service.origin_track}</span>
                                </div>

                                <div className="route-arrow-connector">
                                  <div className="arrow-duration">{formatDuration(durationSec)}</div>
                                  <div className="arrow-line" />
                                  <div className="arrow-dist">{service.total_distance_km ? `${service.total_distance_km} km` : ''}</div>
                                </div>

                                <div className="endpoint-col text-right">
                                  <span className="endpoint-time">{service.arrival_time}</span>
                                  <span className="endpoint-station">{service.dest_station}</span>
                                  <span className="endpoint-track">Track {service.dest_track}</span>
                                </div>
                              </div>
                            </div>

                            <div className="card-cell cell-action">
                              <button 
                                type="button" 
                                className="btn-toggle-expand"
                                aria-label="Toggle details"
                              >
                                {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                              </button>
                            </div>
                          </div>

                          {/* Expandable Stops & Full Itinerary Details */}
                          {isExpanded && (
                            <div className="service-expanded-drawer">
                              <div className="drawer-header-row">
                                <div className="drawer-title-group">
                                  <MapPin size={16} className="drawer-icon" />
                                  <h4>Microscopic Itinerary & Station Stop Halts</h4>
                                </div>

                                <div className="drawer-actions">
                                  <Link 
                                    to="/simulation" 
                                    className="btn btn-sm btn-outline-cyan"
                                  >
                                    <Activity size={14} />
                                    <span>Track Live in Simulator</span>
                                  </Link>
                                </div>
                              </div>

                              {loadingDetail && !detail ? (
                                <div className="drawer-loading">
                                  <div className="loading-spinner-ring sm" />
                                  <span>Loading intermediate station stops...</span>
                                </div>
                              ) : detail?.stops && detail.stops.length > 0 ? (
                                <div className="stops-table-container">
                                  <table className="stops-table">
                                    <thead>
                                      <tr>
                                        <th>#</th>
                                        <th>Station Node</th>
                                        <th>Platform Track</th>
                                        <th>Scheduled Arrival</th>
                                        <th>Scheduled Departure</th>
                                        <th>Calibrated Dwell</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {detail.stops.map((stop, sIdx) => (
                                        <tr key={stop.stop_sequence || sIdx}>
                                          <td className="stop-seq-col">{stop.stop_sequence}</td>
                                          <td className="stop-station-col">
                                            <strong>{stop.station}</strong>
                                          </td>
                                          <td className="stop-track-col">
                                            <code>{stop.train_stop_id}</code>
                                          </td>
                                          <td className="stop-time-col">{stop.arrival_time || '--'}</td>
                                          <td className="stop-time-col">{stop.departure_time || '--'}</td>
                                          <td className="stop-dwell-col">
                                            {stop.dwell_sec ? `${stop.dwell_sec}s` : 'Transit / Terminus'}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>

                                  {/* Operating Days pills */}
                                  {detail.operating_days && detail.operating_days.length > 0 && (
                                    <div className="operating-days-bar">
                                      <span className="days-label">Active Operating Days:</span>
                                      <div className="days-pills-list">
                                        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => {
                                          const isActive = detail.operating_days.includes(day);
                                          return (
                                            <span 
                                              key={day} 
                                              className={`day-pill ${isActive ? 'day-active' : 'day-inactive'}`}
                                            >
                                              {day}
                                            </span>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <p className="no-stops-note">Direct point-to-point corridor transit (no intermediate stops).</p>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* ======================================================== */}
            {/* VIEW 2: STATION TIMETABLE & MOVEMENTS BOARD */}
            {/* ======================================================== */}
            {activeTab === 'station_board' && (
              <div className="station-board-view">
                {/* Board Selection Header */}
                <div className="station-board-toolbar">
                  <div className="station-picker">
                    <label>Select Station Hub:</label>
                    <select 
                      value={selectedStation} 
                      onChange={(e) => setSelectedStation(e.target.value)}
                      className="station-board-select"
                    >
                      {stations.map(st => (
                        <option key={st} value={st}>{st}</option>
                      ))}
                    </select>
                  </div>

                  <div className="movement-toggle-buttons">
                    <button
                      type="button"
                      className={`btn-toggle-move ${stationMoveFilter === 'ALL' ? 'active' : ''}`}
                      onClick={() => setStationMoveFilter('ALL')}
                    >
                      All Movements ({stationMovements.length})
                    </button>
                    <button
                      type="button"
                      className={`btn-toggle-move ${stationMoveFilter === 'DEPARTURES' ? 'active' : ''}`}
                      onClick={() => setStationMoveFilter('DEPARTURES')}
                    >
                      Departures Only
                    </button>
                    <button
                      type="button"
                      className={`btn-toggle-move ${stationMoveFilter === 'ARRIVALS' ? 'active' : ''}`}
                      onClick={() => setStationMoveFilter('ARRIVALS')}
                    >
                      Arrivals Only
                    </button>
                  </div>
                </div>

                {/* Station Chronological Movement Table */}
                <div className="station-board-table-card">
                  <div className="board-card-header">
                    <div className="station-title-box">
                      <Building2 size={20} className="text-cyan" />
                      <h3>{selectedStation} Station Timetable Board</h3>
                    </div>
                    <span className="board-update-chip">Real-Time Clockface Schedule</span>
                  </div>

                  {stationMovements.length === 0 ? (
                    <div className="empty-board-box">
                      <Clock size={32} />
                      <p>No scheduled movements registered for {selectedStation} in this direction.</p>
                    </div>
                  ) : (
                    <div className="board-table-responsive">
                      <table className="station-board-table">
                        <thead>
                          <tr>
                            <th>Time</th>
                            <th>Type</th>
                            <th>Train #</th>
                            <th>Service Name</th>
                            <th>Destination / Origin</th>
                            <th>Platform Track</th>
                            <th>Class</th>
                            <th>Assigned Rake</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stationMovements.map((move, mIdx) => (
                            <tr key={`${move.trainNumber}-${move.type}-${mIdx}`} className={`move-row move-${move.type.toLowerCase()}`}>
                              <td className="board-time-cell">
                                <strong>{move.time}</strong>
                              </td>
                              <td>
                                <span className={`movement-type-badge ${move.type === 'DEPARTURE' ? 'type-dep' : 'type-arr'}`}>
                                  {move.type}
                                </span>
                              </td>
                              <td className="board-train-num">
                                <code>#{move.trainNumber}</code>
                              </td>
                              <td className="board-service-name">
                                <strong>{move.trainName}</strong>
                              </td>
                              <td className="board-bound-cell">
                                <span className="bound-tag">{move.bound}</span>
                              </td>
                              <td className="board-track-cell">
                                <code>{move.track}</code>
                              </td>
                              <td>
                                <span className={`service-class-badge ${getClassBadgeClass(move.serviceClass)}`}>
                                  {move.serviceClass}
                                </span>
                              </td>
                              <td className="board-rake-cell">
                                <span className="rake-pill">{move.assignedRake}</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ======================================================== */}
            {/* VIEW 3: PHYSICAL RAKES & FLEET ROSTER */}
            {/* ======================================================== */}
            {activeTab === 'rakes' && (
              <div className="rakes-roster-view">
                {/* Roster Controls */}
                <div className="roster-toolbar">
                  <div className="roster-desc">
                    <h3>Physical Trainset Fleet (31 Continuous Rakes)</h3>
                    <p>
                      Each rake represents a tracked physical trainset operating across multiple daily revenue services,
                      maintaining continuous microscopic location from dawn rollout to night stabling.
                    </p>
                  </div>

                  <div className="roster-filter-box">
                    <label>Filter Consist Model:</label>
                    <select 
                      value={rakeTypeFilter} 
                      onChange={(e) => setRakeTypeFilter(e.target.value)}
                      className="directory-select"
                    >
                      <option value="ALL">All 7 Consist Types ({rakes.length})</option>
                      {rollingStock.map(rs => (
                        <option key={rs.type_id} value={rs.type_id}>{rs.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Rakes Grid */}
                <div className="rakes-cards-grid">
                  {filteredRakes.map(rake => (
                    <div key={rake.rake_id} className="rake-card">
                      <div className="rake-card-header">
                        <div className="rake-id-badge">
                          <Train size={16} />
                          <strong>{rake.rake_id}</strong>
                        </div>
                        <span className="rake-services-badge">
                          {rake.assigned_services_count} Daily Runs
                        </span>
                      </div>

                      <div className="rake-card-body">
                        <div className="rake-field">
                          <span className="field-label">Consist Type:</span>
                          <span className="field-value font-mono">{rake.rolling_stock_type}</span>
                        </div>

                        <div className="rake-field">
                          <span className="field-label">Home Depot:</span>
                          <span className="field-value font-bold text-cyan">{rake.home_depot}</span>
                        </div>

                        <div className="rake-field">
                          <span className="field-label">Overnight Siding:</span>
                          <span className="field-value font-mono text-dim">{rake.overnight_stabling_track}</span>
                        </div>
                      </div>

                      <div className="rake-card-footer">
                        <button
                          type="button"
                          className="btn btn-sm btn-rake-filter"
                          onClick={() => {
                            setSearchQuery(rake.rake_id);
                            setActiveTab('services');
                          }}
                        >
                          <Search size={13} />
                          <span>View Assigned Services</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ======================================================== */}
            {/* VIEW 4: ROLLING STOCK CONSIST SPECIFICATIONS */}
            {/* ======================================================== */}
            {activeTab === 'rolling_stock' && (
              <div className="rolling-stock-view">
                <div className="rolling-stock-header">
                  <h3>Rolling Stock Engineering & Kinematics Specifications</h3>
                  <p>
                    Microscopic acceleration, deceleration, length, and traction parameters codified into the 
                    SUMO simulation engine and the Reinforcement Learning observation space.
                  </p>
                </div>

                <div className="rolling-stock-grid">
                  {rollingStock.map(rs => (
                    <div key={rs.type_id} className="rs-spec-card">
                      <div className="rs-card-top">
                        <div className="rs-title-box">
                          <h4 className="rs-name">{rs.name}</h4>
                          <span className="rs-type-id"><code>{rs.type_id}</code></span>
                        </div>
                        <div className="rs-speed-badge">
                          <span className="speed-num">{rs.max_speed_kmh}</span>
                          <span className="speed-unit">km/h</span>
                        </div>
                      </div>

                      <div className="rs-metrics-grid">
                        <div className="metric-box">
                          <span className="m-label">Length</span>
                          <span className="m-val">{rs.total_length_m} m</span>
                        </div>
                        <div className="metric-box">
                          <span className="m-label">Carriages</span>
                          <span className="m-val">{rs.carriages_count} Cars</span>
                        </div>
                        <div className="metric-box">
                          <span className="m-label">Gross Mass</span>
                          <span className="m-val">{rs.gross_weight_tons} t</span>
                        </div>
                        <div className="metric-box">
                          <span className="m-label">Capacity</span>
                          <span className="m-val">{rs.passenger_capacity ? `${rs.passenger_capacity} Pax` : 'Freight Payload'}</span>
                        </div>
                      </div>

                      <div className="rs-physics-table">
                        <div className="physics-row">
                          <span>Max Acceleration:</span>
                          <strong>{rs.acceleration_ms2} m/s²</strong>
                        </div>
                        <div className="physics-row">
                          <span>Service Deceleration:</span>
                          <strong>{rs.deceleration_ms2} m/s²</strong>
                        </div>
                        <div className="physics-row">
                          <span>Emergency Decel:</span>
                          <strong>{rs.emergency_decel_ms2} m/s²</strong>
                        </div>
                        <div className="physics-row">
                          <span>Traction / Power:</span>
                          <strong>{rs.power_supply}</strong>
                        </div>
                        <div className="physics-row">
                          <span>SUMO vClass:</span>
                          <code>{rs.sumo_vclass}</code>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
