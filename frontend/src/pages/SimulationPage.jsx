import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  FastForward, 
  AlertTriangle, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Clock, 
  Search, 
  Train, 
  X,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  GitFork,
  Zap,
  MapPin,
  ArrowUpRight,
  ArrowDownRight,
  Eye,
  Activity,
  Layers,
  Navigation,
  Flame,
  Crosshair,
  GripHorizontal,
  CheckCircle2,
  ArrowRight
} from 'lucide-react';
import './SimulationPage.css';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const MODELS = [
  { id: 'Centralized_PPO', label: 'Centralized PPO (Lead AI)' },
  { id: 'Hierarchical_Hybrid', label: 'Hierarchical Hybrid Ensemble' },
  { id: 'Decentralized_MAPPO', label: 'Decentralized MAPPO (Multi-Agent)' },
  { id: 'Comm_MAPPO', label: 'Comm-MAPPO (GNN Communication)' },
  { id: 'Multi_Train_Centralized_PPO', label: 'Multi-Train Centralized PPO' },
  { id: 'Priority_Greedy_Heuristic', label: 'Dynamic Priority Heuristic' },
  { id: 'FIFO_Heuristic', label: 'First-Come First-Served (FIFO)' },
];

export default function SimulationPage() {
  // Model B: Per-User Isolated Simulation Session ID
  const [sessionId, setSessionId] = useState(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const urlSid = params.get('session') || params.get('sessionId');
      if (urlSid) return urlSid;
      const stored = localStorage.getItem('railway_sim_session_id');
      if (stored) return stored;
      const newSid = 'sess_' + (typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID().replace(/-/g, '').slice(0, 10)
        : Math.random().toString(36).substring(2, 10));
      localStorage.setItem('railway_sim_session_id', newSid);
      return newSid;
    } catch {
      return 'sess_default';
    }
  });
  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;

  const handleNewSession = useCallback(() => {
    const newSid = 'sess_' + (typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID().replace(/-/g, '').slice(0, 10)
      : Math.random().toString(36).substring(2, 10));
    try {
      localStorage.setItem('railway_sim_session_id', newSid);
    } catch {}
    setSessionId(newSid);
    sessionIdRef.current = newSid;
  }, []);

  // Sim state
  const [simStatus, setSimStatus] = useState({
    running: false,
    paused: true,
    sim_time_sec: 21600,
    sim_time_formatted: '06:00:00',
    current_model: 'Centralized_PPO',
    current_day: 'Mon',
    speed_multiplier: 1.0,
    active_disruptions: [],
    active_disruptions_data: [],
    active_overrides: {},
    day_completed: false
  });

  const [dayCompletionDismissed, setDayCompletionDismissed] = useState(false);

  // Telemetry stream
  const [trains, setTrains] = useState([]);
  const [kpis, setKpis] = useState({
    active_trains: 0,
    punctuality_pct: 100.0,
    avg_delay_sec: 0.0,
    max_delay_sec: 0.0,
    platform_utilization_pct: 28.5,
    throughput_tph: 18.0
  });

  // Network Geometry cache
  const [geometry, setGeometry] = useState(null);
  const [loadingGeometry, setLoadingGeometry] = useState(true);

  // Filters & Selected Train
  const [selectedDay, setSelectedDay] = useState('Mon');
  const [selectedModel, setSelectedModel] = useState('Centralized_PPO');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [delayOnlyFilter, setDelayOnlyFilter] = useState(false);
  const [selectedTrain, setSelectedTrain] = useState(null);
  const [selectedStation, setSelectedStation] = useState(null);
  const [stationCardPos, setStationCardPos] = useState({ x: 20, y: 145 });
  const [isDraggingStationCard, setIsDraggingStationCard] = useState(false);
  const dragCardRef = useRef({ startX: 0, startY: 0, origX: 20, origY: 145 });
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(380);
  const [isResizingSidebar, setIsResizingSidebar] = useState(false);
  const resizeStartXRef = useRef(0);
  const resizeStartWidthRef = useRef(380);
  const [activeSideTab, setActiveSideTab] = useState('trains'); // 'trains' | 'station'

  // Google Maps Railway Feature Navigation & Overlays
  const [activeFeatureLayer, setActiveFeatureLayer] = useState('none'); // 'none' | 'all' | 'crossovers' | 'loops' | 'buffer_stops' | 'signals'
  const [selectedFeature, setSelectedFeature] = useState(null);
  const [showFeatureMenu, setShowFeatureMenu] = useState(false);
  const [showSignalHeads, setShowSignalHeads] = useState(false);
  const [showOverlayLabels, setShowOverlayLabels] = useState(false); // Toggle to disable names & text crowding the screen
  const [showMapLegend, setShowMapLegend] = useState(true); // Interactive Track Legend & Speed Profile Guide

  // Get peer features for cyclical previous/next navigation
  const getPeerFeatures = useCallback((feat) => {
    if (!feat || !geometry) return [];
    if (feat.type === 'crossover') {
      return (geometry.track_features || []).filter(f => f.type === 'crossover');
    }
    if (feat.type === 'passing_loop' || feat.type === 'express_thru') {
      return (geometry.track_features || []).filter(f => f.type === 'passing_loop' || f.type === 'express_thru');
    }
    if (feat.type === 'buffer_stop') {
      return (geometry.buffer_stops || []).map(b => ({ ...b, type: 'buffer_stop' }));
    }
    if (feat.signal_type || feat.type === 'signal') {
      return (geometry.signals || []).map(s => ({ ...s, type: 'signal' }));
    }
    return geometry.track_features || [];
  }, [geometry]);

  // Compute Selected Station Topology (Platforms, Converging Inbound, Diverging Outbound, Crossovers, Switches)
  const selectedStationTopology = React.useMemo(() => {
    if (!selectedStation || !geometry || !geometry.lanes) {
      return { 
        platforms: [], 
        converging: [], 
        diverging: [], 
        crossovers: [], 
        switches: [], 
        platEdgeIds: new Set(), 
        convEdgeIds: new Set(), 
        divEdgeIds: new Set(),
        switchEdgeIds: new Set() 
      };
    }
    const stX = selectedStation.x;
    const stY = selectedStation.y;
    const platforms = [];
    const converging = [];
    const diverging = [];
    const crossovers = [];
    const switches = [];
    const radius = 3200;

    for (const lane of geometry.lanes) {
      const coords = lane.coordinates || lane.shape;
      if (!coords || coords.length < 2) continue;

      let near = false;
      for (let i = 0; i < coords.length; i++) {
        const dx = coords[i][0] - stX;
        const dy = coords[i][1] - stY;
        if (dx * dx + dy * dy <= radius * radius) {
          near = true;
          break;
        }
      }
      if (!near) continue;

      const cat = lane.category || '';
      const isPlat = cat === 'platform' || (lane.edge_id && lane.edge_id.includes('plat'));
      if (isPlat) {
        platforms.push(lane);
        continue;
      }

      if (cat === 'switch' || lane.is_internal || (lane.edge_id && (lane.edge_id.startsWith(':') || lane.edge_id.includes('Throat')))) {
        switches.push(lane);
        continue;
      }

      if (cat === 'yard') {
        continue; // Yard staging tracks are not mainline connecting corridors
      }

      const cStart = coords[0];
      const cEnd = coords[coords.length - 1];
      const dStart = Math.hypot(cStart[0] - stX, cStart[1] - stY);
      const dEnd = Math.hypot(cEnd[0] - stX, cEnd[1] - stY);

      if (dStart - dEnd > 25) {
        converging.push(lane);
      } else if (dEnd - dStart > 25) {
        diverging.push(lane);
      } else {
        crossovers.push(lane);
      }
    }

    return {
      platforms,
      converging,
      diverging,
      crossovers,
      switches,
      platEdgeIds: new Set(platforms.map(l => l.edge_id)),
      convEdgeIds: new Set(converging.map(l => l.edge_id)),
      divEdgeIds: new Set(diverging.map(l => l.edge_id)),
      switchEdgeIds: new Set(switches.map(l => l.edge_id))
    };
  }, [selectedStation, geometry]);

  // Compute Trains Active on Converging, Platform, or Diverging Tracks for Selected Station
  const selectedStationTrains = React.useMemo(() => {
    if (!selectedStation) {
      return { approaching: [], dwelling: [], departing: [] };
    }
    const stX = selectedStation.x;
    const stY = selectedStation.y;
    const approaching = [];
    const dwelling = [];
    const departing = [];

    const { platEdgeIds, convEdgeIds, divEdgeIds } = selectedStationTopology;

    for (const t of trains) {
      const dist = Math.hypot(t.x - stX, t.y - stY);
      if (dist > 3500) continue;

      const road = t.road_id || '';
      const upcoming = t.upcoming_station || '';
      const isTarget = upcoming === selectedStation.station_name || upcoming.includes(selectedStation.station_name);

      if (platEdgeIds.has(road) || (dist < 800 && t.is_at_stop)) {
        dwelling.push(t);
      } else if (convEdgeIds.has(road) || (isTarget && dist < 3200)) {
        approaching.push(t);
      } else if (divEdgeIds.has(road) || dist < 3000) {
        departing.push(t);
      }
    }

    return { approaching, dwelling, departing };
  }, [selectedStation, selectedStationTopology, trains]);

  // Filtered Trains computed for both Canvas & Sidebar
  const filteredTrains = React.useMemo(() => {
    return trains.filter(t => {
      if (categoryFilter !== 'ALL' && t.category !== categoryFilter) return false;
      if (delayOnlyFilter && (!t.delay_sec || t.delay_sec <= 0)) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase().trim();
        const num = String(t.train_number || t.id).toLowerCase();
        const name = String(t.train_name || '').toLowerCase();
        const route = String(t.route_desc || '').toLowerCase();
        if (!num.includes(q) && !name.includes(q) && !route.includes(q)) return false;
      }
      return true;
    });
  }, [trains, categoryFilter, delayOnlyFilter, searchQuery]);

  // Canvas Refs
  const canvasRef = useRef(null);
  const transformRef = useRef({ scale: 0.03, offsetX: 100, offsetY: 100 });
  const isDraggingRef = useRef(false);
  const didDragRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const wsRef = useRef(null);
  const selectedSpeedRef = useRef(null);
  const confirmedSpeedRef = useRef(1.0);
  const speedQueueRef = useRef(Promise.resolve());
  const speedRequestIdRef = useRef(0);
  const latestConfirmedSpeedReqIdRef = useRef(0);
  const lastConfirmedSpeedTimeRef = useRef(0);

  // Helper: compute centered transform from geometry bounds
  const getCenteredTransform = useCallback((bounds, cWidth, cHeight) => {
    if (!bounds || bounds.length < 4) return { scale: 0.03, offsetX: 50, offsetY: 50 };
    const [minX, minY, maxX, maxY] = bounds;
    const netWidth = maxX - minX || 30000;
    const netHeight = maxY - minY || 27000;
    const pad = 40;
    const availW = Math.max(100, cWidth - pad * 2);
    const availH = Math.max(100, cHeight - pad * 2);
    const scale = Math.min(availW / netWidth, availH / netHeight);
    const offsetX = (cWidth - netWidth * scale) / 2 - minX * scale;
    const offsetY = (cHeight - netHeight * scale) / 2 - minY * scale;
    return { scale, offsetX, offsetY };
  }, []);

  // Smooth animated zoom to a station
  const zoomToStation = useCallback((station, customScale) => {
    if (!station || !canvasRef.current || !geometry || !geometry.bounds) return;
    const canvas = canvasRef.current;
    const cWidth = canvas.clientWidth;
    const cHeight = canvas.clientHeight;
    const [, minY, , maxY] = geometry.bounds;
    const screenStationX = station.x;
    const screenStationY = maxY - station.y + minY;

    // Zoom deep into the station yard so every individual track line and switch connection is distinct
    const targetScale = customScale || ((station.platform_count && station.platform_count > 6) ? 1.5 : 2.0);
    const targetOffsetX = cWidth / 2 - screenStationX * targetScale;
    const targetOffsetY = cHeight / 2 - screenStationY * targetScale;

    const startScale = transformRef.current.scale;
    const startOffsetX = transformRef.current.offsetX;
    const startOffsetY = transformRef.current.offsetY;
    const startTime = performance.now();
    const duration = 500;

    setSelectedStation(station);
    setSelectedTrain(null);
    setActiveSideTab('station');

    const animate = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      const ease = progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(-2 * progress + 2, 3) / 2;

      transformRef.current.scale = startScale + (targetScale - startScale) * ease;
      transformRef.current.offsetX = startOffsetX + (targetOffsetX - startOffsetX) * ease;
      transformRef.current.offsetY = startOffsetY + (targetOffsetY - startOffsetY) * ease;

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };
    requestAnimationFrame(animate);
  }, [geometry]);

  // Draggable Station Focus Card Handlers
  const handleCardPointerDown = useCallback((e) => {
    if (e.target.closest('button')) return;
    setIsDraggingStationCard(true);
    dragCardRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      origX: stationCardPos.x,
      origY: stationCardPos.y
    };
  }, [stationCardPos]);

  useEffect(() => {
    if (!isDraggingStationCard) return;

    const handlePointerMove = (e) => {
      const dx = e.clientX - dragCardRef.current.startX;
      const dy = e.clientY - dragCardRef.current.startY;
      const cardW = 290;
      const cardH = 110;
      const maxX = Math.max(10, window.innerWidth - cardW - 10);
      const maxY = Math.max(10, window.innerHeight - cardH - 10);
      const nextX = Math.min(Math.max(10, dragCardRef.current.origX + dx), maxX);
      const nextY = Math.min(Math.max(10, dragCardRef.current.origY + dy), maxY);
      setStationCardPos({ x: nextX, y: nextY });
    };

    const handlePointerUp = () => {
      setIsDraggingStationCard(false);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [isDraggingStationCard]);

  // Resizable Right Sidebar Handler (cursor drag to the left/right)
  const handleResizePointerDown = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizingSidebar(true);
    resizeStartXRef.current = e.clientX;
    resizeStartWidthRef.current = sidebarWidth;
  }, [sidebarWidth]);

  useEffect(() => {
    if (!isResizingSidebar) return;

    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';

    const handlePointerMove = (e) => {
      // Dragging cursor to the left (smaller clientX) expands the sidebar width
      const deltaX = resizeStartXRef.current - e.clientX;
      const nextW = Math.min(
        Math.max(260, resizeStartWidthRef.current + deltaX),
        Math.floor(window.innerWidth * 0.72)
      );
      setSidebarWidth(nextW);
    };

    const handlePointerUp = () => {
      setIsResizingSidebar(false);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isResizingSidebar]);

  // Smooth animated zoom to a train
  const zoomToTrain = useCallback((t) => {
    if (!t || !canvasRef.current || !geometry || !geometry.bounds) return;
    const canvas = canvasRef.current;
    const cWidth = canvas.clientWidth;
    const cHeight = canvas.clientHeight;
    const [, minY, , maxY] = geometry.bounds;
    const screenTrainX = t.x;
    const screenTrainY = maxY - t.y + minY;

    const targetScale = 0.95;
    const targetOffsetX = cWidth / 2 - screenTrainX * targetScale;
    const targetOffsetY = cHeight / 2 - screenTrainY * targetScale;

    const startScale = transformRef.current.scale;
    const startOffsetX = transformRef.current.offsetX;
    const startOffsetY = transformRef.current.offsetY;
    const startTime = performance.now();
    const duration = 450;

    setSelectedTrain(t);

    const animate = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      const ease = progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(-2 * progress + 2, 3) / 2;

      transformRef.current.scale = startScale + (targetScale - startScale) * ease;
      transformRef.current.offsetX = startOffsetX + (targetOffsetX - startOffsetX) * ease;
      transformRef.current.offsetY = startOffsetY + (targetOffsetY - startOffsetY) * ease;

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };
    requestAnimationFrame(animate);
  }, [geometry]);

  // Smooth animated zoom to a railway track feature (Crossover, Passing Loop, Buffer Stop, Signal)
  const zoomToFeature = useCallback((feature, overrideScale) => {
    if (!feature || !canvasRef.current || !geometry || !geometry.bounds) return;
    const canvas = canvasRef.current;
    const cWidth = canvas.clientWidth;
    const cHeight = canvas.clientHeight;
    const [, minY, , maxY] = geometry.bounds;
    const screenX = feature.x;
    const screenY = maxY - feature.y + minY;

    let targetScale = overrideScale || 2.5;
    if (!overrideScale) {
      if (feature.type === 'crossover') targetScale = 2.5;
      else if (feature.type === 'passing_loop' || feature.type === 'express_thru') targetScale = 3.2;
      else if (feature.type === 'buffer_stop') targetScale = 5.5;
      else if (feature.signal_type) targetScale = 4.0;
    }

    const targetOffsetX = cWidth / 2 - screenX * targetScale;
    const targetOffsetY = cHeight / 2 - screenY * targetScale;

    const startScale = transformRef.current.scale;
    const startOffsetX = transformRef.current.offsetX;
    const startOffsetY = transformRef.current.offsetY;
    const startTime = performance.now();
    const duration = 500;

    setSelectedFeature(feature);
    setSelectedTrain(null);
    setSelectedStation(null);

    const animate = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      const ease = progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(-2 * progress + 2, 3) / 2;

      transformRef.current.scale = startScale + (targetScale - startScale) * ease;
      transformRef.current.offsetX = startOffsetX + (targetOffsetX - startOffsetX) * ease;
      transformRef.current.offsetY = startOffsetY + (targetOffsetY - startOffsetY) * ease;

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };
    requestAnimationFrame(animate);
  }, [geometry]);

  // Smooth animated reset to full network view
  const resetViewAnimated = useCallback(() => {
    if (!geometry?.bounds || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const cWidth = canvas.clientWidth || 1000;
    const cHeight = canvas.clientHeight || 700;
    const target = getCenteredTransform(geometry.bounds, cWidth, cHeight);

    const startScale = transformRef.current.scale;
    const startOffsetX = transformRef.current.offsetX;
    const startOffsetY = transformRef.current.offsetY;
    const startTime = performance.now();
    const duration = 500;

    setSelectedStation(null);

    const animate = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      const ease = progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(-2 * progress + 2, 3) / 2;

      transformRef.current.scale = startScale + (target.scale - startScale) * ease;
      transformRef.current.offsetX = startOffsetX + (target.offsetX - startOffsetX) * ease;
      transformRef.current.offsetY = startOffsetY + (target.offsetY - startOffsetY) * ease;

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };
    requestAnimationFrame(animate);
  }, [geometry, getCenteredTransform]);

  // Keyboard arrow navigation for infrastructure features
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!selectedFeature) return;
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;

      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        const peerList = getPeerFeatures(selectedFeature);
        if (peerList.length > 1) {
          e.preventDefault();
          const curIdx = peerList.findIndex(f => f.id === selectedFeature.id);
          const nextIdx = (curIdx + 1) % peerList.length;
          zoomToFeature(peerList[nextIdx]);
        }
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        const peerList = getPeerFeatures(selectedFeature);
        if (peerList.length > 1) {
          e.preventDefault();
          const curIdx = peerList.findIndex(f => f.id === selectedFeature.id);
          const prevIdx = (curIdx - 1 + peerList.length) % peerList.length;
          zoomToFeature(peerList[prevIdx]);
        }
      } else if (e.key === 'Escape') {
        setSelectedFeature(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedFeature, getPeerFeatures, zoomToFeature]);

  // 1. Fetch Network Geometry on Mount
  useEffect(() => {
    let mounted = true;
    const fetchGeometry = async () => {
      try {
        let res = await fetch('/network_geometry.json');
        if (!res.ok) {
          res = await fetch('/api/network/geometry');
        }
        if (res.ok) {
          const data = await res.json();
          if (mounted) {
            setGeometry(data);
            setLoadingGeometry(false);

            // Fit network to canvas initial scale
            if (data.bounds && canvasRef.current) {
              const cWidth = canvasRef.current.clientWidth || 1000;
              const cHeight = canvasRef.current.clientHeight || 700;
              transformRef.current = getCenteredTransform(data.bounds, cWidth, cHeight);
            }
          }
        }
      } catch (err) {
        console.error('Error fetching geometry:', err);
      }
    };
    fetchGeometry();
    return () => { mounted = false; };
  }, [getCenteredTransform]);

  // 2. Fetch Sim Status and Telemetry Poll Fallback
  const fetchStatus = useCallback(async () => {
    const snapshotConfirmedId = latestConfirmedSpeedReqIdRef.current;
    try {
      const res = await fetch('/api/sim/status', {
        headers: { 'X-Session-ID': sessionIdRef.current }
      });
      if (res.ok) {
        const data = await res.json();
        // Apply snapshot speeds only when they are not older than the latest successful speed request
        const isSpeedFresh = snapshotConfirmedId >= latestConfirmedSpeedReqIdRef.current;
        if (isSpeedFresh && data.speed_multiplier !== undefined && data.speed_multiplier !== null) {
          confirmedSpeedRef.current = data.speed_multiplier;
        }
        setSimStatus(prev => ({
          ...prev,
          running: data.status === 'RUNNING',
          paused: data.status === 'PAUSED',
          sim_time_sec: data.sim_time_sec ?? prev.sim_time_sec,
          sim_time_formatted: data.time_formatted ?? prev.sim_time_formatted,
          current_model: data.dispatcher_model ?? prev.current_model,
          current_day: data.calendar_day ?? prev.current_day,
          speed_multiplier: isSpeedFresh
            ? (selectedSpeedRef.current ?? data.speed_multiplier ?? prev.speed_multiplier)
            : (selectedSpeedRef.current ?? confirmedSpeedRef.current ?? prev.speed_multiplier),
          active_disruptions: data.active_disruptions ?? prev.active_disruptions,
          active_disruptions_data: data.active_disruptions_data ?? prev.active_disruptions_data ?? [],
          active_overrides: data.active_overrides ?? prev.active_overrides ?? {},
          day_completed: Boolean(data.day_completed)
        }));
        if (data.daily_summary) {
          setKpis(prev => ({
            ...prev,
            daily_summary: data.daily_summary,
            avg_delay_sec: data.daily_summary.mean_delay_sec ?? prev.avg_delay_sec,
            punctuality_pct: data.daily_summary.punctuality_pct ?? prev.punctuality_pct,
            total_actions_taken: data.daily_summary.total_actions_taken ?? prev.total_actions_taken
          }));
        } else if (data.mean_delay_sec !== undefined) {
          setKpis(prev => ({
            ...prev,
            avg_delay_sec: data.mean_delay_sec,
            punctuality_pct: data.punctuality_pct ?? prev.punctuality_pct,
            total_actions_taken: data.total_actions_taken ?? prev.total_actions_taken
          }));
        }
        if (data.calendar_day) setSelectedDay(data.calendar_day);
        if (data.dispatcher_model) setSelectedModel(data.dispatcher_model);
      }
    } catch (e) {
      console.warn('Status poll error:', e);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // 3. Connect WebSocket for Real-Time Telemetry
  useEffect(() => {
    let isMounted = true;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Use current host so Vite proxy forwards to backend with session isolation
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry?sessionId=${encodeURIComponent(sessionId)}`;
    let ws = null;
    let reconnectTimeout = null;

    const connectWS = () => {
      if (!isMounted) return;
      try {
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!isMounted && ws) {
            try { ws.close(); } catch {}
          }
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            
            // Ingest active trains
            const incomingTrains = data.trains || data.active_trains;
            if (Array.isArray(incomingTrains)) {
              setTrains(incomingTrains.map(t => {
                let cat = t.category;
                if (!cat) {
                  const vid = t.id || '';
                  const vtype = t.vtype || '';
                  if (vid.startsWith('HS') || vtype.includes('high_speed')) {
                    cat = 'HighSpeed';
                  } else if (vid.startsWith('FRT') || vtype.includes('freight')) {
                    cat = 'Freight';
                  } else {
                    cat = 'Regional';
                  }
                }
                const speedMs = t.speed_ms ?? t.speed ?? ((t.speed_kmh ?? 0) / 3.6);
                return {
                  ...t,
                  category: cat,
                  train_number: t.train_number || t.id,
                  speed_kmh: t.speed_kmh ?? Math.round(speedMs * 3.6),
                  speed: speedMs
                };
              }));
            }

            // Ingest KPIs
            const incomingKpis = data.kpis || data.kpi;
            if (incomingKpis) {
              setKpis(prev => ({
                ...prev,
                active_trains: incomingKpis.active_trains_count ?? incomingKpis.active_trains ?? 0,
                punctuality_pct: incomingKpis.punctuality_pct ?? 100.0,
                avg_delay_sec: incomingKpis.mean_delay_sec ?? incomingKpis.avg_delay_sec ?? 0.0,
                max_delay_sec: incomingKpis.max_delay_sec ?? 0.0,
                platform_utilization_pct: incomingKpis.platform_utilization_pct ?? 28.5,
                throughput_tph: incomingKpis.throughput_tph ?? 18.0,
                total_actions_taken: incomingKpis.total_actions_taken ?? data.total_actions_taken ?? prev.total_actions_taken ?? 0,
                daily_summary: incomingKpis.daily_summary || data.daily_summary || prev.daily_summary || null
              }));
            }

            // Ingest clock and sim state
            const timeFormatted = incomingKpis?.time_formatted || data.sim_time_formatted || data.time_formatted;
            const timeSec = incomingKpis?.sim_time_sec ?? data.sim_time_sec;
            const statusStr = data.sim_status || data.status;

            if (timeFormatted || statusStr) {
              const incomingSpeed = data.speed_multiplier;
              const hasIncomingSpeed = incomingSpeed !== undefined && incomingSpeed !== null;
              // Ignore delayed WebSocket messages initiated before the latest successful speed change
              const isDelayedWsSpeed = hasIncomingSpeed &&
                latestConfirmedSpeedReqIdRef.current > 0 &&
                (Date.now() - lastConfirmedSpeedTimeRef.current < 2000) &&
                incomingSpeed !== confirmedSpeedRef.current;

              if (hasIncomingSpeed && !isDelayedWsSpeed) {
                confirmedSpeedRef.current = incomingSpeed;
              }
              setSimStatus(prev => {
                let nextRunning;
                let nextPaused;
                if (statusStr) {
                  nextRunning = statusStr === 'RUNNING';
                  nextPaused = statusStr === 'PAUSED';
                } else {
                  nextRunning = data.running ?? prev.running;
                  nextPaused = data.paused ?? prev.paused;
                }

                const resolvedSpeed = isDelayedWsSpeed
                  ? (selectedSpeedRef.current ?? confirmedSpeedRef.current ?? prev.speed_multiplier)
                  : (selectedSpeedRef.current ?? incomingSpeed ?? prev.speed_multiplier);

                return {
                  ...prev,
                  sim_time_formatted: timeFormatted || prev.sim_time_formatted,
                  sim_time_sec: timeSec ?? prev.sim_time_sec,
                  running: nextRunning,
                  paused: nextPaused,
                  current_model: data.dispatcher_model || data.current_model || prev.current_model,
                  current_day: data.calendar_day || data.current_day || prev.current_day,
                  speed_multiplier: resolvedSpeed,
                  active_disruptions: data.active_disruptions || prev.active_disruptions,
                  active_disruptions_data: data.active_disruptions_data || prev.active_disruptions_data || [],
                  active_overrides: data.active_overrides || prev.active_overrides || {},
                  day_completed: Boolean(data.day_completed ?? data.kpis?.day_completed ?? prev.day_completed)
                };
              });
            }

          } catch (err) {
            console.error('WebSocket parse error:', err);
          }
        };

        ws.onclose = () => {
          if (isMounted) {
            reconnectTimeout = setTimeout(connectWS, 2500);
          }
        };
        ws.onerror = () => {
          // Handled by onclose
        };
      } catch {
        if (isMounted) {
          reconnectTimeout = setTimeout(connectWS, 2500);
        }
      }
    };

    connectWS();
    return () => {
      isMounted = false;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) {
        if (ws.readyState === WebSocket.OPEN) {
          try { ws.close(); } catch {}
        } else if (ws.readyState === WebSocket.CONNECTING) {
          ws.onopen = () => {
            try { ws.close(); } catch {}
          };
        }
      }
    };
  }, [sessionId]);

  // 4. Canvas Drawing Loop
  const renderCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle high DPI
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
      canvas.width = width * dpr;
      canvas.height = height * dpr;
    }

    ctx.save();
    ctx.scale(dpr, dpr);

    // Deep modern dark background
    ctx.fillStyle = '#05080f';
    ctx.fillRect(0, 0, width, height);

    // Grid coordinates conversion: SUMO has Y increasing UP, Canvas has Y increasing DOWN.
    // Bounds: [minX, minY, maxX, maxY].
    const bounds = geometry?.bounds || [-0.33, -0.18, 29708.16, 26683.47];
    const [, minY, , maxY] = bounds;
    const toCanvasY = (sumoY) => maxY - sumoY + minY;

    // Apply viewport pan & zoom
    const { scale, offsetX, offsetY } = transformRef.current;
    ctx.save();
    ctx.translate(offsetX, offsetY);
    ctx.scale(scale, scale);

    // 1. Draw Track Lanes (Google Maps Style: Scale-Adaptive & Visible at all Zoom Levels)
    if (geometry && geometry.lanes) {
      const { convEdgeIds, divEdgeIds, platEdgeIds, switchEdgeIds } = selectedStationTopology;
      const isStationSelected = Boolean(selectedStation);

      // Viewport bounds in world coordinates (with 40m margin)
      const vpMinX = -offsetX / scale - 40;
      const vpMaxX = (width - offsetX) / scale + 40;
      const vpMinY = maxY + minY - (height - offsetY) / scale - 40;
      const vpMaxY = maxY + minY - (-offsetY) / scale + 40;

      // Scale-adaptive line width for overview/medium zoom (guarantees zero dropouts across all zoom levels)
      const minScreenPx = scale < 0.12 ? 1.6 : (scale < 0.5 ? 1.8 : 2.2);
      const wNetwork = Math.max(minScreenPx / scale, 1.0);
      const wPlatform = Math.max((minScreenPx * 1.1) / scale, 1.2);
      const wSpur = Math.max((minScreenPx * 1.0) / scale, 1.0);
      const wPocket = Math.max((minScreenPx * 1.0) / scale, 1.0);
      const wYard = Math.max((minScreenPx * 0.75) / scale, 0.8);
      const wSwitch = Math.max((minScreenPx * 0.85) / scale, 0.8);

      // Fast parallel rail offset calculation for standard gauge (1.435m)
      const getRailOffsets = (pts, gauge = 1.435) => {
        const halfG = gauge / 2;
        const left = [];
        const right = [];
        const n = pts.length;
        for (let k = 0; k < n; k++) {
          let nx = 0, ny = 0;
          if (k === 0) {
            const dx = pts[1][0] - pts[0][0];
            const dy = pts[1][1] - pts[0][1];
            const L = Math.hypot(dx, dy) || 1;
            nx = -dy / L;
            ny = dx / L;
          } else if (k === n - 1) {
            const dx = pts[n - 1][0] - pts[n - 2][0];
            const dy = pts[n - 1][1] - pts[n - 2][1];
            const L = Math.hypot(dx, dy) || 1;
            nx = -dy / L;
            ny = dx / L;
          } else {
            const dx1 = pts[k][0] - pts[k - 1][0];
            const dy1 = pts[k][1] - pts[k - 1][1];
            const L1 = Math.hypot(dx1, dy1) || 1;
            const dx2 = pts[k + 1][0] - pts[k][0];
            const dy2 = pts[k + 1][1] - pts[k][1];
            const L2 = Math.hypot(dx2, dy2) || 1;
            nx = (-dy1 / L1 + -dy2 / L2) / 2;
            ny = (dx1 / L1 + dx2 / L2) / 2;
            const L = Math.hypot(nx, ny) || 1;
            nx /= L;
            ny /= L;
          }
          left.push([pts[k][0] + nx * halfG, pts[k][1] + ny * halfG]);
          right.push([pts[k][0] - nx * halfG, pts[k][1] - ny * halfG]);
        }
        return { left, right };
      };

      for (let i = 0; i < geometry.lanes.length; i++) {
        const lane = geometry.lanes[i];
        const coords = lane.coordinates || lane.shape;
        if (!coords || coords.length < 2) continue;

        // Filter out any internal loopback/hairpin turns generated by netconvert
        if (lane.is_internal && coords.length >= 2) {
          const p0 = coords[0];
          const p1 = coords[1];
          const pN1 = coords[coords.length - 2];
          const pN = coords[coords.length - 1];
          const a0 = Math.atan2(p1[1] - p0[1], p1[0] - p0[0]);
          const aN = Math.atan2(pN[1] - pN1[1], pN[1] - pN1[0]);
          let diff = Math.abs(a0 - aN);
          if (diff > Math.PI) diff = 2 * Math.PI - diff;
          if (diff > (42 * Math.PI) / 180) continue;
        }

        // Viewport bounding box culling
        let lMinX = coords[0][0], lMaxX = coords[0][0];
        let lMinY = coords[0][1], lMaxY = coords[0][1];
        for (let k = 1; k < coords.length; k++) {
          if (coords[k][0] < lMinX) lMinX = coords[k][0];
          if (coords[k][0] > lMaxX) lMaxX = coords[k][0];
          if (coords[k][1] < lMinY) lMinY = coords[k][1];
          if (coords[k][1] > lMaxY) lMaxY = coords[k][1];
        }
        if (lMaxX < vpMinX || lMinX > vpMaxX || lMaxY < vpMinY || lMinY > vpMaxY) {
          continue; // Outside viewport
        }

        const cat = lane.category || 'connector';
        const isHighSpeed = cat === 'high_speed';
        const isRegional = cat === 'regional';
        const isSpur = cat === 'spur' || (lane.edge_id && lane.edge_id.includes('spur'));
        const isPlatform = cat === 'platform' || platEdgeIds.has(lane.edge_id) || (lane.edge_id && lane.edge_id.includes('plat'));
        const isSwitch = cat === 'switch' || lane.is_internal || (lane.edge_id && (lane.edge_id.startsWith(':') || lane.edge_id.includes('Throat')));
        const isCrossover = cat === 'crossover' || (lane.edge_id && lane.edge_id.includes('xov'));
        const isPocket = cat === 'pocket' || (lane.edge_id && (lane.edge_id.includes('pocket') || lane.edge_id.includes('tail')));
        const isPassingLoop = cat === 'passing_loop' || (lane.edge_id && (lane.edge_id.includes('siding') || lane.edge_id.includes('loop')));
        const isExpressThru = cat === 'express_thru' || (lane.edge_id && lane.edge_id.includes('thru'));
        const isYard = cat === 'yard' || (lane.edge_id && lane.edge_id.includes('yard'));

        const isSelectedConv = convEdgeIds.has(lane.edge_id);
        const isSelectedDiv = divEdgeIds.has(lane.edge_id);
        const isSelectedSwitch = switchEdgeIds ? switchEdgeIds.has(lane.edge_id) : false;

        // If a station is selected, check if this lane belongs to the station topology
        const isConnectedToStation = isPlatform || isSelectedConv || isSelectedDiv || isSelectedSwitch || isCrossover || isPocket;

        // Determine feature color theme
        let featureColor = '#0284c7';
        if (isPlatform) featureColor = '#f59e0b';
        else if (isCrossover) featureColor = '#f59e0b';
        else if (isExpressThru) featureColor = '#38bdf8';
        else if (isPassingLoop) featureColor = '#14b8a6';
        else if (isPocket) featureColor = '#10b981';
        else if (isSpur) featureColor = '#8b5cf6';
        else if (isSwitch || isSelectedSwitch) featureColor = '#818cf8';
        else if (isYard) featureColor = '#64748b';
        else if (isHighSpeed) featureColor = '#00f0ff';
        else if (isRegional) featureColor = '#f59e0b';

        if (isStationSelected && !isConnectedToStation) {
          featureColor = 'rgba(71, 85, 105, 0.25)';
        }

        // =====================================================================
        // MODE A: DEEP MICROSCOPIC RAILWAY GEOMETRY (scale >= 1.4 up to 60.0)
        // Renders authentic dual parallel steel rails, cross-ties (sleepers), 
        // ballast bed, and check rails (guard rails) at diamond switches!
        // =====================================================================
        if (scale >= 1.4) {
          // 1. Ballast Bed (Continuous physical tracks only, never internal switch lines)
          if (!lane.is_internal) {
            ctx.beginPath();
            ctx.moveTo(coords[0][0], toCanvasY(coords[0][1]));
            for (let j = 1; j < coords.length; j++) {
              ctx.lineTo(coords[j][0], toCanvasY(coords[j][1]));
            }
            // Stroke shoulder border FIRST
            ctx.strokeStyle = '#1e293b';
            ctx.lineWidth = 3.6;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.stroke();

            // Stroke dark inner ballast SECOND
            ctx.strokeStyle = '#090e17';
            ctx.lineWidth = 2.8;
            ctx.stroke();
          }

          // 2. Cross-Ties (Sleepers) when scale >= 2.2 (Physical continuous tracks only)
          if (scale >= 2.2 && !lane.is_internal) {
            ctx.strokeStyle = '#334155'; // Concrete / hardwood railway tie
            ctx.lineWidth = Math.max(0.24, 0.8 / scale);
            ctx.beginPath();
            const step = scale >= 8.0 ? 0.75 : (scale >= 4.0 ? 1.2 : 1.8);
            for (let j = 0; j < coords.length - 1; j++) {
              const x0 = coords[j][0], y0 = coords[j][1];
              const x1 = coords[j + 1][0], y1 = coords[j + 1][1];
              const dx = x1 - x0, dy = y1 - y0;
              const segL = Math.hypot(dx, dy);
              if (segL < 0.1) continue;
              const ux = dx / segL, uy = dy / segL;
              const nx = -uy, ny = ux;
              for (let s = 0.4; s < segL; s += step) {
                const cx = x0 + ux * s;
                const cy = y0 + uy * s;
                ctx.moveTo(cx + nx * 1.25, toCanvasY(cy + ny * 1.25));
                ctx.lineTo(cx - nx * 1.25, toCanvasY(cy - ny * 1.25));
              }
            }
            ctx.stroke();
          }

          // 3. Dual Parallel Steel Rails (1.435m Standard Gauge)
          // For internal 2-point chords: draw as a clean steel turnout switch connector
          const isInternalChord = lane.is_internal && coords.length === 2;
          if (!isInternalChord) {
            const { left, right } = getRailOffsets(coords, 1.435);

            // Left Rail
            ctx.beginPath();
            ctx.moveTo(left[0][0], toCanvasY(left[0][1]));
            for (let j = 1; j < left.length; j++) {
              ctx.lineTo(left[j][0], toCanvasY(left[j][1]));
            }
            ctx.strokeStyle = '#475569';
            ctx.lineWidth = Math.max(0.14, 1.2 / scale);
            ctx.stroke();
            ctx.strokeStyle = '#f8fafc'; // Gleaming silver railhead
            ctx.lineWidth = Math.max(0.06, 0.6 / scale);
            ctx.stroke();

            // Right Rail
            ctx.beginPath();
            ctx.moveTo(right[0][0], toCanvasY(right[0][1]));
            for (let j = 1; j < right.length; j++) {
              ctx.lineTo(right[j][0], toCanvasY(right[j][1]));
            }
            ctx.strokeStyle = '#475569';
            ctx.lineWidth = Math.max(0.14, 1.2 / scale);
            ctx.stroke();
            ctx.strokeStyle = '#f8fafc'; // Gleaming silver railhead
            ctx.lineWidth = Math.max(0.06, 0.6 / scale);
            ctx.stroke();
          } else {
            // Clean single switch blade line connecting turnouts
            ctx.beginPath();
            ctx.moveTo(coords[0][0], toCanvasY(coords[0][1]));
            ctx.lineTo(coords[1][0], toCanvasY(coords[1][1]));
            ctx.strokeStyle = '#94a3b8';
            ctx.lineWidth = Math.max(0.2, 1.0 / scale);
            ctx.stroke();
          }

          // 4. Subtle Centerline Color-Coded Functional Glow
          const shouldShowCenterline = isPlatform || isCrossover || isPocket || isSpur ||
            (isPassingLoop && activeFeatureLayer === 'loops') ||
            (isExpressThru && activeFeatureLayer === 'loops') ||
            (isSelectedSwitch || (isSwitch && isStationSelected && isConnectedToStation));

          if (shouldShowCenterline) {
            ctx.beginPath();
            ctx.moveTo(coords[0][0], toCanvasY(coords[0][1]));
            for (let j = 1; j < coords.length; j++) {
              ctx.lineTo(coords[j][0], toCanvasY(coords[j][1]));
            }
            ctx.strokeStyle = featureColor;
            ctx.lineWidth = Math.max(0.2, 0.9 / scale);
            ctx.stroke();
          }

          // 5. Crossover Frogs & Diamond Intersections at Deep Zoom
          if (isCrossover && coords.length >= 2) {
            const pStart = coords[0];
            const pEnd = coords[coords.length - 1];
            const dSize = Math.max(1.8, 3.5 / scale);

            // Frog Switch Plates
            ctx.save();
            ctx.translate(pStart[0], toCanvasY(pStart[1]));
            ctx.rotate(Math.PI / 4);
            ctx.fillStyle = '#fbbf24';
            ctx.fillRect(-dSize / 2, -dSize / 2, dSize, dSize);
            ctx.restore();

            ctx.save();
            ctx.translate(pEnd[0], toCanvasY(pEnd[1]));
            ctx.rotate(Math.PI / 4);
            ctx.fillStyle = '#fbbf24';
            ctx.fillRect(-dSize / 2, -dSize / 2, dSize, dSize);
            ctx.restore();
          }

          // 6. Platform Track Labels at Deep Zoom (Only if labels enabled)
          if (showOverlayLabels && isPlatform && coords.length >= 2) {
            const midIdx = Math.floor(coords.length / 2);
            const mx = coords[midIdx][0];
            const my = toCanvasY(coords[midIdx][1]);
            const platLabel = lane.edge_id.replace(/^.*plat_/, 'Track ').replace(/_fw.*/, ' [FW]').replace(/_bw.*/, ' [BW]');
            ctx.save();
            ctx.font = `700 ${Math.min(9.5 / scale, 12)}px Inter, sans-serif`;
            ctx.fillStyle = '#fbbf24';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            ctx.fillText(platLabel, mx, my - Math.min(2.5, 3.5 / scale));
            ctx.restore();
          }
        } 
        // =====================================================================
        // MODE B: OVERVIEW & MEDIUM ZOOM (scale < 1.4)
        // High-contrast scale-adaptive lines with guaranteed minimum visibility
        // =====================================================================
        else {
          ctx.beginPath();
          ctx.moveTo(coords[0][0], toCanvasY(coords[0][1]));
          for (let j = 1; j < coords.length; j++) {
            ctx.lineTo(coords[j][0], toCanvasY(coords[j][1]));
          }

          if (isPlatform) {
            ctx.strokeStyle = '#020617';
            ctx.lineWidth = wPlatform * 1.35;
            ctx.stroke();

            ctx.strokeStyle = '#f59e0b';
            ctx.lineWidth = wPlatform;
            ctx.stroke();

            ctx.strokeStyle = '#fef08a';
            ctx.lineWidth = wPlatform * 0.45;
            ctx.stroke();
          } else if (isCrossover) {
            const isHighlighted = activeFeatureLayer === 'crossovers' || selectedFeature?.type === 'crossover';
            ctx.strokeStyle = isHighlighted ? '#f43f5e' : (isStationSelected ? 'rgba(245, 158, 11, 0.4)' : '#f59e0b');
            ctx.lineWidth = wNetwork * (isHighlighted ? 1.35 : 1.15);
            ctx.stroke();

            ctx.strokeStyle = '#fef08a';
            ctx.lineWidth = Math.max(0.6 / scale, wNetwork * 0.4);
            ctx.stroke();

            if (scale >= 0.1 && coords.length >= 2) {
              const pStart = coords[0];
              const pEnd = coords[coords.length - 1];
              const diamondSize = Math.max(2.5 / scale, 3.5);

              ctx.save();
              ctx.translate(pStart[0], toCanvasY(pStart[1]));
              ctx.rotate(Math.PI / 4);
              ctx.fillStyle = '#fbbf24';
              ctx.fillRect(-diamondSize / 2, -diamondSize / 2, diamondSize, diamondSize);
              ctx.restore();

              ctx.save();
              ctx.translate(pEnd[0], toCanvasY(pEnd[1]));
              ctx.rotate(Math.PI / 4);
              ctx.fillStyle = '#fbbf24';
              ctx.fillRect(-diamondSize / 2, -diamondSize / 2, diamondSize, diamondSize);
              ctx.restore();
            }
          } else if (isExpressThru) {
            const isHighlighted = activeFeatureLayer === 'loops' || selectedFeature?.type === 'express_thru';
            ctx.strokeStyle = isHighlighted ? '#38bdf8' : (isStationSelected && !isConnectedToStation ? 'rgba(2, 132, 199, 0.3)' : '#0284c7');
            ctx.lineWidth = wNetwork * 1.2;
            ctx.stroke();

            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = Math.max(0.7 / scale, wNetwork * 0.45);
            ctx.stroke();
          } else if (isPassingLoop) {
            const isHighlighted = activeFeatureLayer === 'loops' || selectedFeature?.type === 'passing_loop';
            ctx.strokeStyle = isHighlighted ? '#10b981' : (isStationSelected && !isConnectedToStation ? 'rgba(20, 184, 166, 0.35)' : '#14b8a6');
            ctx.lineWidth = wNetwork * 1.15;
            ctx.stroke();

            ctx.strokeStyle = '#99f6e4';
            ctx.lineWidth = Math.max(0.6 / scale, wNetwork * 0.4);
            ctx.stroke();
          } else if (isPocket) {
            // Reversal pocket and tail tracks directly feeding buffer stops
            const isHighlighted = activeFeatureLayer === 'loops' || selectedFeature?.type === 'passing_loop';
            ctx.strokeStyle = isHighlighted ? '#10b981' : (isStationSelected && !isConnectedToStation ? 'rgba(16, 185, 129, 0.35)' : '#10b981');
            ctx.lineWidth = wPocket;
            ctx.stroke();

            ctx.strokeStyle = '#a7f3d0';
            ctx.lineWidth = Math.max(0.5 / scale, wPocket * 0.35);
            ctx.stroke();
          } else if (isSpur) {
            // Dedicated electrified maintenance depot branch spurs (linking cities to depots)
            ctx.strokeStyle = isStationSelected && !isConnectedToStation ? 'rgba(139, 92, 246, 0.3)' : '#8b5cf6';
            ctx.lineWidth = wSpur;
            ctx.stroke();

            ctx.strokeStyle = '#c4b5fd';
            ctx.lineWidth = Math.max(0.6 / scale, wSpur * 0.4);
            ctx.stroke();
          } else if (isYard) {
            // Stabling, layover and freight classification yard tracks
            ctx.strokeStyle = isStationSelected && !isConnectedToStation ? 'rgba(100, 116, 139, 0.25)' : '#64748b';
            ctx.lineWidth = wYard;
            ctx.stroke();
          } else if (isSelectedSwitch || (isSwitch && isStationSelected && isConnectedToStation)) {
            ctx.strokeStyle = '#818cf8';
            ctx.lineWidth = wSwitch;
            ctx.stroke();
          } else if (isSwitch) {
            ctx.strokeStyle = isStationSelected ? 'rgba(129, 140, 248, 0.22)' : '#818cf8';
            ctx.lineWidth = wSwitch;
            ctx.stroke();
          } else if (isHighSpeed) {
            ctx.strokeStyle = isStationSelected && !isConnectedToStation ? 'rgba(14, 116, 144, 0.22)' : '#0284c7';
            ctx.lineWidth = wNetwork;
            ctx.stroke();

            if (!isStationSelected || isConnectedToStation) {
              ctx.strokeStyle = '#00f0ff';
              ctx.lineWidth = Math.max(0.6 / scale, wNetwork * 0.45);
              ctx.stroke();
            }
          } else if (isRegional) {
            ctx.strokeStyle = isStationSelected && !isConnectedToStation ? 'rgba(217, 119, 6, 0.22)' : '#d97706';
            ctx.lineWidth = wNetwork;
            ctx.stroke();

            if (!isStationSelected || isConnectedToStation) {
              ctx.strokeStyle = '#fbbf24';
              ctx.lineWidth = Math.max(0.6 / scale, wNetwork * 0.4);
              ctx.stroke();
            }
          } else {
            ctx.strokeStyle = isStationSelected && !isConnectedToStation ? 'rgba(30, 41, 59, 0.22)' : '#0284c7';
            ctx.lineWidth = wNetwork;
            ctx.stroke();
          }
        }

        // Active Station Converging Track (Inbound Flow): Animated Neon Cyan pulse towards station
        if (isSelectedConv) {
          ctx.save();
          ctx.beginPath();
          ctx.moveTo(coords[0][0], toCanvasY(coords[0][1]));
          for (let j = 1; j < coords.length; j++) {
            ctx.lineTo(coords[j][0], toCanvasY(coords[j][1]));
          }
          ctx.strokeStyle = '#00f0ff';
          ctx.lineWidth = Math.min(1.8, 2.2 / scale);
          ctx.setLineDash([Math.min(8, 12 / scale), Math.min(12, 16 / scale)]);
          ctx.lineDashOffset = -(Date.now() / 30) % (28 / scale);
          ctx.shadowColor = '#00f0ff';
          ctx.shadowBlur = 10;
          ctx.stroke();

          // Outer endpoint tag if zoomed in
          if (scale >= 0.25 && coords.length >= 2) {
            const startPt = coords[0];
            ctx.font = `700 ${Math.min(8.5 / scale, 11)}px Inter, sans-serif`;
            ctx.fillStyle = '#22d3ee';
            ctx.textAlign = 'center';
            ctx.fillText('↗ INBOUND', startPt[0], toCanvasY(startPt[1]) - Math.min(4, 5 / scale));
          }
          ctx.restore();
        }

        // Active Station Diverging Track (Outbound Flow): Animated Emerald pulse away from station
        if (isSelectedDiv) {
          ctx.save();
          ctx.beginPath();
          ctx.moveTo(coords[0][0], toCanvasY(coords[0][1]));
          for (let j = 1; j < coords.length; j++) {
            ctx.lineTo(coords[j][0], toCanvasY(coords[j][1]));
          }
          ctx.strokeStyle = '#10b981';
          ctx.lineWidth = Math.min(1.8, 2.2 / scale);
          ctx.setLineDash([Math.min(8, 12 / scale), Math.min(12, 16 / scale)]);
          ctx.lineDashOffset = (Date.now() / 30) % (28 / scale);
          ctx.shadowColor = '#10b981';
          ctx.shadowBlur = 10;
          ctx.stroke();

          // Outer endpoint tag if zoomed in
          if (scale >= 0.25 && coords.length >= 2) {
            const endPt = coords[coords.length - 1];
            ctx.font = `700 ${Math.min(8.5 / scale, 11)}px Inter, sans-serif`;
            ctx.fillStyle = '#34d399';
            ctx.textAlign = 'center';
            ctx.fillText('↘ OUTBOUND', endPt[0], toCanvasY(endPt[1]) - Math.min(4, 5 / scale));
          }
          ctx.restore();
        }
      }
    }

    // 2. Draw Terminating Points & Buffer Stops (Hydraulic Bumper Blocks)
    if (geometry && geometry.buffer_stops) {
      for (const buf of geometry.buffer_stops) {
        const bx = buf.x;
        const by = toCanvasY(buf.y);
        const angleRad = -((buf.angle_deg || 0) * Math.PI) / 180;
        const isBufSelected = selectedFeature?.id === buf.id || activeFeatureLayer === 'buffer_stops';

        ctx.save();
        ctx.translate(bx, by);
        ctx.rotate(angleRad);

        // Bumper block crossbar dimensions (physical 2.6m width spanning 1.435m track gauge)
        const barWidth = Math.max(2.6, 10 / scale);
        const barThickness = Math.max(0.7, 3.5 / scale);

        // Terminating stop posts
        ctx.fillStyle = '#1e293b';
        ctx.fillRect(-barThickness, -barWidth / 2, barThickness, barWidth);

        // Red/white striped hydraulic bumper crossbar
        ctx.fillStyle = '#ef4444';
        ctx.fillRect(-barThickness / 2, -barWidth / 2, barThickness, barWidth);

        // White hazard diagonal stripes
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = Math.max(1.4 / scale, 1.8);
        ctx.beginPath();
        ctx.moveTo(-barThickness / 2, -barWidth / 4);
        ctx.lineTo(barThickness / 2, -barWidth / 2);
        ctx.moveTo(-barThickness / 2, barWidth / 4);
        ctx.lineTo(barThickness / 2, 0);
        ctx.stroke();

        // Twin Red Warning Marker Lights
        const lightRadius = Math.max(2 / scale, 2.8);
        ctx.beginPath();
        ctx.arc(0, -barWidth / 2 + lightRadius + 1, lightRadius, 0, Math.PI * 2);
        ctx.arc(0, barWidth / 2 - lightRadius - 1, lightRadius, 0, Math.PI * 2);
        ctx.fillStyle = '#ef4444';
        ctx.shadowColor = '#ef4444';
        ctx.shadowBlur = isBufSelected ? 16 : 8;
        ctx.fill();

        ctx.restore();

        // Pulsing selection radar ring if buffer stop selected
        if (isBufSelected) {
          const bPulse = (Math.sin(Date.now() / 150) + 1) / 2;
          ctx.save();
          ctx.beginPath();
          ctx.arc(bx, by, (16 / scale) * (1.2 + bPulse * 0.4), 0, Math.PI * 2);
          ctx.strokeStyle = '#ef4444';
          ctx.lineWidth = 2.5 / scale;
          ctx.shadowColor = '#ef4444';
          ctx.shadowBlur = 14;
          ctx.stroke();
          ctx.restore();
        }

        // Buffer stop label if zoomed in (scale >= 0.15) or buffer layer active
        if ((showOverlayLabels && scale >= 0.15) || isBufSelected) {
          ctx.save();
          const fontSize = Math.min(9.5 / scale, 12);
          ctx.font = `700 ${fontSize}px Inter, sans-serif`;
          ctx.fillStyle = '#f87171';
          ctx.textAlign = 'center';
          ctx.fillText(`🛑 ${buf.name || 'Buffer Stop'}`, bx, by - Math.min(10 / scale, 15));
          ctx.restore();
        }
      }
    }

    // 3. Draw Railway Signals (Signal Target Plates & Luminous Lenses)
    if (showSignalHeads && geometry && geometry.signals && (scale >= 0.08 || activeFeatureLayer === 'signals')) {
      for (const sig of geometry.signals) {
        const sx = sig.x;
        const sy = toCanvasY(sig.y);
        const isSigSelected = selectedFeature?.id === sig.id;

        // Signal target plate (physical ~0.7m x 1.8m head with min screen size)
        const sigW = Math.max(0.7, 4.5 / scale);
        const sigH = Math.max(1.8, 11 / scale);

        ctx.save();
        ctx.fillStyle = '#090d16';
        ctx.strokeStyle = isSigSelected ? '#00f0ff' : 'rgba(255, 255, 255, 0.35)';
        ctx.lineWidth = Math.max(0.8 / scale, 1);
        ctx.beginPath();
        ctx.roundRect(sx - sigW / 2, sy - sigH / 2, sigW, sigH, 2 / scale);
        ctx.fill();
        ctx.stroke();

        // Luminous Signal Aspect Lens (Default Clear Green #10b981)
        const lensR = Math.max(1.6 / scale, 2.0);
        ctx.beginPath();
        ctx.arc(sx, sy + sigH / 4, lensR, 0, Math.PI * 2);
        ctx.fillStyle = '#10b981';
        ctx.shadowColor = '#10b981';
        ctx.shadowBlur = 8;
        ctx.fill();

        ctx.restore();
      }
    }

    // 4. Draw High-Level Track Feature Markers (Only when labels enabled or layer active, to prevent crowding)
    if (showOverlayLabels && geometry && geometry.track_features && scale < 0.25) {
      for (const feat of geometry.track_features) {
        const fx = feat.x;
        const fy = toCanvasY(feat.y);
        const isFeatSelected = selectedFeature?.id === feat.id;

        if (feat.type === 'crossover' && (activeFeatureLayer === 'crossovers' || isFeatSelected)) {
          // High-Speed Diamond Crossover Zone Marker
          ctx.save();
          const pillW = 160 / scale;
          const pillH = 18 / scale;
          ctx.fillStyle = isFeatSelected ? 'rgba(245, 158, 11, 0.95)' : 'rgba(15, 23, 42, 0.88)';
          ctx.strokeStyle = '#f59e0b';
          ctx.lineWidth = 1.5 / scale;
          ctx.beginPath();
          ctx.roundRect(fx - pillW / 2, fy - pillH / 2, pillW, pillH, 4 / scale);
          ctx.fill();
          ctx.stroke();

          ctx.font = `700 ${10 / scale}px Inter, sans-serif`;
          ctx.fillStyle = isFeatSelected ? '#020617' : '#fbbf24';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(`🔀 Crossover (${feat.speed_kmh} km/h)`, fx, fy);
          ctx.restore();
        } else if ((feat.type === 'express_thru' || feat.type === 'passing_loop') && (activeFeatureLayer === 'loops' || isFeatSelected)) {
          // Dynamic Passing Loop / Bypass Marker
          ctx.save();
          const pillW = 140 / scale;
          const pillH = 18 / scale;
          ctx.fillStyle = isFeatSelected ? 'rgba(20, 184, 166, 0.95)' : 'rgba(15, 23, 42, 0.88)';
          ctx.strokeStyle = '#14b8a6';
          ctx.lineWidth = 1.5 / scale;
          ctx.beginPath();
          ctx.roundRect(fx - pillW / 2, fy - pillH / 2, pillW, pillH, 4 / scale);
          ctx.fill();
          ctx.stroke();

          ctx.font = `700 ${10 / scale}px Inter, sans-serif`;
          ctx.fillStyle = isFeatSelected ? '#020617' : '#2dd4bf';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(feat.type === 'express_thru' ? `⚡ Express Thru` : `🔄 Passing Loop`, fx, fy);
          ctx.restore();
        }
      }
    }

    const activeDisruptionsData = simStatus.active_disruptions_data || [];
    const activeOverrides = simStatus.active_overrides || {};

    // 2. Draw Stations
    if (geometry && geometry.stations) {
      for (const st of geometry.stations) {
        const sx = st.x;
        const sy = toCanvasY(st.y);
        const isCity = st.station_name && st.station_name.startsWith('City');
        const hubRadius = (isCity ? 14 : 9) / scale;
        const innerRadius = (isCity ? 7 : 4.5) / scale;

        // Check if this station is selected for microscopic inspection
        const isSelectedSt = selectedStation && (selectedStation.station_name === st.station_name);

        // Check if this station is impacted by platform blockage, breakdown, or compound failure
        const isDisruptedStation = activeDisruptionsData.some(d => {
          if (d.mode === 'platform_blockage' || d.mode === 'compound_failure') {
            if (d.station_id === st.station_name) return true;
            if (d.platform_id && (d.platform_id.includes(st.station_name) || st.station_name.includes(d.platform_id))) return true;
            if (d.station_name && st.display_name && (d.station_name.toLowerCase() === st.display_name.toLowerCase())) return true;
            if (st.platforms && st.platforms.some(p => p.platform_id === d.platform_id || p.lane === d.platform_id)) return true;
          }
          return false;
        });

        const isSurgeStation = activeDisruptionsData.some(d => 
          d.mode === 'fleet_surge' && (!d.station_id || d.station_id === st.station_name || d.station_name === st.display_name)
        );

        // If selected station: draw spinning high-tech focus brackets & cyan radar halo
        if (isSelectedSt) {
          const sPulse = (Math.sin(Date.now() / 180) + 1) / 2;
          ctx.save();
          ctx.beginPath();
          ctx.arc(sx, sy, hubRadius * (2.1 + sPulse * 0.4), 0, Math.PI * 2);
          ctx.strokeStyle = '#00f0ff';
          ctx.lineWidth = 3 / scale;
          ctx.shadowColor = '#00f0ff';
          ctx.shadowBlur = 18;
          ctx.setLineDash([10 / scale, 8 / scale]);
          ctx.lineDashOffset = -(Date.now() / 45) % (18 / scale);
          ctx.stroke();
          ctx.restore();
        }

        // If fleet surge active: draw pulsating amber boarding wave
        if (isSurgeStation && !isDisruptedStation) {
          const sPulse = (Math.sin(Date.now() / 160) + 1) / 2;
          ctx.beginPath();
          ctx.arc(sx, sy, hubRadius * (1.8 + sPulse * 0.8), 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(245, 158, 11, ${0.8 + sPulse * 0.2})`;
          ctx.lineWidth = 3 / scale;
          ctx.stroke();
          ctx.fillStyle = 'rgba(245, 158, 11, 0.2)';
          ctx.fill();
        }

        // If disrupted station: draw pulsating danger shockwave radar rings
        if (isDisruptedStation) {
          const pulse = (Math.sin(Date.now() / 150) + 1) / 2;
          const shockRadius = hubRadius * (1.8 + pulse * 1.5);
          ctx.beginPath();
          ctx.arc(sx, sy, shockRadius, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(239, 68, 68, ${0.7 + pulse * 0.3})`;
          ctx.lineWidth = 3.5 / scale;
          ctx.stroke();
          ctx.fillStyle = 'rgba(239, 68, 68, 0.22)';
          ctx.fill();

          // Expanding radar pulse ring
          const ringProgress = (Date.now() % 1200) / 1200;
          ctx.beginPath();
          ctx.arc(sx, sy, hubRadius * (1.2 + ringProgress * 2.2), 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(239, 68, 68, ${1 - ringProgress})`;
          ctx.lineWidth = 2 / scale;
          ctx.stroke();

          // Highlight blocked platform tracks directly with glowing hazard stripes
          if (st.platforms) {
            for (const plat of st.platforms) {
              const isPlatTargeted = activeDisruptionsData.some(d => 
                (d.mode === 'platform_blockage' || d.mode === 'compound_failure') &&
                (d.platform_id === plat.platform_id || d.platform_id === plat.lane || !d.platform_id)
              );
              if (isPlatTargeted && plat.coordinates && plat.coordinates.length >= 2) {
                ctx.save();
                ctx.beginPath();
                ctx.moveTo(plat.coordinates[0][0], toCanvasY(plat.coordinates[0][1]));
                for (let pi = 1; pi < plat.coordinates.length; pi++) {
                  ctx.lineTo(plat.coordinates[pi][0], toCanvasY(plat.coordinates[pi][1]));
                }
                ctx.strokeStyle = '#ef4444';
                ctx.lineWidth = 14 / scale;
                ctx.shadowColor = '#ef4444';
                ctx.shadowBlur = 18;
                ctx.stroke();
                ctx.strokeStyle = '#fef08a';
                ctx.lineWidth = 4 / scale;
                ctx.setLineDash([14 / scale, 8 / scale]);
                ctx.lineDashOffset = -(Date.now() / 40) % 22;
                ctx.stroke();
                ctx.restore();
              }
            }
          }
        }

        // When zoomed in to inspect tracks (scale >= 0.22), fade out the giant hub disc so it does not obscure individual tracks!
        const discAlpha = Math.max(0, 1 - (scale - 0.16) / 0.16);

        if (discAlpha > 0) {
          ctx.save();
          ctx.globalAlpha = discAlpha;

          // Outer Glow Halo
          ctx.beginPath();
          ctx.arc(sx, sy, hubRadius * 1.6, 0, Math.PI * 2);
          ctx.fillStyle = isDisruptedStation 
            ? 'rgba(239, 68, 68, 0.3)' 
            : (isCity ? 'rgba(0, 240, 255, 0.12)' : 'rgba(56, 189, 248, 0.08)');
          ctx.fill();

          // Hub Disc
          ctx.beginPath();
          ctx.arc(sx, sy, hubRadius, 0, Math.PI * 2);
          ctx.fillStyle = isDisruptedStation 
            ? 'rgba(153, 27, 27, 0.95)' 
            : (isCity ? 'rgba(12, 74, 110, 0.95)' : 'rgba(30, 58, 138, 0.9)');
          ctx.fill();
          ctx.strokeStyle = isDisruptedStation ? '#ef4444' : (isCity ? '#00f0ff' : '#38bdf8');
          ctx.lineWidth = (isDisruptedStation ? 3.5 : 2.5) / scale;
          ctx.stroke();

          // Core dot
          ctx.beginPath();
          ctx.arc(sx, sy, innerRadius, 0, Math.PI * 2);
          ctx.fillStyle = '#ffffff';
          ctx.fill();

          ctx.restore();
        }

        // Station Name Pill Badge (Only when labels enabled, or when this station is selected/disrupted)
        if (showOverlayLabels || isSelectedSt || isDisruptedStation) {
          const name = st.display_name || st.station_name || 'Station';
          const fontSize = Math.min((isCity ? 11 : 9.5) / scale, 13);
          ctx.font = `600 ${fontSize}px Inter, system-ui, sans-serif`;
          const textMetrics = ctx.measureText(name);
          const textWidth = textMetrics.width;
          const padX = 6 / scale;
          const padY = 3 / scale;
          const badgeH = fontSize + padY * 2;
          const badgeW = textWidth + padX * 2;
          const badgeX = sx - badgeW / 2;
          const badgeY = scale >= 0.22 
            ? sy - Math.max(hubRadius * 1.6, 65 / scale) 
            : sy - hubRadius * 1.6 - badgeH - (4 / scale);

          // Badge background
          ctx.fillStyle = 'rgba(6, 11, 24, 0.9)';
          ctx.beginPath();
          ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 4 / scale);
          ctx.fill();
          ctx.strokeStyle = isDisruptedStation 
            ? '#ef4444' 
            : (isCity ? 'rgba(0, 240, 255, 0.6)' : 'rgba(56, 189, 248, 0.4)');
          ctx.lineWidth = 1 / scale;
          ctx.stroke();

          // Badge text
          ctx.fillStyle = '#f8fafc';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(name, sx, badgeY + badgeH / 2);
        }

        // Danger Warning Tag if Disrupted
        if (isDisruptedStation) {
          const dLabel = '⛔ PLATFORM TRACK BLOCKED';
          const dFontSize = (isCity ? 10.5 : 9) / scale;
          ctx.font = `800 ${dFontSize}px Inter, system-ui, sans-serif`;
          const dMetrics = ctx.measureText(dLabel);
          const dPadX = 7 / scale;
          const dPadY = 3.5 / scale;
          const dBadgeH = dFontSize + dPadY * 2;
          const dBadgeW = dMetrics.width + dPadX * 2;
          const dBadgeX = sx - dBadgeW / 2;
          const dBadgeY = badgeY - dBadgeH - (5 / scale);

          ctx.fillStyle = 'rgba(185, 28, 28, 0.96)';
          ctx.beginPath();
          ctx.roundRect(dBadgeX, dBadgeY, dBadgeW, dBadgeH, 4 / scale);
          ctx.fill();
          ctx.strokeStyle = '#fca5a5';
          ctx.lineWidth = 1.5 / scale;
          ctx.stroke();

          ctx.fillStyle = '#ffffff';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(dLabel, sx, dBadgeY + dBadgeH / 2);
        }
      }
    }

    // 3. Draw Active Trains
    for (const train of filteredTrains) {
      const tx = train.x;
      const ty = toCanvasY(train.y);
      const angleRad = ((train.angle ?? 90) - 90) * (Math.PI / 180);

      const isSelected = selectedTrain && (selectedTrain.id === train.id);
      const isHighSpeed = train.category === 'HighSpeed';
      const isFreight = train.category === 'Freight';
      const isDelayed = (train.delay_sec || 0) > 30;

      // Check if train is specifically disrupted (breakdown / mechanical stall)
      const isDisruptedTrain = activeDisruptionsData.some(d => 
        (d.mode === 'train_delay' || d.mode === 'compound_failure') && 
        (d.vehicle_id === train.id || train.is_stalled)
      );

      // Check if train has an active operator override
      const activeOverride = activeOverrides[train.id];

      // Physical train dimensions in meters: 3.0m - 3.4m wide, 85m - 240m long, with minimum screen visibility
      const physLen = isFreight ? 240.0 : isHighSpeed ? 160.0 : 85.0;
      const physWidth = isFreight ? 3.4 : 3.0;
      const trainLen = Math.max(physLen, (isFreight ? 38 : isHighSpeed ? 34 : 26) / scale);
      const trainWidth = Math.max(physWidth, (isFreight ? 10 : 8) / scale);

      // Active manual override: pulsating neon purple halo
      if (activeOverride) {
        const oPulse = (Math.sin(Date.now() / 160) + 1) / 2;
        ctx.save();
        ctx.beginPath();
        ctx.arc(tx, ty, (trainLen * 0.85) * (1.2 + oPulse * 0.35), 0, Math.PI * 2);
        ctx.strokeStyle = '#c084fc';
        ctx.lineWidth = 3.5 / scale;
        ctx.shadowColor = '#a855f7';
        ctx.shadowBlur = 18;
        ctx.stroke();
        ctx.fillStyle = 'rgba(168, 85, 247, 0.22)';
        ctx.fill();
        ctx.restore();
      }

      // Active train disruption: pulsating crimson hazard beacon
      if (isDisruptedTrain) {
        const dPulse = (Math.sin(Date.now() / 140) + 1) / 2;
        ctx.save();
        ctx.beginPath();
        ctx.arc(tx, ty, (trainLen * 0.85) * (1.3 + dPulse * 0.4), 0, Math.PI * 2);
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 4 / scale;
        ctx.shadowColor = '#dc2626';
        ctx.shadowBlur = 22;
        ctx.stroke();
        ctx.fillStyle = 'rgba(239, 68, 68, 0.28)';
        ctx.fill();
        ctx.restore();
      }

      ctx.save();
      ctx.translate(tx, ty);
      ctx.rotate(angleRad);

      // Glow if selected
      if (isSelected) {
        ctx.shadowColor = '#00f0ff';
        ctx.shadowBlur = 18;
      }

      // Train Body
      ctx.beginPath();
      ctx.roundRect(-trainLen / 2, -trainWidth / 2, trainLen, trainWidth, 3 / scale);

      if (isDisruptedTrain) {
        ctx.fillStyle = '#dc2626'; // Bright Red for stalled breakdown
      } else if (activeOverride) {
        ctx.fillStyle = '#7c3aed'; // Vivid Purple for overridden vehicle
      } else if (isDelayed) {
        ctx.fillStyle = '#ef4444'; // Red for delayed
      } else if (isHighSpeed) {
        ctx.fillStyle = '#00f0ff'; // Neon Cyan for High-Speed
      } else if (isFreight) {
        ctx.fillStyle = '#f97316'; // Orange for Freight
      } else {
        ctx.fillStyle = '#10b981'; // Emerald for Regional
      }
      ctx.fill();

      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.2 / scale;
      ctx.stroke();

      // Heading indicator (nose chevron)
      ctx.beginPath();
      ctx.moveTo(trainLen / 2, 0);
      ctx.lineTo(trainLen / 2 - 6 / scale, -trainWidth / 3);
      ctx.lineTo(trainLen / 2 - 6 / scale, trainWidth / 3);
      ctx.closePath();
      ctx.fillStyle = '#ffffff';
      ctx.fill();

      ctx.restore();

      // Train Label Pill (non-rotated)
      const speedKmh = Math.round(train.speed_kmh ?? ((train.speed || 0) * 3.6));
      const trainDisplayId = train.train_number ? `Train #${train.train_number}` : `Train #${train.id}`;
      const trainLabel = `${trainDisplayId} • ${speedKmh} km/h`;
      const tFontSize = 9.5 / scale;
      ctx.font = `600 ${tFontSize}px Inter, system-ui, sans-serif`;
      const tMetrics = ctx.measureText(trainLabel);
      const tW = tMetrics.width + (6 / scale);
      const tH = tFontSize + (4 / scale);
      const tBoxX = tx - tW / 2;
      const tBoxY = ty + (10 / scale);

      ctx.fillStyle = isSelected 
        ? 'rgba(0, 240, 255, 0.95)' 
        : (activeOverride ? 'rgba(88, 28, 135, 0.92)' : 'rgba(15, 23, 42, 0.88)');
      ctx.beginPath();
      ctx.roundRect(tBoxX, tBoxY, tW, tH, 3 / scale);
      ctx.fill();
      ctx.strokeStyle = isSelected 
        ? '#ffffff' 
        : (activeOverride ? '#c084fc' : (isDisruptedTrain ? '#ef4444' : 'rgba(255, 255, 255, 0.25)'));
      ctx.lineWidth = 1 / scale;
      ctx.stroke();

      ctx.fillStyle = isSelected ? '#04111d' : '#f1f5f9';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(trainLabel, tx, tBoxY + tH / 2);

      // Floating Badges above Train for Disruptions, Surges, Reroutes, or Overrides
      if (isDisruptedTrain) {
        const delaySec = Math.round(train.delay_sec || 0);
        const disLabel = `🚨 BREAKDOWN (0 km/h) • DELAY: +${delaySec}s`;
        const dFontSize = 9.5 / scale;
        ctx.font = `800 ${dFontSize}px Inter, system-ui, sans-serif`;
        const dMetrics = ctx.measureText(disLabel);
        const dW = dMetrics.width + (8 / scale);
        const dH = dFontSize + (6 / scale);
        const dX = tx - dW / 2;
        const dY = ty - (26 / scale);

        ctx.fillStyle = 'rgba(185, 28, 28, 0.96)';
        ctx.beginPath();
        ctx.roundRect(dX, dY, dW, dH, 4 / scale);
        ctx.fill();
        ctx.strokeStyle = '#fca5a5';
        ctx.lineWidth = 1.5 / scale;
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(disLabel, tx, dY + dH / 2);
      } else if (train.surge_active) {
        const sLabel = '⚡ PASSENGER DWELL SURGE (+40%)';
        const sFontSize = 9 / scale;
        ctx.font = `800 ${sFontSize}px Inter, system-ui, sans-serif`;
        const sMetrics = ctx.measureText(sLabel);
        const sW = sMetrics.width + (8 / scale);
        const sH = sFontSize + (6 / scale);
        const sX = tx - sW / 2;
        const sY = ty - (26 / scale);

        ctx.fillStyle = 'rgba(180, 83, 9, 0.96)';
        ctx.beginPath();
        ctx.roundRect(sX, sY, sW, sH, 4 / scale);
        ctx.fill();
        ctx.strokeStyle = '#fcd34d';
        ctx.lineWidth = 1.5 / scale;
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(sLabel, tx, sY + sH / 2);
      } else if (train.bypass_divert) {
        const divLabel = '🔄 AI DIVERSION: ALTERNATE PLATFORM';
        const divFontSize = 9 / scale;
        ctx.font = `800 ${divFontSize}px Inter, system-ui, sans-serif`;
        const divMetrics = ctx.measureText(divLabel);
        const divW = divMetrics.width + (8 / scale);
        const divH = divFontSize + (6 / scale);
        const divX = tx - divW / 2;
        const divY = ty - (26 / scale);

        ctx.fillStyle = 'rgba(67, 56, 202, 0.96)';
        ctx.beginPath();
        ctx.roundRect(divX, divY, divW, divH, 4 / scale);
        ctx.fill();
        ctx.strokeStyle = '#a5b4fc';
        ctx.lineWidth = 1.5 / scale;
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(divLabel, tx, divY + divH / 2);
      } else if (train.is_holding || (train.speed_kmh === 0 && (train.delay_sec || 0) > 20)) {
        const holdLabel = '⚠️ APPROACH HOLD [HEADWAY SIGNAL]';
        const hFontSize = 9 / scale;
        ctx.font = `800 ${hFontSize}px Inter, system-ui, sans-serif`;
        const hMetrics = ctx.measureText(holdLabel);
        const hW = hMetrics.width + (8 / scale);
        const hH = hFontSize + (6 / scale);
        const hX = tx - hW / 2;
        const hY = ty - (26 / scale);

        ctx.fillStyle = 'rgba(180, 83, 9, 0.92)';
        ctx.beginPath();
        ctx.roundRect(hX, hY, hW, hH, 4 / scale);
        ctx.fill();
        ctx.strokeStyle = '#fde68a';
        ctx.lineWidth = 1.2 / scale;
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(holdLabel, tx, hY + hH / 2);
      } else if (activeOverride) {
        const ovLabel = `🎮 OVERRIDE: ${activeOverride.label || activeOverride.type}`;
        const oFontSize = 9.5 / scale;
        ctx.font = `800 ${oFontSize}px Inter, system-ui, sans-serif`;
        const oMetrics = ctx.measureText(ovLabel);
        const oW = oMetrics.width + (8 / scale);
        const oH = oFontSize + (6 / scale);
        const oX = tx - oW / 2;
        const oY = ty - (26 / scale);

        ctx.fillStyle = 'rgba(88, 28, 135, 0.96)';
        ctx.beginPath();
        ctx.roundRect(oX, oY, oW, oH, 4 / scale);
        ctx.fill();
        ctx.strokeStyle = '#c084fc';
        ctx.lineWidth = 1.5 / scale;
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(ovLabel, tx, oY + oH / 2);
      }
    }

    ctx.restore(); // Exit world coordinate zoom/pan transform

    // 4. Screen-space HUD Overlays (Top Alert Banners on Canvas)
    if (activeDisruptionsData.length > 0 || Object.keys(activeOverrides).length > 0) {
      let bannerY = 16;
      if (activeDisruptionsData.length > 0) {
        const bannerW = Math.min(width - 32, 600);
        const bannerH = 34;
        const bannerX = (width - bannerW) / 2;
        const firstD = activeDisruptionsData[0];
        const modeLabel = firstD.mode ? firstD.mode.replace('_', ' ').toUpperCase() : 'INCIDENT';
        const targetText = firstD.station_name || firstD.vehicle_id || firstD.platform_id || 'Network';
        const bannerText = `🚨 ACTIVE DISRUPTION: ${modeLabel} @ ${targetText} • Click Station to Inspect Tracks`;

        ctx.fillStyle = 'rgba(153, 27, 27, 0.94)';
        ctx.beginPath();
        ctx.roundRect(bannerX, bannerY, bannerW, bannerH, 6);
        ctx.fill();
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.font = '700 12px Inter, system-ui, sans-serif';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(bannerText, bannerX + bannerW / 2, bannerY + bannerH / 2);

        bannerY += bannerH + 8;
      }

      if (Object.keys(activeOverrides).length > 0) {
        const oVehs = Object.keys(activeOverrides).join(', #');
        const bannerW = Math.min(width - 32, 500);
        const bannerH = 30;
        const bannerX = (width - bannerW) / 2;
        const ovText = `🎮 MANUAL OVERRIDE ACTIVE: #${oVehs} • AI Yielding Priority Margin`;

        ctx.fillStyle = 'rgba(76, 29, 149, 0.94)';
        ctx.beginPath();
        ctx.roundRect(bannerX, bannerY, bannerW, bannerH, 6);
        ctx.fill();
        ctx.strokeStyle = '#c084fc';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.font = '700 11.5px Inter, system-ui, sans-serif';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(ovText, bannerX + bannerW / 2, bannerY + bannerH / 2);
      }
    }

    ctx.restore(); // Exit DPR scaling
  }, [geometry, filteredTrains, selectedTrain, selectedStation, selectedStationTopology, simStatus.active_disruptions_data, simStatus.active_overrides, selectedFeature, showSignalHeads, activeFeatureLayer, showOverlayLabels]);

  // Request Animation Frame loop
  useEffect(() => {
    let animId;
    const loop = () => {
      renderCanvas();
      animId = requestAnimationFrame(loop);
    };
    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [renderCanvas]);

  // Pan & Zoom Controls
  const handleMouseDown = (e) => {
    isDraggingRef.current = true;
    didDragRef.current = false;
    dragStartRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
      didDragRef.current = true;
    }
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    transformRef.current.offsetX += dx;
    transformRef.current.offsetY += dy;
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  const handleWheel = (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const currentScale = transformRef.current.scale;
    const newScale = Math.min(Math.max(currentScale * zoomFactor, 0.005), 60.0);

    transformRef.current.offsetX = mouseX - (mouseX - transformRef.current.offsetX) * (newScale / currentScale);
    transformRef.current.offsetY = mouseY - (mouseY - transformRef.current.offsetY) * (newScale / currentScale);
    transformRef.current.scale = newScale;
  };

  const zoomIn = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const cx = canvas.clientWidth / 2;
    const cy = canvas.clientHeight / 2;
    const currentScale = transformRef.current.scale;
    const newScale = Math.min(currentScale * 1.35, 60.0);
    const factor = newScale / currentScale;
    transformRef.current.offsetX = cx - (cx - transformRef.current.offsetX) * factor;
    transformRef.current.offsetY = cy - (cy - transformRef.current.offsetY) * factor;
    transformRef.current.scale = newScale;
  };
  const zoomOut = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const cx = canvas.clientWidth / 2;
    const cy = canvas.clientHeight / 2;
    const currentScale = transformRef.current.scale;
    const newScale = Math.max(currentScale * 0.75, 0.005);
    const factor = newScale / currentScale;
    transformRef.current.offsetX = cx - (cx - transformRef.current.offsetX) * factor;
    transformRef.current.offsetY = cy - (cy - transformRef.current.offsetY) * factor;
    transformRef.current.scale = newScale;
  };
  const resetView = () => {
    resetViewAnimated();
  };

  // Click on Canvas to Select Nearest Train or Station
  const handleCanvasClick = (e) => {
    if (didDragRef.current) return;
    const canvas = canvasRef.current;
    if (!canvas || !geometry) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const { scale, offsetX, offsetY } = transformRef.current;
    const bounds = geometry.bounds || [-0.33, -0.18, 29708.16, 26683.47];
    const [, minY, , maxY] = bounds;

    const worldX = (clickX - offsetX) / scale;
    const worldY = maxY + minY - (clickY - offsetY) / scale;

    // 1. Check if user clicked on a Station (prioritize station zoom)
    if (geometry && geometry.stations) {
      let closestStation = null;
      let minStationDist = Math.max(50 / scale, 850); // screen click radius ~50px
      for (const st of geometry.stations) {
        const dist = Math.hypot(st.x - worldX, st.y - worldY);
        if (dist < minStationDist) {
          minStationDist = dist;
          closestStation = st;
        }
      }
      if (closestStation) {
        zoomToStation(closestStation);
        return;
      }
    }

    // 2. Check if user clicked on a Buffer Stop (Dead-End Terminus)
    if (geometry && geometry.buffer_stops) {
      let closestBuf = null;
      let minBufDist = 32 / scale; // ~32 screen pixels
      for (const buf of geometry.buffer_stops) {
        const dist = Math.hypot(buf.x - worldX, buf.y - worldY);
        if (dist < minBufDist) {
          minBufDist = dist;
          closestBuf = buf;
        }
      }
      if (closestBuf) {
        zoomToFeature({ ...closestBuf, type: 'buffer_stop' });
        return;
      }
    }

    // 3. Check if user clicked on a Track Feature Complex (Crossover / Loop / Bypass)
    if (geometry && geometry.track_features) {
      let closestFeat = null;
      let minFeatDist = 45 / scale; // ~45 screen pixels
      for (const feat of geometry.track_features) {
        const dist = Math.hypot(feat.x - worldX, feat.y - worldY);
        if (dist < minFeatDist) {
          minFeatDist = dist;
          closestFeat = feat;
        }
      }
      if (closestFeat) {
        zoomToFeature(closestFeat);
        return;
      }
    }

    // 4. Check if user clicked on a Train
    let closest = null;
    let minDist = 35 / scale; // click tolerance in world coordinates

    for (const t of filteredTrains) {
      const dist = Math.hypot(t.x - worldX, t.y - worldY);
      if (dist < minDist) {
        minDist = dist;
        closest = t;
      }
    }
    if (closest) {
      zoomToTrain(closest);
      return;
    }
  };

  // Playback Control Handlers
  const sendControl = useCallback(async (action, speed, reqId, startTimeSec) => {
    const targetSpeed = speed !== undefined ? speed : (selectedSpeedRef.current ?? confirmedSpeedRef.current ?? simStatus.speed_multiplier ?? 1.0);
    const currentReqId = reqId !== undefined ? reqId : (action === 'set_speed' || speed !== undefined ? ++speedRequestIdRef.current : undefined);
    try {
      if (action === 'set_speed') {
        const res = await fetch('/api/sim/config', {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'X-Session-ID': sessionIdRef.current
          },
          body: JSON.stringify({ speed: targetSpeed })
        });
        if (res.ok) {
          const data = await res.json().catch(() => null);
          if (data && data.success !== false) {
            const isWinning = currentReqId === undefined || currentReqId >= latestConfirmedSpeedReqIdRef.current;
            if (isWinning) {
              if (currentReqId !== undefined) {
                latestConfirmedSpeedReqIdRef.current = currentReqId;
              }
              lastConfirmedSpeedTimeRef.current = Date.now();
              confirmedSpeedRef.current = targetSpeed;
            }
            if (selectedSpeedRef.current === targetSpeed) {
              selectedSpeedRef.current = null;
            }
          } else {
            if (selectedSpeedRef.current === targetSpeed) {
              selectedSpeedRef.current = null;
              setSimStatus(prev => ({ ...prev, speed_multiplier: confirmedSpeedRef.current }));
            }
          }
        } else {
          if (selectedSpeedRef.current === targetSpeed) {
            selectedSpeedRef.current = null;
            setSimStatus(prev => ({ ...prev, speed_multiplier: confirmedSpeedRef.current }));
          }
        }
      } else {
        const payload = { action, speed: targetSpeed };
        if (action === 'reset' && startTimeSec !== undefined) {
          payload.start_time_sec = startTimeSec;
        }
        const res = await fetch('/api/sim/control', {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'X-Session-ID': sessionIdRef.current
          },
          body: JSON.stringify(payload)
        });
        if (action === 'reset') {
          setSelectedTrain(null);
          setSelectedStation(null);
          setSelectedFeature(null);
          setShowDisruptionModal(false);
          setShowOverrideModal(false);
          setDayCompletionDismissed(false);
          if (res.ok) {
            const data = await res.json().catch(() => null);
            const status = data?.current_status || {};
            setSimStatus(prev => ({
              ...prev,
              running: false,
              paused: false,
              sim_time_sec: status.sim_time_sec ?? (startTimeSec !== undefined ? startTimeSec : 21600.0),
              sim_time_formatted: status.time_formatted ?? (startTimeSec !== undefined ? `${String(Math.floor(startTimeSec / 3600)).padStart(2, '0')}:${String(Math.floor((startTimeSec % 3600) / 60)).padStart(2, '0')}:00` : '06:00:00'),
              active_disruptions: [],
              active_disruptions_data: [],
              active_overrides: {},
              day_completed: false
            }));
            setKpis(prev => ({
              ...prev,
              avg_delay_sec: 0.0,
              max_delay_sec: 0.0,
              punctuality_pct: 100.0,
              active_trains: status.active_trains_count ?? 0,
              total_actions_taken: 0
            }));
            if (Array.isArray(data?.trains)) {
              setTrains(data.trains.map(t => {
                let cat = t.category;
                if (!cat) {
                  const vid = t.id || '';
                  const vtype = t.vtype || '';
                  if (vid.startsWith('HS') || vtype.includes('high_speed')) {
                    cat = 'HighSpeed';
                  } else if (vid.startsWith('FRT') || vtype.includes('freight')) {
                    cat = 'Freight';
                  } else {
                    cat = 'Regional';
                  }
                }
                const speedMs = t.speed_ms ?? t.speed ?? ((t.speed_kmh ?? 0) / 3.6);
                return {
                  ...t,
                  category: cat,
                  train_number: t.train_number || t.id,
                  speed_kmh: t.speed_kmh ?? Math.round(speedMs * 3.6),
                  speed: speedMs
                };
              }));
            }
          } else {
            setSimStatus(prev => ({
              ...prev,
              running: false,
              paused: false,
              sim_time_sec: startTimeSec !== undefined ? startTimeSec : 21600.0,
              sim_time_formatted: startTimeSec !== undefined ? `${String(Math.floor(startTimeSec / 3600)).padStart(2, '0')}:${String(Math.floor((startTimeSec % 3600) / 60)).padStart(2, '0')}:00` : '06:00:00',
              active_disruptions: [],
              active_disruptions_data: [],
              active_overrides: {},
              day_completed: false
            }));
          }
        } else if (res.ok && speed !== undefined) {
          const isWinning = currentReqId === undefined || currentReqId >= latestConfirmedSpeedReqIdRef.current;
          if (isWinning) {
            if (currentReqId !== undefined) {
              latestConfirmedSpeedReqIdRef.current = currentReqId;
            }
            lastConfirmedSpeedTimeRef.current = Date.now();
            confirmedSpeedRef.current = targetSpeed;
          }
          if (selectedSpeedRef.current === targetSpeed) {
            selectedSpeedRef.current = null;
          }
        }
      }
      fetchStatus();
    } catch (err) {
      if (action === 'set_speed' && selectedSpeedRef.current === targetSpeed) {
        selectedSpeedRef.current = null;
        setSimStatus(prev => ({ ...prev, speed_multiplier: confirmedSpeedRef.current }));
      }
      console.error('Sim control error:', err);
    }
  }, [fetchStatus, simStatus.speed_multiplier]);

  const handleSpeedChange = (s) => {
    selectedSpeedRef.current = s;
    setSimStatus(prev => ({ ...prev, speed_multiplier: s }));
    const reqId = ++speedRequestIdRef.current;
    speedQueueRef.current = speedQueueRef.current.then(async () => {
      await sendControl('set_speed', s, reqId);
    }).catch(err => {
      console.error('Speed change error:', err);
    });
  };

  const handleConfigChange = async (day, model) => {
    try {
      const modelChanged = model !== selectedModel;
      if (modelChanged) {
        setKpis(prev => ({ ...prev, total_actions_taken: 0 }));
      }
      const res = await fetch('/api/sim/config', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Session-ID': sessionIdRef.current
        },
        body: JSON.stringify({ day, model })
      });
      setSelectedDay(day);
      setSelectedModel(model);
      setDayCompletionDismissed(false);
      if (res.ok) {
        const data = await res.json().catch(() => null);
        if (data?.updated_status) {
          const s = data.updated_status;
          setSimStatus(prev => ({
            ...prev,
            current_model: s.dispatcher_model || model,
            current_day: s.calendar_day || day,
            day_completed: Boolean(s.day_completed)
          }));
          if (s.daily_summary) {
            setKpis(prev => ({
              ...prev,
              daily_summary: s.daily_summary,
              avg_delay_sec: s.daily_summary.mean_delay_sec ?? prev.avg_delay_sec,
              punctuality_pct: s.daily_summary.punctuality_pct ?? prev.punctuality_pct,
              total_actions_taken: s.daily_summary.total_actions_taken ?? 0
            }));
          }
        }
      }
      fetchStatus();
    } catch (err) {
      console.error('Config change error:', err);
    }
  };



  // Clear Disruptions
  const handleClearDisruptions = async () => {
    try {
      await fetch('/api/disruption/clear', { 
        method: 'POST',
        headers: { 'X-Session-ID': sessionIdRef.current }
      });
      setSimStatus(prev => ({
        ...prev,
        active_disruptions: [],
        active_disruptions_data: []
      }));
      fetchStatus();
    } catch (err) {
      console.error('Clear disruptions error:', err);
    }
  };


  return (
    <div className="simulation-page">
      {/* Top HUD Controls Bar */}
      <div className="sim-hud-bar glass-panel">
        <div className="hud-left-group">
          {/* Play / Pause / Step / Reset */}
          <div className="hud-playback-controls">
            {simStatus.running && !simStatus.paused ? (
              <button 
                onClick={() => sendControl('pause')} 
                className="btn btn-hud btn-hud-pause" 
                title="Pause Simulation"
              >
                <Pause size={18} />
                <span>Pause</span>
              </button>
            ) : (
              <button 
                onClick={() => sendControl('play')} 
                className="btn btn-hud btn-hud-play" 
                title="Run Simulation"
              >
                <Play size={18} fill="currentColor" />
                <span>Run</span>
              </button>
            )}

            <button 
              onClick={() => sendControl('reset')} 
              className="btn btn-hud" 
              title="Reset Simulation Day"
            >
              <RotateCcw size={16} />
              <span>Reset</span>
            </button>
          </div>

          {/* Speed Multiplier */}
          <div className="hud-speed-group">
            <FastForward size={14} className="speed-icon" />
            {[1, 2, 5, 10, 20, 30, 40, 50].map((s) => (
              <button
                key={s}
                onClick={() => handleSpeedChange(s)}
                className={`btn-speed-pill ${simStatus.speed_multiplier === s ? 'active' : ''}`}
              >
                {s}x
              </button>
            ))}
          </div>

          <div className="hud-divider" />

          {/* Day Selector */}
          <div className="hud-select-group">
            <span className="hud-select-label">Day:</span>
            <select 
              value={selectedDay} 
              onChange={(e) => handleConfigChange(e.target.value, selectedModel)}
              className="hud-dropdown"
            >
              {DAYS.map(d => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>

          {/* AI Model Selector */}
          <div className="hud-select-group">
            <span className="hud-select-label">Dispatcher AI:</span>
            <select 
              value={selectedModel} 
              onChange={(e) => handleConfigChange(selectedDay, e.target.value)}
              className="hud-dropdown hud-model-dropdown"
            >
              {MODELS.map(m => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>

          <div className="hud-divider" />

          {/* Session Sandbox Group (Model B: Per-User Isolated Control Room) */}
          <div className="hud-session-group" title={`Session ID: ${sessionId} (Model B: Isolated Simulation Sandbox)`}>
            <div className="hud-session-badge">
              <span className="hud-session-pulse" />
              <span className="hud-session-label">Session:</span>
              <span className="hud-session-id">{sessionId.replace('sess_', '').slice(0, 8)}</span>
            </div>
            <button 
              onClick={handleNewSession}
              className="btn-new-session" 
              title="Spawn a new private simulation sandbox"
            >
              <RefreshCw size={12} />
              <span>New Session</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Simulation Viewport */}
      <div className="sim-viewport-container">
        {/* HTML5 Canvas */}
        <div className="canvas-wrapper">
          {loadingGeometry && (
            <div className="canvas-loader-overlay">
              <RefreshCw size={36} className="loader-spin" />
              <span>Parsing 2,413 Network Lanes & Platform Topology...</span>
            </div>
          )}

          <canvas 
            ref={canvasRef}
            className="rail-canvas"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onWheel={handleWheel}
            onClick={handleCanvasClick}
          />

          {/* Floating Canvas Camera Tools */}
          <div className="canvas-floating-controls">
            <button onClick={zoomIn} title="Zoom In" className="btn-canvas-tool"><ZoomIn size={16} /></button>
            <button onClick={zoomOut} title="Zoom Out" className="btn-canvas-tool"><ZoomOut size={16} /></button>
            <button onClick={resetView} title="Reset Network View" className="btn-canvas-tool"><Maximize2 size={16} /></button>
          </div>

          {/* Canvas Floating Clock & KPI Overlay */}
          <div className="canvas-clock-overlay glass-panel">
            <div className="clock-time-row">
              <Clock size={16} className="clock-icon" />
              <span className="clock-digits">{simStatus.sim_time_formatted || '06:00:00'}</span>
              <span className={`sim-state-chip ${simStatus.day_completed ? 'chip-completed' : (simStatus.running && !simStatus.paused ? 'chip-live' : 'chip-paused')}`}>
                {simStatus.day_completed ? 'DAY COMPLETE' : (simStatus.running && !simStatus.paused ? 'RUNNING' : 'PAUSED')}
              </span>
            </div>
            <div className="kpi-mini-grid">
              <div className="kpi-mini-item">
                <span className="kpi-mini-lbl">Active</span>
                <span className="kpi-mini-val text-cyan">{kpis.active_trains || trains.length}</span>
              </div>
              <div className="kpi-mini-item">
                <span className="kpi-mini-lbl">Punctuality</span>
                <span className="kpi-mini-val text-emerald">{(kpis.punctuality_pct ?? 100.0).toFixed(1)}%</span>
              </div>
              <div className="kpi-mini-item">
                <span className="kpi-mini-lbl">Avg Delay</span>
                <span className="kpi-mini-val text-amber">{(kpis.avg_delay_sec ?? 0).toFixed(1)}s</span>
              </div>
            </div>
          </div>


          {/* Draggable Floating Station Traffic HUD Card */}
          {selectedStation && (
            <div 
              className={`canvas-station-focus-card glass-panel ${isDraggingStationCard ? 'is-dragging' : ''}`}
              style={{
                left: `${stationCardPos.x}px`,
                top: `${stationCardPos.y}px`,
              }}
              onPointerDown={handleCardPointerDown}
            >
              <div 
                className="station-focus-header drag-handle"
                onDoubleClick={() => setStationCardPos({ x: 20, y: 145 })}
                title="Drag to move anywhere • Double-click to reset"
              >
                <div className="station-focus-title">
                  <GripHorizontal size={15} className="drag-grip-icon" />
                  <MapPin size={15} className="text-cyan animate-pulse" />
                  <h4>{selectedStation.display_name || selectedStation.station_name}</h4>
                </div>
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    resetViewAnimated();
                  }} 
                  className="btn-close-train" 
                  title="Close Focus Card & Reset View"
                >
                  <X size={15} />
                </button>
              </div>

              {/* Live Trains on Station Tracks: Approaching, Dwelling, Departing */}
              <div className="station-focus-traffic-row">
                <div className="traffic-metric">
                  <span className="traffic-num text-cyan">{selectedStationTrains.approaching.length}</span>
                  <span className="traffic-lbl">Approaching</span>
                </div>
                <div className="traffic-metric">
                  <span className="traffic-num text-amber">{selectedStationTrains.dwelling.length}</span>
                  <span className="traffic-lbl">Dwelling</span>
                </div>
                <div className="traffic-metric">
                  <span className="traffic-num text-emerald">{selectedStationTrains.departing.length}</span>
                  <span className="traffic-lbl">Departing</span>
                </div>
              </div>
            </div>
          )}

          {/* Google Maps Railway Infrastructure Layer Control Bar */}
          <div className="google-maps-feature-bar glass-panel">
            <div className="feature-bar-label">
              <Layers size={13} className="text-cyan" />
              <span>INFRASTRUCTURE</span>
            </div>
            
            <button 
              className={`feature-tab ${activeFeatureLayer === 'none' && !selectedFeature ? 'active' : ''}`}
              onClick={() => {
                setActiveFeatureLayer('none');
                setSelectedFeature(null);
                setShowOverlayLabels(false);
              }}
              title="Clean Map: Hide all active overlays, markers, and badges"
            >
              <span>Clean Map</span>
            </button>

            <button 
              className={`feature-tab tab-crossover ${activeFeatureLayer === 'crossovers' ? 'active' : ''}`}
              onClick={() => {
                const xovList = (geometry?.track_features || []).filter(f => f.type === 'crossover');
                if (activeFeatureLayer === 'crossovers' && selectedFeature && xovList.length > 0) {
                  const curIdx = xovList.findIndex(f => f.id === selectedFeature.id);
                  const nextXov = xovList[(curIdx + 1) % xovList.length];
                  zoomToFeature(nextXov);
                } else {
                  setActiveFeatureLayer('crossovers');
                  if (xovList.length > 0) zoomToFeature(xovList[0]);
                }
              }}
              title="Highlight & Cycle through 8 High-Speed Double-Diamond X Crossovers"
            >
              <span className="dot dot-amber"></span>
              <span>X Crossovers</span>
              <span className="feature-count-badge">8</span>
            </button>

            <button 
              className={`feature-tab tab-loop ${activeFeatureLayer === 'loops' ? 'active' : ''}`}
              onClick={() => {
                const loopList = (geometry?.track_features || []).filter(f => f.type === 'passing_loop' || f.type === 'express_thru');
                if (activeFeatureLayer === 'loops' && selectedFeature && loopList.length > 0) {
                  const curIdx = loopList.findIndex(f => f.id === selectedFeature.id);
                  const nextLoop = loopList[(curIdx + 1) % loopList.length];
                  zoomToFeature(nextLoop);
                } else {
                  setActiveFeatureLayer('loops');
                  if (loopList.length > 0) zoomToFeature(loopList[0]);
                }
              }}
              title="Highlight & Cycle through 12 Dynamic Passing Loops & Express Bypasses"
            >
              <span className="dot dot-teal"></span>
              <span>Passing Loops</span>
              <span className="feature-count-badge">12</span>
            </button>

            <button 
              className={`feature-tab tab-buffer ${activeFeatureLayer === 'buffer_stops' ? 'active' : ''}`}
              onClick={() => {
                const bufList = (geometry?.buffer_stops || []).map(b => ({ ...b, type: 'buffer_stop' }));
                if (activeFeatureLayer === 'buffer_stops' && selectedFeature && bufList.length > 0) {
                  const curIdx = bufList.findIndex(f => f.id === selectedFeature.id);
                  const nextBuf = bufList[(curIdx + 1) % bufList.length];
                  zoomToFeature(nextBuf);
                } else {
                  setActiveFeatureLayer('buffer_stops');
                  if (bufList.length > 0) zoomToFeature(bufList[0]);
                }
              }}
              title="Highlight & Cycle through 23 Dead-End Terminus Buffer Stops"
            >
              <span className="dot dot-rose"></span>
              <span>Buffer Stops</span>
              <span className="feature-count-badge">23</span>
            </button>

            <button 
              className={`feature-tab tab-signals ${activeFeatureLayer === 'signals' || showSignalHeads ? 'active' : ''}`}
              onClick={() => {
                const sigList = (geometry?.signals || []).map(s => ({ ...s, type: 'signal' }));
                if (activeFeatureLayer === 'signals' && selectedFeature && sigList.length > 0) {
                  const curIdx = sigList.findIndex(f => f.id === selectedFeature.id);
                  const nextSig = sigList[(curIdx + 1) % sigList.length];
                  zoomToFeature(nextSig);
                } else {
                  setShowSignalHeads(true);
                  setActiveFeatureLayer('signals');
                  if (sigList.length > 0) zoomToFeature(sigList[0]);
                }
              }}
              title="Toggle & Cycle through 268 Multi-Aspect Railway Signals"
            >
              <span className="dot dot-emerald"></span>
              <span>Signals</span>
              <span className="feature-count-badge">268</span>
            </button>

            <button 
              className={`feature-tab tab-labels ${showOverlayLabels ? 'active' : ''}`}
              onClick={() => setShowOverlayLabels(prev => !prev)}
              title={showOverlayLabels ? "Hide map text labels & floating badges (Clean View)" : "Show map feature labels & station tags"}
            >
              <Eye size={13} className={showOverlayLabels ? "text-cyan" : "text-muted"} />
              <span>{showOverlayLabels ? 'Labels ON' : 'Labels OFF'}</span>
            </button>

            <button 
              className={`feature-tab tab-explorer ${showFeatureMenu ? 'active' : ''}`}
              onClick={() => setShowFeatureMenu(prev => !prev)}
              title="Explore Infrastructure Elements & Fly-To Any Feature"
            >
              <Crosshair size={13} className="text-cyan" />
              <span>Directory</span>
            </button>

            <button 
              className={`feature-tab tab-legend ${showMapLegend ? 'active' : ''}`}
              onClick={() => setShowMapLegend(prev => !prev)}
              title="Toggle Railway Track Classification & Operational Speed Legend"
            >
              <Layers size={13} className={showMapLegend ? "text-cyan" : "text-muted"} />
              <span>Legend</span>
            </button>
          </div>

          {/* Floating Feature Inspector HUD Card */}
          {selectedFeature && (
            <div className="canvas-feature-focus-card glass-panel">
              <div className="feature-focus-header">
                <div className="feature-focus-title">
                  <div className={`feature-icon-box ${selectedFeature.type || (selectedFeature.signal_type ? 'signal' : 'crossover')}`}>
                    {selectedFeature.type === 'crossover' && <GitFork size={18} className="text-amber" />}
                    {(selectedFeature.type === 'passing_loop' || selectedFeature.type === 'express_thru') && <Activity size={18} className="text-teal" />}
                    {selectedFeature.type === 'buffer_stop' && <AlertTriangle size={18} className="text-rose" />}
                    {selectedFeature.signal_type && <Zap size={18} className="text-emerald" />}
                  </div>
                  <div>
                    <h4>{selectedFeature.name || selectedFeature.id}</h4>
                    <span className="feature-focus-subtitle">
                      {selectedFeature.type === 'crossover' && 'High-Speed Double Diamond X-Crossover Complex'}
                      {selectedFeature.type === 'passing_loop' && 'Dynamic Siding / Passing Loop'}
                      {selectedFeature.type === 'express_thru' && 'Express Center Thru-Line Bypass'}
                      {selectedFeature.type === 'buffer_stop' && `Dead-End Bay Terminus • ${selectedFeature.station_name || 'Terminal'}`}
                      {selectedFeature.signal_type && `Railway Interlocking Signal • ${selectedFeature.signal_type}`}
                    </span>
                  </div>
                </div>
                <button onClick={() => setSelectedFeature(null)} className="btn-close-train" title="Close Focus">
                  <X size={16} />
                </button>
              </div>

              {/* Arrow Buttons Navigator to cycle across all features */}
              {(() => {
                const peerList = getPeerFeatures(selectedFeature);
                const peerIndex = peerList.findIndex(f => f.id === selectedFeature.id);
                const totalPeers = peerList.length;

                return totalPeers > 1 ? (
                  <div className="feature-focus-nav-strip">
                    <button 
                      className="btn-peer-cycle"
                      onClick={() => {
                        const prevIdx = (peerIndex - 1 + totalPeers) % totalPeers;
                        zoomToFeature(peerList[prevIdx]);
                      }}
                      title="View Previous Feature (← Arrow)"
                    >
                      <ChevronLeft size={16} />
                      <span>Prev</span>
                    </button>

                    <div className="peer-step-badge">
                      <span className="peer-type-name">
                        {selectedFeature.type === 'crossover' ? 'Crossover' : 
                         (selectedFeature.type === 'passing_loop' || selectedFeature.type === 'express_thru') ? 'Loop / Siding' : 
                         selectedFeature.type === 'buffer_stop' ? 'Buffer Stop' : 'Signal'}
                      </span>
                      <span className="peer-index-txt">{peerIndex + 1} of {totalPeers}</span>
                    </div>

                    <button 
                      className="btn-peer-cycle"
                      onClick={() => {
                        const nextIdx = (peerIndex + 1) % totalPeers;
                        zoomToFeature(peerList[nextIdx]);
                      }}
                      title="View Next Feature (→ Arrow)"
                    >
                      <span>Next</span>
                      <ChevronRight size={16} />
                    </button>
                  </div>
                ) : null;
              })()}

              <div className="feature-focus-specs">
                <div className="spec-item">
                  <span className="spec-lbl">Feature Type</span>
                  <span className="spec-val highlight">
                    {selectedFeature.type === 'crossover' ? 'X Diamond Switch' :
                     selectedFeature.type === 'passing_loop' ? 'Passing Loop' :
                     selectedFeature.type === 'express_thru' ? 'Express Bypass' :
                     selectedFeature.type === 'buffer_stop' ? 'Buffer Stop (Dead End)' : 'Signal Post'}
                  </span>
                </div>
                {selectedFeature.speed_kmh && (
                  <div className="spec-item">
                    <span className="spec-lbl">Design Speed</span>
                    <span className="spec-val text-amber">{selectedFeature.speed_kmh} km/h</span>
                  </div>
                )}
                {selectedFeature.lane_count && (
                  <div className="spec-item">
                    <span className="spec-lbl">Turnout Lanes</span>
                    <span className="spec-val text-cyan">{selectedFeature.lane_count} Tracks</span>
                  </div>
                )}
                {selectedFeature.station_name && (
                  <div className="spec-item">
                    <span className="spec-lbl">Station / Yard</span>
                    <span className="spec-val text-blue">{selectedFeature.station_name}</span>
                  </div>
                )}
                <div className="spec-item">
                  <span className="spec-lbl">Coordinates</span>
                  <span className="spec-val font-mono">X: {Math.round(selectedFeature.x)}m, Y: {Math.round(selectedFeature.y)}m</span>
                </div>
              </div>

              {selectedFeature.description && (
                <div className="feature-focus-desc">
                  <p>{selectedFeature.description}</p>
                </div>
              )}

              <div className="feature-focus-actions">
                <button 
                  onClick={() => zoomToFeature(selectedFeature, selectedFeature.type === 'buffer_stop' ? 24.0 : selectedFeature.type === 'crossover' ? 12.0 : 14.0)} 
                  className="btn btn-primary btn-sm"
                  title="Fly to and Focus Feature"
                >
                  <Crosshair size={14} />
                  <span>Inspect Close-Up</span>
                </button>
                <button 
                  onClick={resetViewAnimated} 
                  className="btn btn-secondary btn-sm"
                  title="Reset to Full Network"
                >
                  <Maximize2 size={14} />
                  <span>Network Overview</span>
                </button>
              </div>
            </div>
          )}

          {/* Railway Network Track Legend & Speed Profiles */}
          {showMapLegend && (
            <div className={`canvas-map-legend-card glass-panel ${selectedFeature ? 'with-feature-card' : ''}`}>
              <div className="map-legend-header">
                <div className="map-legend-title">
                  <div className="legend-icon-badge">
                    <Layers size={15} className="text-cyan" />
                  </div>
                  <div>
                    <h4>Railway Network Legend</h4>
                    <span className="legend-subtitle">Rolling Stock, Corridors & Safety Hardware</span>
                  </div>
                </div>
                <button 
                  onClick={() => setShowMapLegend(false)} 
                  className="btn-legend-close"
                  title="Close Legend (Reopen via toolbar anytime)"
                >
                  <X size={15} />
                </button>
              </div>

              <div className="map-legend-scroll">
                {/* 1. Train Fleet & Rolling Stock */}
                <div className="legend-section">
                  <div className="legend-section-title">TRAIN FLEET & STATUS COLORS</div>
                  <div className="legend-row">
                    <div className="legend-train-marker high-speed"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">High-Speed Express (ICE)</span>
                        <span className="legend-speed-badge cyan">300 km/h</span>
                      </div>
                      <span className="legend-track-desc">Neon Cyan • 160m EMU express on Corridor 1</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-train-marker regional"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Regional Passenger (RE/RB)</span>
                        <span className="legend-speed-badge mint">160 km/h</span>
                      </div>
                      <span className="legend-track-desc">Emerald Green • 85m frequent-stop passenger service</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-train-marker freight"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Heavy Freight Cargo</span>
                        <span className="legend-speed-badge orange">100 km/h</span>
                      </div>
                      <span className="legend-track-desc">Vivid Orange • 240m long consist; yields at loops</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-train-marker delayed"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Delayed Service</span>
                        <span className="legend-speed-badge rose">&gt; 30s Delay</span>
                      </div>
                      <span className="legend-track-desc">Warning Red • Schedule delay; prioritized for recovery</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-train-marker breakdown"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Mechanical Breakdown / Stall</span>
                        <span className="legend-speed-badge rose">0 km/h</span>
                      </div>
                      <span className="legend-track-desc">Crimson Hazard Beacon • Emergency stop; auto-reroutes traffic</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-train-marker override"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Manual Operator Override</span>
                        <span className="legend-speed-badge purple">Manual</span>
                      </div>
                      <span className="legend-track-desc">Pulsing Purple • Train under active human intervention</span>
                    </div>
                  </div>
                </div>

                {/* 2. Mainline & High-Speed */}
                <div className="legend-section">
                  <div className="legend-section-title">MAINLINE CORRIDORS</div>
                  <div className="legend-row">
                    <div className="legend-track-line high-speed"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">High-Speed Express Trunk</span>
                        <span className="legend-speed-badge cyan">300 km/h</span>
                      </div>
                      <span className="legend-track-desc">Corridor 1 East–West Mainline &amp; Diagonal Bypass</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-track-line regional"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Regional Passenger Spine</span>
                        <span className="legend-speed-badge amber">120 km/h</span>
                      </div>
                      <span className="legend-track-desc">Corridors 2 (N–S), 3 (Alpine), and 4 (Southern Arc)</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-track-line spur"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Maintenance Depot Spurs</span>
                        <span className="legend-speed-badge purple">80 km/h</span>
                      </div>
                      <span className="legend-track-desc">Dedicated electrified branch links connecting to Depots 1–4</span>
                    </div>
                  </div>
                </div>

                {/* 2. Station & Operational Lines */}
                <div className="legend-section">
                  <div className="legend-section-title">STATION & YARD TRACKS</div>
                  <div className="legend-row">
                    <div className="legend-track-line platform"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Passenger Platform Bays</span>
                        <span className="legend-speed-badge gold">50 km/h</span>
                      </div>
                      <span className="legend-track-desc">Commercial boarding bays with trainStop passenger platforms</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-track-line yard"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Stabling & Storage Yards</span>
                        <span className="legend-speed-badge slate">20 km/h</span>
                      </div>
                      <span className="legend-track-desc">Overnight EMU parking, maintenance sidings & freight staging</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-track-line pocket"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Reversal Pockets & Tail Tracks</span>
                        <span className="legend-speed-badge mint">50 km/h</span>
                      </div>
                      <span className="legend-track-desc">Dead-end reversal spurs leading to buffer stops (*Kopfmachen*)</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-track-line passing-loop"></div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Passing Loops & Overtaking</span>
                        <span className="legend-speed-badge teal">60 km/h</span>
                      </div>
                      <span className="legend-track-desc">Alpine dynamic passing sidings & intermediate bypass loops</span>
                    </div>
                  </div>
                </div>

                {/* 3. Interlocking & Safety Hardware */}
                <div className="legend-section">
                  <div className="legend-section-title">INTERLOCKING & HARDWARE</div>
                  <div className="legend-row">
                    <div className="legend-track-line crossover">
                      <span className="frog-diamond"></span>
                    </div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Double Diamond X Crossover</span>
                        <span className="legend-speed-badge amber">160 km/h</span>
                      </div>
                      <span className="legend-track-desc">Universal 4-switch high-speed crossovers (*Überleitstellen*)</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-hardware-icon buffer-stop-icon">
                      <span className="buf-stripe"></span>
                    </div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Buffer Stop (Dead End)</span>
                        <span className="legend-speed-badge rose">0 km/h</span>
                      </div>
                      <span className="legend-track-desc">Hydraulic bumper track arrestors & terminal reversing points</span>
                    </div>
                  </div>

                  <div className="legend-row">
                    <div className="legend-hardware-icon signal-icon">
                      <span className="sig-lens"></span>
                    </div>
                    <div className="legend-meta">
                      <div className="legend-name-line">
                        <span className="legend-track-name">Interlocking Block Signals</span>
                        <span className="legend-speed-badge emerald">Signal</span>
                      </div>
                      <span className="legend-track-desc">Multi-aspect optical signals controlling block headway & routing</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Infrastructure Explorer Drawer */}
          {showFeatureMenu && (
            <div className="feature-explorer-drawer glass-panel">
              <div className="drawer-header">
                <div className="drawer-title">
                  <Layers size={16} className="text-cyan" />
                  <h4>Railway Infrastructure Directory</h4>
                </div>
                <button onClick={() => setShowFeatureMenu(false)} className="btn-close-train">
                  <X size={15} />
                </button>
              </div>

              <div className="drawer-tabs">
                <button 
                  className={`drawer-tab-btn ${activeFeatureLayer === 'crossovers' ? 'active' : ''}`}
                  onClick={() => setActiveFeatureLayer('crossovers')}
                >
                  🔀 X Crossovers ({geometry?.track_features?.filter(f => f.type === 'crossover')?.length || 8})
                </button>
                <button 
                  className={`drawer-tab-btn ${activeFeatureLayer === 'loops' ? 'active' : ''}`}
                  onClick={() => setActiveFeatureLayer('loops')}
                >
                  🔄 Loops & Bypasses ({geometry?.track_features?.filter(f => f.type === 'passing_loop' || f.type === 'express_thru')?.length || 12})
                </button>
                <button 
                  className={`drawer-tab-btn ${activeFeatureLayer === 'buffer_stops' ? 'active' : ''}`}
                  onClick={() => setActiveFeatureLayer('buffer_stops')}
                >
                  🛑 Buffer Stops ({geometry?.buffer_stops?.length || 23})
                </button>
              </div>

              <div className="drawer-items-list">
                {activeFeatureLayer === 'buffer_stops' ? (
                  (geometry?.buffer_stops || []).map((buf) => (
                    <div 
                      key={buf.id} 
                      className={`drawer-feature-item ${selectedFeature?.id === buf.id ? 'active' : ''}`}
                      onClick={() => zoomToFeature({ ...buf, type: 'buffer_stop' })}
                    >
                      <div className="item-icon-col text-rose">🛑</div>
                      <div className="item-info-col">
                        <div className="item-name">{buf.name}</div>
                        <div className="item-sub">Terminus at {buf.station_name || 'Terminal'} • Heading {Math.round(buf.angle_deg)}°</div>
                      </div>
                      <button className="btn-item-fly" title="Zoom to Buffer Stop">
                        <Crosshair size={13} />
                      </button>
                    </div>
                  ))
                ) : (
                  (geometry?.track_features || [])
                    .filter(f => {
                      if (activeFeatureLayer === 'crossovers') return f.type === 'crossover';
                      if (activeFeatureLayer === 'loops') return f.type === 'passing_loop' || f.type === 'express_thru';
                      return true;
                    })
                    .map((feat) => (
                      <div 
                        key={feat.id} 
                        className={`drawer-feature-item ${selectedFeature?.id === feat.id ? 'active' : ''}`}
                        onClick={() => zoomToFeature(feat)}
                      >
                        <div className="item-icon-col">
                          {feat.type === 'crossover' ? '🔀' : feat.type === 'express_thru' ? '⚡' : '🔄'}
                        </div>
                        <div className="item-info-col">
                          <div className="item-name">{feat.name}</div>
                          <div className="item-sub">
                            {feat.type === 'crossover' ? `Diamond Switch • ${feat.lane_count} turnouts • ${feat.speed_kmh} km/h` :
                             feat.type === 'express_thru' ? `Express Bypass • ${feat.speed_kmh} km/h` :
                             `Passing Loop • ${feat.lane_count} siding tracks • ${feat.speed_kmh} km/h`}
                          </div>
                        </div>
                        <button className="btn-item-fly" title="Fly to Feature">
                          <Crosshair size={13} />
                        </button>
                      </div>
                    ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Dispatcher Control Panel (Collapsible & Resizable) */}
        <aside 
          className={`sim-sidebar glass-panel ${!sidebarOpen ? 'sidebar-collapsed' : ''} ${isResizingSidebar ? 'is-resizing' : ''}`}
          style={{
            width: sidebarOpen ? `${sidebarWidth}px` : '0px',
            minWidth: sidebarOpen ? `${sidebarWidth}px` : '0px',
          }}
        >
          {sidebarOpen && (
            <>
              {/* Left Edge Cursor Drag Resize Handle */}
              <div 
                className={`sidebar-resize-handle ${isResizingSidebar ? 'resizing' : ''}`}
                onPointerDown={handleResizePointerDown}
                title="Drag left or right to expand/resize sidebar"
              >
                <div className="resize-handle-bar" />
              </div>

              {/* Active Disruption Emergency Banner */}
              {simStatus.active_disruptions_data && simStatus.active_disruptions_data.length > 0 && (
                <div className="sidebar-incident-alert-banner">
                  <div className="incident-banner-top">
                    <div className="incident-banner-title">
                      <Flame size={16} className="text-rose animate-pulse" />
                      <span className="incident-badge">ACTIVE NETWORK INCIDENT</span>
                    </div>
                    <button 
                      onClick={handleClearDisruptions}
                      className="btn-clear-incident"
                      title="Clear Disruption"
                    >
                      Clear
                    </button>
                  </div>
                  {simStatus.active_disruptions_data.map((d, i) => (
                    <div key={i} className="incident-item">
                      <div className="incident-item-header">
                        <span className="incident-type-tag">{d.title || d.mode?.replace(/_/g, ' ').toUpperCase()}</span>
                        <span className="incident-delay-tag">+{d.delay_duration_sec || 180}s DELAY</span>
                      </div>
                      <p className="incident-item-desc">{d.description || d.impact || 'Service throttling in progress.'}</p>
                      <div className="incident-actions-row">
                        <button 
                          onClick={() => {
                            const stName = d.station_name || d.station_id || 'City 1 Central';
                            const st = geometry?.stations?.find(s => 
                              s.station_name === stName || 
                              s.display_name === stName ||
                              s.display_name?.includes(stName) ||
                              s.station_name === 'City_1'
                            ) || geometry?.stations?.[0];
                            if (st) {
                              zoomToStation(st);
                              setActiveSideTab('station');
                            }
                          }}
                          className="btn btn-incident-action btn-xs"
                        >
                          <MapPin size={12} /> Zoom to Station
                        </button>
                        {d.vehicle_id && (
                          <button 
                            onClick={() => {
                              const t = trains.find(tr => tr.id === d.vehicle_id);
                              if (t) zoomToTrain(t);
                            }}
                            className="btn btn-incident-action btn-xs"
                          >
                            <Train size={12} /> Focus Train #{d.vehicle_id}
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Tabs */}
              <div className="sidebar-tabs">
                <button 
                  className={`sidebar-tab ${activeSideTab === 'trains' ? 'active' : ''}`}
                  onClick={() => setActiveSideTab('trains')}
                >
                  <Train size={15} />
                  <span>Trains ({trains.length})</span>
                </button>
                <button 
                  className={`sidebar-tab ${activeSideTab === 'station' ? 'active' : ''}`}
                  onClick={() => setActiveSideTab('station')}
                >
                  <MapPin size={15} />
                  <span>Station {selectedStation ? `(${selectedStation.display_name?.split(' ')[0]})` : ''}</span>
                </button>

                <button 
                  onClick={() => setSidebarOpen(false)}
                  className="sidebar-collapse-btn"
                  title="Close Sidebar to the Right"
                >
                  <ChevronRight size={16} />
                </button>
              </div>


          {/* Active Trains Tab */}
          {activeSideTab === 'trains' && (
            <div className="sidebar-tab-content">
              {/* Category Filter Pills */}
              <div className="category-filters">
                {['ALL', 'HighSpeed', 'Regional', 'Freight'].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setCategoryFilter(cat)}
                    className={`cat-filter-btn ${categoryFilter === cat ? 'active' : ''}`}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              {/* Search & Delay Toggle */}
              <div className="search-filter-box">
                <div className="search-input-wrapper">
                  <Search size={14} className="search-input-icon" />
                  <input 
                    type="text" 
                    placeholder="Search train # or name..." 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="sidebar-search-input"
                  />
                </div>
                <label className="delay-filter-toggle">
                  <input 
                    type="checkbox" 
                    checked={delayOnlyFilter} 
                    onChange={(e) => setDelayOnlyFilter(e.target.checked)} 
                  />
                  <span>Delayed Only</span>
                </label>
              </div>

              {/* Train List */}
              <div className="trains-scroll-list">
                {filteredTrains.length === 0 ? (
                  <div className="empty-trains-notice">
                    <span>No active trains matching filter at current simulation time.</span>
                  </div>
                ) : (
                  filteredTrains.map((t) => (
                    <div 
                      key={t.id}
                      onClick={() => {
                        setSelectedTrain(t);
                        zoomToTrain(t);
                      }}
                      className={`train-row-item ${selectedTrain && selectedTrain.id === t.id ? 'active' : ''}`}
                    >
                      <div className="train-row-left">
                        <div className="train-row-id-stack">
                          <span className="train-row-number">
                            {t.train_number ? `Train #${t.train_number}` : `Train #${t.id}`}
                          </span>
                        </div>
                        <span className="train-row-cat">
                          {t.train_name ? `${t.train_name} • ${t.category}` : t.category}
                        </span>
                      </div>
                      <div className="train-row-right">
                        <span className="train-row-speed">{Math.round((t.speed || 0) * 3.6)} km/h</span>
                        <span className={`train-row-delay ${(t.delay_sec || 0) > 0 ? 'delayed' : 'ontime'}`}>
                          {(t.delay_sec || 0) > 0 ? `+${Math.round(t.delay_sec)}s` : 'ON TIME'}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Station Tracks & Disruption Inspector Tab */}
          {activeSideTab === 'station' && (
            <div className="sidebar-tab-content station-tab-content">
              {/* Station Picker Dropdown */}
              <div className="station-selector-box">
                <label className="sidebar-field-label">
                  <Navigation size={13} className="text-cyan" />
                  <span>Select Network Station:</span>
                </label>
                <select 
                  value={selectedStation?.station_name || ''} 
                  onChange={(e) => {
                    const val = e.target.value;
                    if (!val) {
                      resetViewAnimated();
                      return;
                    }
                    const st = geometry?.stations?.find(s => s.station_name === val);
                    if (st) zoomToStation(st);
                  }}
                  className="sidebar-station-select"
                >
                  <option value="">-- Select Station to Inspect --</option>
                  {geometry?.stations?.map(st => (
                    <option key={st.station_name} value={st.station_name}>
                      {st.display_name || st.station_name} ({st.platforms?.length || 2} Platforms)
                    </option>
                  ))}
                </select>
              </div>

              {!selectedStation ? (
                <div className="empty-trains-notice">
                  <MapPin size={32} className="text-cyan animate-pulse" />
                  <span>Select a station from the dropdown above or click any station circle on the map to inspect its tracks &amp; platforms.</span>
                </div>
              ) : (
                <div className="station-inspector-scroll">
                  {/* Station Banner Header */}
                  <div className="station-detail-banner glass-panel">
                    <div className="banner-station-name-row">
                      <div className="banner-title-box">
                        <span className="station-id-tag">STATION {selectedStation.station_name}</span>
                        <h3>{selectedStation.display_name || selectedStation.station_name}</h3>
                      </div>
                      <div className="banner-action-buttons">
                        <button 
                          onClick={() => zoomToStation(selectedStation)} 
                          className="btn-rezoom" 
                          title="Re-center Camera"
                        >
                          <Crosshair size={14} />
                        </button>
                        <button 
                          onClick={() => resetViewAnimated()} 
                          className="btn-rezoom" 
                          title="Clear Station Selection & Reset View"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    </div>
                    <div className="banner-topology-summary">
                      <span className="topo-tag">
                        <ArrowDownRight size={12} className="text-cyan" />
                        {selectedStationTopology.converging.length} Converging Inbound
                      </span>
                      <span className="topo-tag">
                        <ArrowUpRight size={12} className="text-emerald" />
                        {selectedStationTopology.diverging.length} Diverging Outbound
                      </span>
                      <span className="topo-tag">
                        <Layers size={12} className="text-blue" />
                        {selectedStationTopology.platforms.length || selectedStation.platforms?.length || 2} Platform Tracks
                      </span>
                    </div>

                    {/* Live Train Traffic Counts in Sidebar */}
                    <div className="sidebar-traffic-status-strip">
                      <div className="sidebar-traffic-stat">
                        <span className="traffic-dot dot-cyan"></span>
                        <span className="stat-count text-cyan">{selectedStationTrains.approaching.length}</span>
                        <span className="stat-name">Approaching</span>
                      </div>
                      <div className="sidebar-traffic-stat">
                        <span className="traffic-dot dot-amber"></span>
                        <span className="stat-count text-amber">{selectedStationTrains.dwelling.length}</span>
                        <span className="stat-name">Dwelling</span>
                      </div>
                      <div className="sidebar-traffic-stat">
                        <span className="traffic-dot dot-emerald"></span>
                        <span className="stat-count text-emerald">{selectedStationTrains.departing.length}</span>
                        <span className="stat-name">Departing</span>
                      </div>
                    </div>
                  </div>

                  {/* Disruption Abnormal Impact Diagnosis */}
                  {(() => {
                    const activeDisruptions = simStatus.active_disruptions_data || [];
                    const isStationAffected = activeDisruptions.some(d => 
                      d.station_name === selectedStation.display_name || 
                      d.station_id === selectedStation.station_name ||
                      d.mode === 'fleet_surge'
                    );

                    return (
                      <div className={`station-disruption-impact-box ${isStationAffected ? 'active-disruption-impact' : 'nominal-impact'}`}>
                        <div className="impact-box-header">
                          {isStationAffected ? (
                            <>
                              <Flame size={16} className="text-rose animate-pulse" />
                              <span className="impact-header-title text-rose">ABNORMAL IMPACT DIAGNOSIS</span>
                            </>
                          ) : (
                            <>
                              <Activity size={16} className="text-emerald" />
                              <span className="impact-header-title text-emerald">INTERLOCKING NOMINAL STATUS</span>
                            </>
                          )}
                        </div>

                        {activeDisruptions.find(d => d.mode === 'fleet_surge') && (
                          <div className="impact-scenario-item">
                            <span className="scenario-pill pill-amber">FLEET SURGE ACTIVE</span>
                            <p className="scenario-detail">
                              Heavy passenger crowding adds +40% dwell jitter (+75s to +180s) to platform stops. Platforms turn over sluggishly, forcing converging inbound trains to brake early and hold at throat approach signals.
                            </p>
                          </div>
                        )}

                        {activeDisruptions.find(d => d.mode === 'platform_blockage') && (
                          <div className="impact-scenario-item">
                            <span className="scenario-pill pill-rose">PLATFORM CLOSURE ACTIVE</span>
                            <p className="scenario-detail">
                              Platform 1 is locked with red interlocking stop signals. AI Dispatcher is dynamically rerouting converging inbound trains across switch ladders to open platforms.
                            </p>
                          </div>
                        )}

                        {activeDisruptions.find(d => d.mode === 'train_delay') && (
                          <div className="impact-scenario-item">
                            <span className="scenario-pill pill-rose">MECHANICAL BREAKDOWN ACTIVE</span>
                            <p className="scenario-detail">
                              Train is stalled at 0 km/h with an emergency brake lock. Trailing trains on converging tracks are throttled to maintain safety headways.
                            </p>
                          </div>
                        )}

                        {!isStationAffected && (
                          <p className="scenario-detail nominal-text">
                            Interlocking throat signals green. All converging tracks (↗ Inbound) and diverging tracks (↘ Outbound) operating at full design timetable velocity.
                          </p>
                        )}
                      </div>
                    );
                  })()}

                  {/* Platform Bays Status */}
                  <div className="station-section-card">
                    <div className="section-card-title">
                      <Layers size={14} className="text-blue" />
                      <span>Platform Bays ({selectedStation.platforms?.length || 2})</span>
                    </div>
                    <div className="platforms-grid">
                      {(selectedStation.platforms || [
                        { platform_id: `${selectedStation.station_name}_P1`, track: 1, direction: 'fw' },
                        { platform_id: `${selectedStation.station_name}_P2`, track: 2, direction: 'bw' }
                      ]).map((p, idx) => {
                        const isBlocked = simStatus.active_disruptions_data?.some(d => 
                          d.mode === 'platform_blockage' && (d.platform_id === p.platform_id || d.platform_id === selectedStation.station_name)
                        ) || (simStatus.active_disruptions_data?.some(d => d.mode === 'compound_failure') && idx === 0);

                        const dwellingTrain = selectedStationTrains.dwelling.find(t => 
                          t.scheduled_platform === p.platform_id || t.road_id === p.platform_id || idx === 0
                        );

                        return (
                          <div key={p.platform_id || idx} className={`platform-status-card ${isBlocked ? 'platform-blocked' : dwellingTrain ? 'platform-occupied' : 'platform-clear'}`}>
                            <div className="platform-card-top">
                              <span className="platform-name">Track {p.track || idx + 1}</span>
                              <span className={`platform-badge ${isBlocked ? 'badge-blocked' : dwellingTrain ? 'badge-occupied' : 'badge-clear'}`}>
                                {isBlocked ? 'BLOCKED' : dwellingTrain ? 'DWELLING' : 'OPEN'}
                              </span>
                            </div>
                            <div className="platform-card-body">
                              {isBlocked ? (
                                <span className="platform-subtext text-rose">⛔ Barricaded / Rerouting Traffic</span>
                              ) : dwellingTrain ? (
                                <span className="platform-subtext text-amber">
                                  🚆 Train #{dwellingTrain.train_number || dwellingTrain.id} ({Math.round(dwellingTrain.speed_kmh || (dwellingTrain.speed || 0) * 3.6)} km/h • +{Math.round(dwellingTrain.delay_sec || 0)}s)
                                </span>
                              ) : (
                                <span className="platform-subtext text-emerald">Ready for Incoming Train</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Converging Tracks (Inbound ↗) */}
                  <div className="station-section-card">
                    <div className="section-card-title">
                      <ArrowDownRight size={14} className="text-cyan" />
                      <span>↗ Converging Inbound Tracks ({selectedStationTopology.converging.length})</span>
                      <span className="section-pill cyan-pill">APPROACH THROAT</span>
                    </div>
                    <div className="tracks-traffic-list">
                      {selectedStationTrains.approaching.length === 0 ? (
                        <span className="empty-subtext">No trains currently on inbound converging approach blocks.</span>
                      ) : (
                        selectedStationTrains.approaching.map(t => (
                          <div 
                            key={t.id} 
                            onClick={() => zoomToTrain(t)}
                            className="station-train-row converging-row"
                          >
                            <div className="row-left">
                              <span className="row-tag-inbound">↗ INBOUND</span>
                              <span className="row-train-num">Train #{t.train_number || t.id}</span>
                              <span className="row-cat">{t.category}</span>
                            </div>
                            <div className="row-right">
                              <span className="row-speed">{Math.round(t.speed_kmh || (t.speed || 0) * 3.6)} km/h</span>
                              <span className={`row-delay ${(t.delay_sec || 0) > 30 ? 'delay-bad' : 'delay-ok'}`}>
                                {(t.delay_sec || 0) > 0 ? `+${Math.round(t.delay_sec)}s` : 'ON TIME'}
                              </span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Diverging Tracks (Outbound ↘) */}
                  <div className="station-section-card">
                    <div className="section-card-title">
                      <ArrowUpRight size={14} className="text-emerald" />
                      <span>↘ Diverging Outbound Tracks ({selectedStationTopology.diverging.length})</span>
                      <span className="section-pill emerald-pill">DEPARTURE THROAT</span>
                    </div>
                    <div className="tracks-traffic-list">
                      {selectedStationTrains.departing.length === 0 ? (
                        <span className="empty-subtext">No trains currently on outbound diverging departure blocks.</span>
                      ) : (
                        selectedStationTrains.departing.map(t => (
                          <div 
                            key={t.id} 
                            onClick={() => zoomToTrain(t)}
                            className="station-train-row diverging-row"
                          >
                            <div className="row-left">
                              <span className="row-tag-outbound">↘ OUTBOUND</span>
                              <span className="row-train-num">Train #{t.train_number || t.id}</span>
                              <span className="row-cat">{t.category}</span>
                            </div>
                            <div className="row-right">
                              <span className="row-speed">{Math.round(t.speed_kmh || (t.speed || 0) * 3.6)} km/h</span>
                              <span className={`row-delay ${(t.delay_sec || 0) > 30 ? 'delay-bad' : 'delay-ok'}`}>
                                {(t.delay_sec || 0) > 0 ? `+${Math.round(t.delay_sec)}s` : 'ON TIME'}
                              </span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Quick Station Switcher */}
                  <div className="quick-stations-box">
                    <span className="quick-stations-title">Quick Jump to Major Hubs:</span>
                    <div className="quick-stations-chips">
                      {geometry?.stations?.slice(0, 6).map(st => (
                        <button
                          key={st.station_name}
                          onClick={() => zoomToStation(st)}
                          className={`quick-chip ${selectedStation?.station_name === st.station_name ? 'active' : ''}`}
                        >
                          {st.display_name?.split(' ')[0] || st.station_name}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}


          </>
          )}
        </aside>

        {/* Floating Sidebar Reopen Tab on Canvas Right Edge */}
        {!sidebarOpen && (
          <button 
            onClick={() => setSidebarOpen(true)}
            className="floating-sidebar-reopen-btn glass-panel"
            title="Expand Dispatcher Sidebar"
          >
            <ChevronLeft size={16} className="text-cyan animate-pulse" />
            <span>Sidebar</span>
          </button>
        )}
      </div>



      {/* Day Completion Summary Modal */}
      {simStatus.day_completed && !dayCompletionDismissed && (
        <div className="modal-backdrop day-completed-backdrop">
          <div className="modal-content glass-panel day-completed-card">
            <div className="modal-header day-completed-header">
              <div className="day-completed-title-box">
                <CheckCircle2 size={24} className="text-emerald animate-pulse" />
                <div>
                  <span className="day-completed-badge">24-HOUR OPERATIONAL CYCLE COMPLETE</span>
                  <h3>
                    {simStatus.current_day === 'Mon' ? 'Monday' : 
                     simStatus.current_day === 'Tue' ? 'Tuesday' :
                     simStatus.current_day === 'Wed' ? 'Wednesday' :
                     simStatus.current_day === 'Thu' ? 'Thursday' :
                     simStatus.current_day === 'Fri' ? 'Friday' :
                     simStatus.current_day === 'Sat' ? 'Saturday' : 'Sunday'} Timetable Finished
                  </h3>
                </div>
              </div>
              <button 
                onClick={() => setDayCompletionDismissed(true)} 
                className="btn-modal-close"
                title="Dismiss & Inspect Finished Network"
              >
                <X size={18} />
              </button>
            </div>

            <div className="day-completed-body">
              <p className="day-completed-desc">
                The simulation has reached the end of the 24-hour service timetable (<strong>06:00:00 → 06:00:00</strong>) and automatically paused. Here is the operational performance summary for the day:
              </p>

              <div className="day-completed-stats-grid">
                <div className="day-stat-box glass-panel">
                  <span className="day-stat-lbl">Network Punctuality</span>
                  <span className="day-stat-val text-emerald">
                    {(kpis.daily_summary?.punctuality_pct ?? kpis.punctuality_pct ?? 100.0).toFixed(1)}%
                  </span>
                  <span className="day-stat-sub">Arrived within 3 min tolerance</span>
                </div>
                <div className="day-stat-box glass-panel">
                  <span className="day-stat-lbl">Average Fleet Delay</span>
                  <span className="day-stat-val text-amber">
                    {(kpis.daily_summary?.mean_delay_sec ?? kpis.avg_delay_sec ?? 0.0).toFixed(1)}s
                  </span>
                  <span className="day-stat-sub">Across all corridors</span>
                </div>
                <div className="day-stat-box glass-panel">
                  <span className="day-stat-lbl">Active Dispatcher</span>
                  <span className="day-stat-val text-cyan">
                    {(kpis.daily_summary?.dispatcher_model || simStatus.current_model || 'Centralized PPO').replace(/_/g, ' ')}
                  </span>
                  <span className="day-stat-sub">Lead Decision Agent</span>
                </div>
                <div className="day-stat-box glass-panel">
                  <span className="day-stat-lbl">AI Interventions</span>
                  <span className="day-stat-val text-blue">
                    {kpis.daily_summary?.total_actions_taken ?? kpis.total_actions_taken ?? 0}
                  </span>
                  <span className="day-stat-sub">Routing & headway locks</span>
                </div>
              </div>

              <div className="day-completed-actions-row">
                <button 
                  onClick={() => {
                    setDayCompletionDismissed(false);
                    sendControl('reset');
                  }} 
                  className="btn btn-secondary"
                >
                  <RotateCcw size={15} />
                  <span>Replay Same Day (06:00)</span>
                </button>
                <button 
                  onClick={() => {
                    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
                    const idx = days.indexOf(simStatus.current_day || 'Mon');
                    const nextDay = days[(idx + 1) % days.length];
                    setDayCompletionDismissed(false);
                    handleConfigChange(nextDay, simStatus.current_model);
                  }} 
                  className="btn btn-primary"
                >
                  <span>Advance to Next Day ({(() => {
                    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
                    const idx = days.indexOf(simStatus.current_day || 'Mon');
                    return days[(idx + 1) % days.length];
                  })()})</span>
                  <ArrowRight size={15} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
