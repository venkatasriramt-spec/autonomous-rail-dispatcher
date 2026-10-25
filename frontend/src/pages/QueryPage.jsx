import React, { useState, useEffect, useMemo } from 'react';
import { 
  Train, 
  Search, 
  Clock, 
  MapPin, 
  Layers, 
  Cpu, 
  ChevronDown, 
  ChevronUp, 
  Sparkles, 
  RotateCcw, 
  Gauge, 
  ArrowUpDown, 
  ArrowUp, 
  ArrowDown, 
  Building2
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
  const [stationNodes, setStationNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Services Directory Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCorridor, setSelectedCorridor] = useState('ALL');
  const [selectedClass, setSelectedClass] = useState('ALL');
  const [selectedOrigin, setSelectedOrigin] = useState('ALL');
  const [selectedDest, setSelectedDest] = useState('ALL');
  const [sortBy, setSortBy] = useState('departure'); // 'departure' | 'arrival' | 'train_number' | 'train_name' | 'corridor' | 'service_class' | 'origin_station' | 'dest_station' | 'distance' | 'duration'
  const [sortOrder, setSortOrder] = useState('asc'); // 'asc' | 'desc'

  // Pagination State for Services Directory
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(15); // 15 | 25 | 50 | 'all'

  // Expanded Service details for stops lookup
  const [expandedTrain, setExpandedTrain] = useState(null);
  const [trainDetailsCache, setTrainDetailsCache] = useState({});
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Station Board State & Pagination
  const [selectedStation, setSelectedStation] = useState('City_1');
  const [selectedBoardDay, setSelectedBoardDay] = useState('Mon');
  const [stationBoardData, setStationBoardData] = useState([]);
  const [loadingStationBoard, setLoadingStationBoard] = useState(false);
  const [stationMoveFilter, setStationMoveFilter] = useState('ALL'); // 'ALL' | 'DEPARTURES' | 'ARRIVALS' | 'HALTS'
  const [boardCurrentPage, setBoardCurrentPage] = useState(1);
  const [boardPageSize, setBoardPageSize] = useState(15); // 15 | 25 | 50 | 'all'

  // Rakes Filter & Pagination State
  const [rakeTypeFilter, setRakeTypeFilter] = useState('ALL');
  const [rakeSortBy, setRakeSortBy] = useState('rake_id'); // 'rake_id' | 'type' | 'depot' | 'services'
  const [rakeSortOrder, setRakeSortOrder] = useState('asc'); // 'asc' | 'desc'
  const [rakeCurrentPage, setRakeCurrentPage] = useState(1);
  const [rakePageSize, setRakePageSize] = useState(12); // 12 | 24 | 'all'

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
          fetch('/api/timetable/stations')
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
            setStationNodes(stationsData);
            setStations(stationsData.map(s => s.id));
          } else {
            // Fallback list of stations extracted from services
            const uniqueStations = Array.from(new Set([
              ...servicesData.map(s => s.origin_station),
              ...servicesData.map(s => s.dest_station)
            ])).filter(Boolean).sort();
            setStations(uniqueStations);
            setStationNodes(uniqueStations.map(s => ({
              id: s,
              name: s.replace('_', ' '),
              category: s.startsWith('Town') ? 'Town' : 'City'
            })));
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

  // 1b. Fetch Station Timetable Data when selectedStation or selectedBoardDay changes
  useEffect(() => {
    let isMounted = true;
    if (!selectedStation) return;

    const fetchStationBoard = async () => {
      setLoadingStationBoard(true);
      try {
        const res = await fetch(`/api/timetable/station/${encodeURIComponent(selectedStation)}?day=${selectedBoardDay}`);
        if (res.ok) {
          const data = await res.json();
          if (isMounted) setStationBoardData(data);
        }
      } catch (err) {
        console.error('Failed to load station timetable:', err);
      } finally {
        if (isMounted) setLoadingStationBoard(false);
      }
    };

    fetchStationBoard();
    return () => { isMounted = false; };
  }, [selectedStation, selectedBoardDay]);

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
      let comparison = 0;
      switch (sortBy) {
        case 'departure':
          comparison = (a.departure_sec || 0) - (b.departure_sec || 0);
          break;
        case 'arrival':
          comparison = (a.arrival_sec || 0) - (b.arrival_sec || 0);
          break;
        case 'corridor':
          comparison = (a.corridor || '').localeCompare(b.corridor || '');
          break;
        case 'service_class':
          comparison = (a.service_class || '').localeCompare(b.service_class || '');
          break;
        case 'origin_station':
          comparison = (a.origin_station || '').localeCompare(b.origin_station || '');
          break;
        case 'dest_station':
          comparison = (a.dest_station || '').localeCompare(b.dest_station || '');
          break;
        case 'train_number':
          comparison = (a.train_number || '').localeCompare(b.train_number || '', undefined, { numeric: true });
          break;
        case 'train_name':
          comparison = (a.train_name || '').localeCompare(b.train_name || '');
          break;
        case 'distance':
          comparison = (a.total_distance_km || 0) - (b.total_distance_km || 0);
          break;
        case 'duration': {
          const durA = (a.arrival_sec || 0) - (a.departure_sec || 0);
          const durB = (b.arrival_sec || 0) - (b.departure_sec || 0);
          comparison = durA - durB;
          break;
        }
        default:
          comparison = (a.departure_sec || 0) - (b.departure_sec || 0);
      }

      // Consistent tie-breaker
      if (comparison === 0 && sortBy !== 'departure') {
        comparison = (a.departure_sec || 0) - (b.departure_sec || 0);
      }
      if (comparison === 0) {
        comparison = (a.train_number || '').localeCompare(b.train_number || '', undefined, { numeric: true });
      }

      return sortOrder === 'desc' ? -comparison : comparison;
    });
  }, [services, searchQuery, selectedCorridor, selectedClass, selectedOrigin, selectedDest, sortBy, sortOrder]);

  // Reset to first page when search, filters, or sort change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, selectedCorridor, selectedClass, selectedOrigin, selectedDest, sortBy, sortOrder, pageSize]);

  // Paginated Sliced Services
  const totalPages = useMemo(() => {
    if (pageSize === 'all') return 1;
    return Math.ceil(filteredServices.length / pageSize) || 1;
  }, [filteredServices.length, pageSize]);

  const paginatedServices = useMemo(() => {
    if (pageSize === 'all') return filteredServices;
    const start = (currentPage - 1) * pageSize;
    return filteredServices.slice(start, start + pageSize);
  }, [filteredServices, currentPage, pageSize]);

  // Helper for generating page numbers with smart ellipsis
  const getPageNumbers = () => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    if (currentPage <= 4) {
      return [1, 2, 3, 4, 5, '...', totalPages];
    }
    if (currentPage >= totalPages - 3) {
      return [1, '...', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
    }
    return [1, '...', currentPage - 1, currentPage, currentPage + 1, '...', totalPages];
  };

  // 4. Station Movements (Departures, Arrivals, Intermediate Halts)
  const stationMovements = useMemo(() => {
    if (!stationBoardData || stationBoardData.length === 0) return [];
    return stationBoardData.filter(m => {
      if (stationMoveFilter === 'DEPARTURES') {
        return m.movement_type === 'DEPARTURE';
      }
      if (stationMoveFilter === 'ARRIVALS') {
        return m.movement_type === 'ARRIVAL';
      }
      if (stationMoveFilter === 'HALTS') {
        return m.movement_type === 'PASSENGER_HALT';
      }
      return true;
    });
  }, [stationBoardData, stationMoveFilter]);

  const movementCounts = useMemo(() => {
    let deps = 0;
    let arrs = 0;
    let halts = 0;
    (stationBoardData || []).forEach(m => {
      if (m.movement_type === 'DEPARTURE') deps++;
      else if (m.movement_type === 'ARRIVAL') arrs++;
      else if (m.movement_type === 'PASSENGER_HALT') halts++;
    });
    return {
      all: (stationBoardData || []).length,
      departures: deps,
      arrivals: arrs,
      halts: halts
    };
  }, [stationBoardData]);

  // Reset Station Board page when filters change
  useEffect(() => {
    setBoardCurrentPage(1);
  }, [selectedStation, selectedBoardDay, stationMoveFilter, boardPageSize]);

  // Paginated Station Movements
  const boardTotalPages = useMemo(() => {
    if (boardPageSize === 'all') return 1;
    return Math.ceil(stationMovements.length / boardPageSize) || 1;
  }, [stationMovements.length, boardPageSize]);

  const paginatedStationMovements = useMemo(() => {
    if (boardPageSize === 'all') return stationMovements;
    const start = (boardCurrentPage - 1) * boardPageSize;
    return stationMovements.slice(start, start + boardPageSize);
  }, [stationMovements, boardCurrentPage, boardPageSize]);

  const getBoardPageNumbers = () => {
    if (boardTotalPages <= 7) {
      return Array.from({ length: boardTotalPages }, (_, i) => i + 1);
    }
    if (boardCurrentPage <= 4) {
      return [1, 2, 3, 4, 5, '...', boardTotalPages];
    }
    if (boardCurrentPage >= boardTotalPages - 3) {
      return [1, '...', boardTotalPages - 4, boardTotalPages - 3, boardTotalPages - 2, boardTotalPages - 1, boardTotalPages];
    }
    return [1, '...', boardCurrentPage - 1, boardCurrentPage, boardCurrentPage + 1, '...', boardTotalPages];
  };

  // 5. Filtered Physical Rakes
  const filteredRakes = useMemo(() => {
    let list = rakes;
    if (rakeTypeFilter !== 'ALL') {
      list = list.filter(r => r.rolling_stock_type === rakeTypeFilter);
    }
    return [...list].sort((a, b) => {
      let comp = 0;
      if (rakeSortBy === 'rake_id') {
        comp = (a.rake_id || '').localeCompare(b.rake_id || '', undefined, { numeric: true });
      } else if (rakeSortBy === 'type') {
        comp = (a.rolling_stock_type || '').localeCompare(b.rolling_stock_type || '');
      } else if (rakeSortBy === 'depot') {
        comp = (a.home_depot || '').localeCompare(b.home_depot || '');
      } else if (rakeSortBy === 'services') {
        comp = (a.assigned_services_count || 0) - (b.assigned_services_count || 0);
      }
      return rakeSortOrder === 'desc' ? -comp : comp;
    });
  }, [rakes, rakeTypeFilter, rakeSortBy, rakeSortOrder]);

  // Reset Rakes page when filter or sort changes
  useEffect(() => {
    setRakeCurrentPage(1);
  }, [rakeTypeFilter, rakeSortBy, rakeSortOrder, rakePageSize]);

  // Paginated Sliced Rakes
  const rakeTotalPages = useMemo(() => {
    if (rakePageSize === 'all') return 1;
    return Math.ceil(filteredRakes.length / rakePageSize) || 1;
  }, [filteredRakes.length, rakePageSize]);

  const paginatedRakes = useMemo(() => {
    if (rakePageSize === 'all') return filteredRakes;
    const start = (rakeCurrentPage - 1) * rakePageSize;
    return filteredRakes.slice(start, start + rakePageSize);
  }, [filteredRakes, rakeCurrentPage, rakePageSize]);

  const getRakePageNumbers = () => {
    if (rakeTotalPages <= 7) {
      return Array.from({ length: rakeTotalPages }, (_, i) => i + 1);
    }
    if (rakeCurrentPage <= 4) {
      return [1, 2, 3, 4, 5, '...', rakeTotalPages];
    }
    if (rakeCurrentPage >= rakeTotalPages - 3) {
      return [1, '...', rakeTotalPages - 4, rakeTotalPages - 3, rakeTotalPages - 2, rakeTotalPages - 1, rakeTotalPages];
    }
    return [1, '...', rakeCurrentPage - 1, rakeCurrentPage, rakeCurrentPage + 1, '...', rakeTotalPages];
  };

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

  // Helper to extract platform number directly from track/stop ID (e.g. "City_6_p1_fw" -> "1")
  const getPlatformNumber = (stopId) => {
    if (!stopId) return '1';
    const match = String(stopId).match(/_p(\d+)/i);
    if (match) return match[1];
    const pMatch = String(stopId).match(/p(\d+)/i);
    if (pMatch) return pMatch[1];
    const digitMatch = String(stopId).match(/\d+/);
    return digitMatch ? digitMatch[0] : '1';
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
                    <div className="filter-select-group has-quick-sort">
                      <select 
                        value={selectedCorridor} 
                        onChange={(e) => setSelectedCorridor(e.target.value)}
                        className="directory-select"
                        aria-label="Filter by Corridor"
                      >
                        {CORRIDORS.map(c => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className={`filter-quick-sort-btn ${sortBy === 'corridor' ? 'active' : ''}`}
                        onClick={() => {
                          if (sortBy === 'corridor') {
                            setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
                          } else {
                            setSortBy('corridor');
                            setSortOrder('asc');
                          }
                        }}
                        title={sortBy === 'corridor' 
                          ? `Sorted by Corridor (${sortOrder.toUpperCase()}). Click to toggle order.` 
                          : 'Sort by Corridor'}
                        aria-label="Sort by Corridor"
                      >
                        {sortBy === 'corridor' ? (sortOrder === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} />}
                      </button>
                    </div>

                    {/* Service Class Dropdown */}
                    <div className="filter-select-group has-quick-sort">
                      <select 
                        value={selectedClass} 
                        onChange={(e) => setSelectedClass(e.target.value)}
                        className="directory-select"
                        aria-label="Filter by Service Class"
                      >
                        {SERVICE_CLASSES.map(sc => (
                          <option key={sc.id} value={sc.id}>{sc.name}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className={`filter-quick-sort-btn ${sortBy === 'service_class' ? 'active' : ''}`}
                        onClick={() => {
                          if (sortBy === 'service_class') {
                            setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
                          } else {
                            setSortBy('service_class');
                            setSortOrder('asc');
                          }
                        }}
                        title={sortBy === 'service_class' 
                          ? `Sorted by Service Class (${sortOrder.toUpperCase()}). Click to toggle order.` 
                          : 'Sort by Service Class'}
                        aria-label="Sort by Service Class"
                      >
                        {sortBy === 'service_class' ? (sortOrder === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} />}
                      </button>
                    </div>

                    {/* Sort Selector & ASC/DESC Toggle */}
                    <div className="filter-sort-controls">
                      <div className="filter-select-group sort-group">
                        <ArrowUpDown size={15} className="sort-icon" />
                        <select 
                          value={sortBy} 
                          onChange={(e) => setSortBy(e.target.value)}
                          className="directory-select directory-sort-select"
                          aria-label="Sort by attribute"
                        >
                          <optgroup label="Filter Attributes">
                            <option value="corridor">Sort: Corridor</option>
                            <option value="service_class">Sort: Service Class</option>
                            <option value="origin_station">Sort: Origin Station</option>
                            <option value="dest_station">Sort: Destination Station</option>
                          </optgroup>
                          <optgroup label="Schedule & Fleet Metrics">
                            <option value="departure">Sort: Departure Time</option>
                            <option value="arrival">Sort: Arrival Time</option>
                            <option value="duration">Sort: Travel Duration</option>
                            <option value="distance">Sort: Total Distance</option>
                            <option value="train_number">Sort: Train Number</option>
                            <option value="train_name">Sort: Train Name</option>
                          </optgroup>
                        </select>
                      </div>

                      {/* Ascending / Descending Toggle Buttons */}
                      <div className="sort-direction-toggle" role="group" aria-label="Sort Order">
                        <button
                          type="button"
                          className={`btn-sort-dir ${sortOrder === 'asc' ? 'active' : ''}`}
                          onClick={() => setSortOrder('asc')}
                          title="Sort in Ascending Order (A→Z, Lowest First, Earliest First)"
                          aria-label="Ascending order"
                        >
                          <ArrowUp size={13} />
                          <span>ASC</span>
                        </button>
                        <button
                          type="button"
                          className={`btn-sort-dir ${sortOrder === 'desc' ? 'active' : ''}`}
                          onClick={() => setSortOrder('desc')}
                          title="Sort in Descending Order (Z→A, Highest First, Latest First)"
                          aria-label="Descending order"
                        >
                          <ArrowDown size={13} />
                          <span>DESC</span>
                        </button>
                      </div>
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
                        <button
                          type="button"
                          className={`filter-quick-sort-btn sm ${sortBy === 'origin_station' ? 'active' : ''}`}
                          onClick={() => {
                            if (sortBy === 'origin_station') {
                              setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
                            } else {
                              setSortBy('origin_station');
                              setSortOrder('asc');
                            }
                          }}
                          title={sortBy === 'origin_station' 
                            ? `Sorted by Origin Station (${sortOrder.toUpperCase()}). Click to toggle order.` 
                            : 'Sort by Origin Station'}
                          aria-label="Sort by Origin Station"
                        >
                          {sortBy === 'origin_station' ? (sortOrder === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ArrowUpDown size={12} />}
                          <span>Sort</span>
                        </button>
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
                        <button
                          type="button"
                          className={`filter-quick-sort-btn sm ${sortBy === 'dest_station' ? 'active' : ''}`}
                          onClick={() => {
                            if (sortBy === 'dest_station') {
                              setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
                            } else {
                              setSortBy('dest_station');
                              setSortOrder('asc');
                            }
                          }}
                          title={sortBy === 'dest_station' 
                            ? `Sorted by Destination Station (${sortOrder.toUpperCase()}). Click to toggle order.` 
                            : 'Sort by Destination Station'}
                          aria-label="Sort by Destination Station"
                        >
                          {sortBy === 'dest_station' ? (sortOrder === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ArrowUpDown size={12} />}
                          <span>Sort</span>
                        </button>
                      </div>
                    </div>

                    <div className="filter-actions-right">
                      <span className="active-sort-indicator">
                        <ArrowUpDown size={12} />
                        <span>
                          Sorted by <strong>{
                            sortBy === 'corridor' ? 'Corridor' :
                            sortBy === 'service_class' ? 'Service Class' :
                            sortBy === 'origin_station' ? 'Origin' :
                            sortBy === 'dest_station' ? 'Destination' :
                            sortBy === 'departure' ? 'Departure Time' :
                            sortBy === 'arrival' ? 'Arrival Time' :
                            sortBy === 'train_number' ? 'Train #' :
                            sortBy === 'train_name' ? 'Train Name' :
                            sortBy === 'distance' ? 'Distance' :
                            sortBy === 'duration' ? 'Duration' : sortBy
                          }</strong> ({sortOrder.toUpperCase()})
                        </span>
                      </span>

                      <span className="results-counter">
                        Showing <strong>{filteredServices.length}</strong> of {services.length} services
                      </span>

                      {(searchQuery || selectedCorridor !== 'ALL' || selectedClass !== 'ALL' || selectedOrigin !== 'ALL' || selectedDest !== 'ALL' || sortBy !== 'departure' || sortOrder !== 'asc') && (
                        <button 
                          type="button"
                          className="btn-reset-filters"
                          onClick={() => {
                            setSearchQuery('');
                            setSelectedCorridor('ALL');
                            setSelectedClass('ALL');
                            setSelectedOrigin('ALL');
                            setSelectedDest('ALL');
                            setSortBy('departure');
                            setSortOrder('asc');
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
                  <>
                    <div className="services-grid-list">
                    {paginatedServices.map(service => {
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
                                        <th>Platform</th>
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
                                            <span className="platform-badge" title={`Internal Track: ${stop.train_stop_id || 'N/A'}`}>
                                              {getPlatformNumber(stop.train_stop_id)}
                                            </span>
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

                  {/* Sliced Pagination Controls */}
                  {filteredServices.length > 0 && (
                    <div className="pagination-bar">
                      <div className="pagination-info">
                        <span>
                          Showing <strong>{filteredServices.length === 0 ? 0 : (currentPage - 1) * (pageSize === 'all' ? filteredServices.length : pageSize) + 1}</strong>
                          {' – '}
                          <strong>{pageSize === 'all' ? filteredServices.length : Math.min(currentPage * pageSize, filteredServices.length)}</strong>
                          {' of '}
                          <strong>{filteredServices.length}</strong> services
                        </span>

                        <div className="page-size-selector">
                          <label>Show per page:</label>
                          <select 
                            value={pageSize} 
                            onChange={(e) => setPageSize(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                            className="page-size-select"
                          >
                            <option value={15}>15 per page</option>
                            <option value={25}>25 per page</option>
                            <option value={50}>50 per page</option>
                            <option value="all">All ({filteredServices.length})</option>
                          </select>
                        </div>
                      </div>

                      {totalPages > 1 && (
                        <div className="pagination-controls">
                          <button 
                            type="button"
                            className="btn-page-nav"
                            disabled={currentPage === 1}
                            onClick={() => {
                              setCurrentPage(1);
                              window.scrollTo({ top: 380, behavior: 'smooth' });
                            }}
                            title="First Page"
                          >
                            « First
                          </button>
                          <button 
                            type="button"
                            className="btn-page-nav"
                            disabled={currentPage === 1}
                            onClick={() => {
                              setCurrentPage(p => Math.max(1, p - 1));
                              window.scrollTo({ top: 380, behavior: 'smooth' });
                            }}
                            title="Previous Page"
                          >
                            ‹ Prev
                          </button>

                          <div className="page-numbers-list">
                            {getPageNumbers().map((pNum, idx) => (
                              pNum === '...' ? (
                                <span key={`ellipsis-${idx}`} className="page-ellipsis">…</span>
                              ) : (
                                <button
                                  key={pNum}
                                  type="button"
                                  className={`btn-page-number ${currentPage === pNum ? 'active' : ''}`}
                                  onClick={() => {
                                    setCurrentPage(pNum);
                                    window.scrollTo({ top: 380, behavior: 'smooth' });
                                  }}
                                >
                                  {pNum}
                                </button>
                              )
                            ))}
                          </div>

                          <button 
                            type="button"
                            className="btn-page-nav"
                            disabled={currentPage === totalPages}
                            onClick={() => {
                              setCurrentPage(p => Math.min(totalPages, p + 1));
                              window.scrollTo({ top: 380, behavior: 'smooth' });
                            }}
                            title="Next Page"
                          >
                            Next ›
                          </button>
                          <button 
                            type="button"
                            className="btn-page-nav"
                            disabled={currentPage === totalPages}
                            onClick={() => {
                              setCurrentPage(totalPages);
                              window.scrollTo({ top: 380, behavior: 'smooth' });
                            }}
                            title="Last Page"
                          >
                            Last »
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </>
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
                  <div className="station-picker-group">
                    <div className="station-picker">
                      <label>Select Station Hub:</label>
                      <select 
                        value={selectedStation} 
                        onChange={(e) => setSelectedStation(e.target.value)}
                        className="station-board-select"
                      >
                        {stationNodes.some(s => s.category === 'City') ? (
                          <>
                            <optgroup label="Intercity Hubs (Cities)">
                              {stationNodes.filter(s => s.category === 'City').map(st => (
                                <option key={st.id} value={st.id}>{st.name}</option>
                              ))}
                            </optgroup>
                            <optgroup label="Town Stations & Passenger Halts">
                              {stationNodes.filter(s => s.category === 'Town').map(st => (
                                <option key={st.id} value={st.id}>{st.name}</option>
                              ))}
                            </optgroup>
                            <optgroup label="Depot Maintenance Facilities">
                              {stationNodes.filter(s => s.category === 'Depot').map(st => (
                                <option key={st.id} value={st.id}>{st.name}</option>
                              ))}
                            </optgroup>
                          </>
                        ) : (
                          stations.map(st => (
                            <option key={st} value={st}>{st.replace('_', ' ')}</option>
                          ))
                        )}
                      </select>
                    </div>

                    <div className="station-picker day-picker">
                      <label>Operating Day:</label>
                      <select 
                        value={selectedBoardDay} 
                        onChange={(e) => setSelectedBoardDay(e.target.value)}
                        className="station-board-select select-day"
                      >
                        <option value="Mon">Monday (Weekday Trunk · 232 Runs)</option>
                        <option value="Tue">Tuesday (233 Runs)</option>
                        <option value="Wed">Wednesday (229 Runs)</option>
                        <option value="Thu">Thursday (235 Runs)</option>
                        <option value="Fri">Friday (231 Runs)</option>
                        <option value="Sat">Saturday (Weekend Reduced · 145 Runs)</option>
                        <option value="Sun">Sunday (Weekend Reduced · 141 Runs)</option>
                        <option value="ALL">All Days (Master Weekly Matrix)</option>
                      </select>
                    </div>
                  </div>

                  <div className="movement-toggle-buttons">
                    <button
                      type="button"
                      className={`btn-toggle-move ${stationMoveFilter === 'ALL' ? 'active' : ''}`}
                      onClick={() => setStationMoveFilter('ALL')}
                    >
                      All Movements ({movementCounts.all})
                    </button>
                    <button
                      type="button"
                      className={`btn-toggle-move ${stationMoveFilter === 'DEPARTURES' ? 'active' : ''}`}
                      onClick={() => setStationMoveFilter('DEPARTURES')}
                    >
                      Origin Departures ({movementCounts.departures})
                    </button>
                    <button
                      type="button"
                      className={`btn-toggle-move ${stationMoveFilter === 'ARRIVALS' ? 'active' : ''}`}
                      onClick={() => setStationMoveFilter('ARRIVALS')}
                    >
                      Terminus Arrivals ({movementCounts.arrivals})
                    </button>
                    <button
                      type="button"
                      className={`btn-toggle-move ${stationMoveFilter === 'HALTS' ? 'active' : ''}`}
                      onClick={() => setStationMoveFilter('HALTS')}
                    >
                      Passenger Halts ({movementCounts.halts})
                    </button>
                  </div>
                </div>

                {/* Station Chronological Movement Table */}
                <div className="station-board-table-card">
                  <div className="board-card-header">
                    <div className="station-title-box">
                      <Building2 size={22} className="text-cyan" />
                      <div>
                        <h3>
                          {stationNodes.find(s => s.id === selectedStation)?.name || selectedStation.replace('_', ' ')} Station Board
                        </h3>
                        <span className="station-board-subtitle">
                          Operating Day: <strong>{selectedBoardDay === 'ALL' ? 'Master Full-Week Matrix' : DAYS_OF_WEEK.find(d => d.id === selectedBoardDay)?.name || selectedBoardDay}</strong>
                          {' · '}
                          {stationMovements.length} Movements Listed
                        </span>
                      </div>
                    </div>
                    <div className="board-header-badges">
                      <span className="board-update-chip">
                        <Clock size={12} className="inline-icon" />
                        <span>Synchronized Taktfahrplan</span>
                      </span>
                    </div>
                  </div>

                  {loadingStationBoard ? (
                    <div className="empty-board-box">
                      <div className="loading-spinner-ring sm" />
                      <p>Loading timetabled movements for {selectedStation} ({selectedBoardDay})...</p>
                    </div>
                  ) : stationMovements.length === 0 ? (
                    <div className="empty-board-box">
                      <Clock size={32} />
                      <p>No scheduled movements registered for {selectedStation} on {selectedBoardDay} in this category.</p>
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
                            <th>Platform</th>
                            <th>Dwell</th>
                            <th>Class</th>
                            <th>Assigned Rake</th>
                          </tr>
                        </thead>
                        <tbody>
                          {paginatedStationMovements.map((move, mIdx) => (
                            <tr 
                              key={`${move.train_number}-${move.stop_sequence || mIdx}-${mIdx}`} 
                              className={`move-row move-${(move.movement_type || 'halt').toLowerCase()}`}
                            >
                              <td className="board-time-cell">
                                <strong>{move.display_time || move.departure_time || move.arrival_time}</strong>
                                {move.movement_type === 'PASSENGER_HALT' && move.arrival_time && (
                                  <span className="board-subtime">Arr: {move.arrival_time}</span>
                                )}
                              </td>
                              <td>
                                {move.movement_type === 'DEPARTURE' && (
                                  <span className="movement-type-badge type-dep">ORIGIN DEP</span>
                                )}
                                {move.movement_type === 'ARRIVAL' && (
                                  <span className="movement-type-badge type-arr">TERMINUS ARR</span>
                                )}
                                {move.movement_type === 'PASSENGER_HALT' && (
                                  <span className="movement-type-badge type-halt">PASSENGER HALT</span>
                                )}
                              </td>
                              <td className="board-train-num">
                                <code>#{move.train_number}</code>
                              </td>
                              <td className="board-service-name">
                                <strong>{move.train_name}</strong>
                                {move.corridor && (
                                  <span className="board-subcorridor">{move.corridor.replace('_', ' ')}</span>
                                )}
                              </td>
                              <td className="board-track-cell">
                                <span className="platform-badge" title={`Internal Track: ${move.train_stop_id || 'N/A'}`}>
                                  {getPlatformNumber(move.train_stop_id)}
                                </span>
                              </td>
                              <td className="board-dwell-cell">
                                {move.movement_type === 'PASSENGER_HALT' ? (
                                  <span className="dwell-tag">{move.dwell_sec ? `${move.dwell_sec}s dwell` : 'Halt'}</span>
                                ) : move.movement_type === 'DEPARTURE' ? (
                                  <span className="dwell-tag-origin">Origin</span>
                                ) : (
                                  <span className="dwell-tag-term">Terminus</span>
                                )}
                              </td>
                              <td>
                                <span className={`service-class-badge ${getClassBadgeClass(move.service_class)}`}>
                                  {move.service_class}
                                </span>
                              </td>
                              <td className="board-rake-cell">
                                <span className="rake-pill">{move.assigned_rake}</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Sliced Pagination Controls for Station Board */}
                  {stationMovements.length > 0 && (
                    <div className="pagination-bar station-board-pagination">
                      <div className="pagination-info">
                        <span>
                          Showing <strong>{stationMovements.length === 0 ? 0 : (boardCurrentPage - 1) * (boardPageSize === 'all' ? stationMovements.length : boardPageSize) + 1}</strong>
                          {' – '}
                          <strong>{boardPageSize === 'all' ? stationMovements.length : Math.min(boardCurrentPage * boardPageSize, stationMovements.length)}</strong>
                          {' of '}
                          <strong>{stationMovements.length}</strong> movements
                        </span>

                        <div className="page-size-selector">
                          <label>Show per page:</label>
                          <select 
                            value={boardPageSize} 
                            onChange={(e) => setBoardPageSize(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                            className="page-size-select"
                          >
                            <option value={15}>15 per page</option>
                            <option value={25}>25 per page</option>
                            <option value={50}>50 per page</option>
                            <option value="all">All ({stationMovements.length})</option>
                          </select>
                        </div>
                      </div>

                      {boardTotalPages > 1 && (
                        <div className="pagination-controls">
                          <button 
                            type="button"
                            className="btn-page-nav"
                            disabled={boardCurrentPage === 1}
                            onClick={() => {
                              setBoardCurrentPage(1);
                              window.scrollTo({ top: 380, behavior: 'smooth' });
                            }}
                            title="First Page"
                          >
                            « First
                          </button>
                          <button 
                            type="button"
                            className="btn-page-nav"
                            disabled={boardCurrentPage === 1}
                            onClick={() => {
                              setBoardCurrentPage(p => Math.max(1, p - 1));
                              window.scrollTo({ top: 380, behavior: 'smooth' });
                            }}
                            title="Previous Page"
                          >
                            ‹ Prev
                          </button>

                          <div className="page-numbers-list">
                            {getBoardPageNumbers().map((pNum, idx) => (
                              pNum === '...' ? (
                                <span key={`ellipsis-board-${idx}`} className="page-ellipsis">…</span>
                              ) : (
                                <button
                                  key={pNum}
                                  type="button"
                                  className={`btn-page-number ${boardCurrentPage === pNum ? 'active' : ''}`}
                                  onClick={() => {
                                    setBoardCurrentPage(pNum);
                                    window.scrollTo({ top: 380, behavior: 'smooth' });
                                  }}
                                >
                                  {pNum}
                                </button>
                              )
                            ))}
                          </div>

                          <button 
                            type="button"
                            className="btn-page-nav"
                            disabled={boardCurrentPage === boardTotalPages}
                            onClick={() => {
                              setBoardCurrentPage(p => Math.min(boardTotalPages, p + 1));
                              window.scrollTo({ top: 380, behavior: 'smooth' });
                            }}
                            title="Next Page"
                          >
                            Next ›
                          </button>
                          <button 
                            type="button"
                            className="btn-page-nav"
                            disabled={boardCurrentPage === boardTotalPages}
                            onClick={() => {
                              setBoardCurrentPage(boardTotalPages);
                              window.scrollTo({ top: 380, behavior: 'smooth' });
                            }}
                            title="Last Page"
                          >
                            Last »
                          </button>
                        </div>
                      )}
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

                  <div className="roster-filter-controls">
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

                    <div className="roster-sort-box">
                      <label>Sort Fleet:</label>
                      <div className="filter-sort-controls">
                        <select 
                          value={rakeSortBy} 
                          onChange={(e) => setRakeSortBy(e.target.value)}
                          className="directory-select directory-sort-select"
                        >
                          <option value="rake_id">Sort: Rake ID</option>
                          <option value="type">Sort: Consist Model (Filter)</option>
                          <option value="services">Sort: Daily Service Count</option>
                          <option value="depot">Sort: Home Depot</option>
                        </select>
                        <div className="sort-direction-toggle" role="group" aria-label="Rake Sort Order">
                          <button
                            type="button"
                            className={`btn-sort-dir ${rakeSortOrder === 'asc' ? 'active' : ''}`}
                            onClick={() => setRakeSortOrder('asc')}
                            title="Sort in Ascending Order"
                          >
                            <ArrowUp size={13} />
                            <span>ASC</span>
                          </button>
                          <button
                            type="button"
                            className={`btn-sort-dir ${rakeSortOrder === 'desc' ? 'active' : ''}`}
                            onClick={() => setRakeSortOrder('desc')}
                            title="Sort in Descending Order"
                          >
                            <ArrowDown size={13} />
                            <span>DESC</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Rakes Grid */}
                <div className="rakes-cards-grid">
                  {paginatedRakes.map(rake => (
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

                {/* Sliced Pagination Controls for Rakes Roster */}
                {filteredRakes.length > 0 && (
                  <div className="pagination-bar">
                    <div className="pagination-info">
                      <span>
                        Showing <strong>{filteredRakes.length === 0 ? 0 : (rakeCurrentPage - 1) * (rakePageSize === 'all' ? filteredRakes.length : rakePageSize) + 1}</strong>
                        {' – '}
                        <strong>{rakePageSize === 'all' ? filteredRakes.length : Math.min(rakeCurrentPage * rakePageSize, filteredRakes.length)}</strong>
                        {' of '}
                        <strong>{filteredRakes.length}</strong> physical rakes
                      </span>

                      <div className="page-size-selector">
                        <label>Show per page:</label>
                        <select 
                          value={rakePageSize} 
                          onChange={(e) => setRakePageSize(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                          className="page-size-select"
                        >
                          <option value={12}>12 per page</option>
                          <option value={24}>24 per page</option>
                          <option value="all">All ({filteredRakes.length})</option>
                        </select>
                      </div>
                    </div>

                    {rakeTotalPages > 1 && (
                      <div className="pagination-controls">
                        <button 
                          type="button"
                          className="btn-page-nav"
                          disabled={rakeCurrentPage === 1}
                          onClick={() => {
                            setRakeCurrentPage(1);
                            window.scrollTo({ top: 380, behavior: 'smooth' });
                          }}
                          title="First Page"
                        >
                          « First
                        </button>
                        <button 
                          type="button"
                          className="btn-page-nav"
                          disabled={rakeCurrentPage === 1}
                          onClick={() => {
                            setRakeCurrentPage(p => Math.max(1, p - 1));
                            window.scrollTo({ top: 380, behavior: 'smooth' });
                          }}
                          title="Previous Page"
                        >
                          ‹ Prev
                        </button>

                        <div className="page-numbers-list">
                          {getRakePageNumbers().map((pNum, idx) => (
                            pNum === '...' ? (
                              <span key={`ellipsis-rake-${idx}`} className="page-ellipsis">…</span>
                            ) : (
                              <button
                                key={pNum}
                                type="button"
                                className={`btn-page-number ${rakeCurrentPage === pNum ? 'active' : ''}`}
                                onClick={() => {
                                  setRakeCurrentPage(pNum);
                                  window.scrollTo({ top: 380, behavior: 'smooth' });
                                }}
                              >
                                {pNum}
                              </button>
                            )
                          ))}
                        </div>

                        <button 
                          type="button"
                          className="btn-page-nav"
                          disabled={rakeCurrentPage === rakeTotalPages}
                          onClick={() => {
                            setRakeCurrentPage(p => Math.min(rakeTotalPages, p + 1));
                            window.scrollTo({ top: 380, behavior: 'smooth' });
                          }}
                          title="Next Page"
                        >
                          Next ›
                        </button>
                        <button 
                          type="button"
                          className="btn-page-nav"
                          disabled={rakeCurrentPage === rakeTotalPages}
                          onClick={() => {
                            setRakeCurrentPage(rakeTotalPages);
                            window.scrollTo({ top: 380, behavior: 'smooth' });
                          }}
                          title="Last Page"
                        >
                          Last »
                        </button>
                      </div>
                    )}
                  </div>
                )}
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
