import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  FastForward, 
  AlertTriangle, 
  Sliders, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Radio, 
  Clock, 
  Search, 
  Train, 
  X,
  ChevronRight,
  Send,
  RefreshCw,
  CheckCircle2,
  GitFork,
  Zap,
  ShieldCheck
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
  { id: 'Static_Baseline', label: 'Static Baseline (SUMO Native)' }
];

const TIME_JUMPS = [
  { label: '06:00 Dawn', sec: 21600 },
  { label: '07:30 Peak', sec: 27000 },
  { label: '12:00 Midday', sec: 43200 },
  { label: '17:30 Rush', sec: 63000 }
];

export default function SimulationPage() {
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
    active_overrides: {}
  });

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
  const [events, setEvents] = useState([]);

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
  const [showDisruptionModal, setShowDisruptionModal] = useState(false);
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [activeSideTab, setActiveSideTab] = useState('trains'); // 'trains' | 'events'

  // Disruption Form
  const [disruptionForm, setDisruptionForm] = useState({
    mode: 'fleet_surge',
    vehicle_id: '',
    platform_id: '',
    delay_duration_sec: 180
  });

  // Override Form
  const [overrideForm, setOverrideForm] = useState({
    vehicle_id: '',
    override_type: 'departure_hold',
    target_platform: 1,
    hold_duration_sec: 60
  });

  // Filtered Trains computed for both Canvas & Sidebar
  const filteredTrains = React.useMemo(() => {
    return trains.filter(t => {
      if (categoryFilter !== 'ALL' && t.category !== categoryFilter) return false;
      if (delayOnlyFilter && (!t.delay_sec || t.delay_sec <= 0)) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const num = String(t.train_number || t.id).toLowerCase();
        if (!num.includes(q)) return false;
      }
      return true;
    });
  }, [trains, categoryFilter, delayOnlyFilter, searchQuery]);

  // Canvas Refs
  const canvasRef = useRef(null);
  const transformRef = useRef({ scale: 0.03, offsetX: 100, offsetY: 100 });
  const isDraggingRef = useRef(false);
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

  // 1. Fetch Network Geometry on Mount
  useEffect(() => {
    let mounted = true;
    const fetchGeometry = async () => {
      try {
        const res = await fetch('/api/network/geometry');
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
      const res = await fetch('/api/sim/status');
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
          active_overrides: data.active_overrides ?? prev.active_overrides ?? {}
        }));
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
    // Use current host so Vite proxy forwards to backend
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;
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
              setKpis({
                active_trains: incomingKpis.active_trains_count ?? incomingKpis.active_trains ?? 0,
                punctuality_pct: incomingKpis.punctuality_pct ?? 100.0,
                avg_delay_sec: incomingKpis.mean_delay_sec ?? incomingKpis.avg_delay_sec ?? 0.0,
                max_delay_sec: incomingKpis.max_delay_sec ?? 0.0,
                platform_utilization_pct: incomingKpis.platform_utilization_pct ?? 28.5,
                throughput_tph: incomingKpis.throughput_tph ?? 18.0
              });
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
                  active_overrides: data.active_overrides || prev.active_overrides || {}
                };
              });
            }

            // Ingest recent AI actions
            const incomingActions = data.recent_actions || data.recent_events;
            if (Array.isArray(incomingActions) && incomingActions.length > 0) {
              setEvents(incomingActions);
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
  }, []);

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

    // 1. Draw Track Lanes
    if (geometry && geometry.lanes) {
      for (let i = 0; i < geometry.lanes.length; i++) {
        const lane = geometry.lanes[i];
        const coords = lane.coordinates || lane.shape;
        if (!coords || coords.length < 2) continue;

        const cat = lane.category || 'connector';
        const isHighSpeed = cat === 'high_speed';
        const isPlatform = cat === 'platform';
        const isCrossover = cat === 'crossover';
        const isPassingLoop = cat === 'passing_loop' || cat === 'pocket';
        const isYard = cat === 'yard' || cat === 'depot';

        ctx.beginPath();
        ctx.moveTo(coords[0][0], toCanvasY(coords[0][1]));
        for (let j = 1; j < coords.length; j++) {
          ctx.lineTo(coords[j][0], toCanvasY(coords[j][1]));
        }

        if (isPlatform) {
          // Amber Platform Track
          ctx.strokeStyle = '#291800';
          ctx.lineWidth = 14 / scale;
          ctx.stroke();
          ctx.strokeStyle = '#f59e0b';
          ctx.lineWidth = 5.5 / scale;
          ctx.stroke();
          ctx.strokeStyle = '#fef08a';
          ctx.lineWidth = 1.8 / scale;
          ctx.stroke();
        } else if (isHighSpeed) {
          // Electric Neon Cyan High-Speed Mainline
          ctx.strokeStyle = '#07162c';
          ctx.lineWidth = 10 / scale;
          ctx.stroke();
          ctx.strokeStyle = '#0284c7';
          ctx.lineWidth = 5 / scale;
          ctx.stroke();
          ctx.strokeStyle = '#38bdf8';
          ctx.lineWidth = 2.2 / scale;
          ctx.stroke();
        } else if (isCrossover) {
          // Scissors X-Crossover (Indigo/Violet)
          ctx.strokeStyle = '#1e1b4b';
          ctx.lineWidth = 7 / scale;
          ctx.stroke();
          ctx.strokeStyle = '#818cf8';
          ctx.lineWidth = 3 / scale;
          ctx.stroke();
        } else if (isPassingLoop) {
          // Siding / Overtake Loop (Teal)
          ctx.strokeStyle = '#042f2e';
          ctx.lineWidth = 7 / scale;
          ctx.stroke();
          ctx.strokeStyle = '#2dd4bf';
          ctx.lineWidth = 2.8 / scale;
          ctx.stroke();
        } else if (isYard) {
          // Staging Yard / Siding (Muted Slate)
          ctx.strokeStyle = '#334155';
          ctx.lineWidth = 2.5 / scale;
          ctx.stroke();
        } else {
          // Standard Mainline / Intercity Trunk (Deep Blue/Cyan)
          ctx.strokeStyle = '#0a101d';
          ctx.lineWidth = 7 / scale;
          ctx.stroke();
          ctx.strokeStyle = '#0369a1';
          ctx.lineWidth = 2.5 / scale;
          ctx.stroke();
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

        // Check if this station is impacted by platform blockage or compound failure
        const isDisruptedStation = activeDisruptionsData.some(d => {
          if (d.mode !== 'platform_blockage' && d.mode !== 'compound_failure') return false;
          if (d.platform_id && (d.platform_id.includes(st.station_name) || st.station_name.includes(d.platform_id))) return true;
          if (d.station_name && st.display_name && (d.station_name.toLowerCase() === st.display_name.toLowerCase())) return true;
          if (st.platforms && st.platforms.some(p => p.platform_id === d.platform_id || p.lane === d.platform_id)) return true;
          return false;
        });

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

        // Station Name Pill Badge
        const name = st.display_name || st.station_name || 'Station';
        const fontSize = (isCity ? 11 : 9.5) / scale;
        ctx.font = `600 ${fontSize}px Inter, system-ui, sans-serif`;
        const textMetrics = ctx.measureText(name);
        const textWidth = textMetrics.width;
        const padX = 6 / scale;
        const padY = 3 / scale;
        const badgeH = fontSize + padY * 2;
        const badgeW = textWidth + padX * 2;
        const badgeX = sx - badgeW / 2;
        const badgeY = sy - hubRadius * 1.6 - badgeH - (4 / scale);

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

      const trainLen = (isFreight ? 38 : isHighSpeed ? 34 : 26) / scale;
      const trainWidth = (isFreight ? 10 : 8) / scale;

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
      const trainLabel = `${train.id} • ${speedKmh} km/h`;
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

      // Floating Badges above Train for Disruptions or Overrides
      if (isDisruptedTrain) {
        const disLabel = '⚠️ MECHANICAL STALL • 0 km/h';
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
        const bannerW = Math.min(width - 32, 580);
        const bannerH = 34;
        const bannerX = (width - bannerW) / 2;
        const firstD = activeDisruptionsData[0];
        const modeLabel = firstD.mode ? firstD.mode.replace('_', ' ').toUpperCase() : 'INCIDENT';
        const targetText = firstD.station_name || firstD.vehicle_id || firstD.platform_id || 'Network';
        const bannerText = `🚨 ACTIVE DISRUPTION: ${modeLabel} @ ${targetText} • AI Dynamic Rerouting Engaged`;

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
  }, [geometry, filteredTrains, selectedTrain, simStatus.active_disruptions_data, simStatus.active_overrides]);

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
    dragStartRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
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
    const newScale = Math.min(Math.max(currentScale * zoomFactor, 0.005), 0.5);

    transformRef.current.offsetX = mouseX - (mouseX - transformRef.current.offsetX) * (newScale / currentScale);
    transformRef.current.offsetY = mouseY - (mouseY - transformRef.current.offsetY) * (newScale / currentScale);
    transformRef.current.scale = newScale;
  };

  const zoomIn = () => {
    transformRef.current.scale = Math.min(transformRef.current.scale * 1.3, 0.5);
  };
  const zoomOut = () => {
    transformRef.current.scale = Math.max(transformRef.current.scale * 0.7, 0.005);
  };
  const resetView = () => {
    if (geometry && geometry.bounds && canvasRef.current) {
      const cWidth = canvasRef.current.clientWidth || 1000;
      const cHeight = canvasRef.current.clientHeight || 700;
      transformRef.current = getCenteredTransform(geometry.bounds, cWidth, cHeight);
    }
  };

  // Click on Canvas to Select Nearest Train or Station
  const handleCanvasClick = (e) => {
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

    let closest = null;
    let minDist = 35 / scale; // click tolerance in world coordinates

    for (const t of filteredTrains) {
      const dist = Math.hypot(t.x - worldX, t.y - worldY);
      if (dist < minDist) {
        minDist = dist;
        closest = t;
      }
    }
    setSelectedTrain(closest);
  };

  // Playback Control Handlers
  const sendControl = useCallback(async (action, speed, reqId) => {
    const targetSpeed = speed !== undefined ? speed : (selectedSpeedRef.current ?? confirmedSpeedRef.current ?? simStatus.speed_multiplier ?? 1.0);
    const currentReqId = reqId !== undefined ? reqId : (action === 'set_speed' || speed !== undefined ? ++speedRequestIdRef.current : undefined);
    try {
      if (action === 'set_speed') {
        const res = await fetch('/api/sim/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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
        const res = await fetch('/api/sim/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, speed: targetSpeed })
        });
        if (res.ok && speed !== undefined) {
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
      await fetch('/api/sim/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ day, model })
      });
      setSelectedDay(day);
      setSelectedModel(model);
      fetchStatus();
    } catch (err) {
      console.error('Config change error:', err);
    }
  };

  // Quick Time Jump Handler (Dawn, Morning Peak, Midday, Evening Rush)
  const handleTimeJump = async (sec) => {
    const initialSpeed = selectedSpeedRef.current ?? confirmedSpeedRef.current ?? simStatus.speed_multiplier ?? 1.0;
    try {
      const res = await fetch('/api/sim/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          day: selectedDay,
          model: selectedModel,
          speed: initialSpeed,
          start_time_sec: sec
        })
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.success) {
          // Re-read current speed selection after time-jump completes
          // so any speed change made while the request was pending is preserved
          const currentSpeed = selectedSpeedRef.current ?? confirmedSpeedRef.current ?? simStatus.speed_multiplier ?? 1.0;
          const reqId = ++speedRequestIdRef.current;
          speedQueueRef.current = speedQueueRef.current.then(async () => {
            await sendControl('play', currentSpeed, reqId);
          }).catch(err => {
            console.error('Time jump playback error:', err);
          });
          await speedQueueRef.current;
        }
      }
      fetchStatus();
    } catch (err) {
      console.error('Time jump error:', err);
    }
  };

  // Inject Disruption Handler
  const handleInjectDisruption = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        mode: disruptionForm.mode,
        vehicle_id: disruptionForm.vehicle_id || undefined,
        platform_id: disruptionForm.platform_id || undefined,
        delay_duration_sec: Number(disruptionForm.delay_duration_sec)
      };
      const res = await fetch('/api/disruption/inject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => null);
      if (data?.active_disruptions_data) {
        setSimStatus(prev => ({
          ...prev,
          active_disruptions: data.active_disruptions || prev.active_disruptions,
          active_disruptions_data: data.active_disruptions_data
        }));
      }
      if (data?.recent_actions) {
        setEvents(data.recent_actions);
      }
      setShowDisruptionModal(false);
      setActiveSideTab('events');
      fetchStatus();
    } catch (err) {
      console.error('Disruption injection error:', err);
    }
  };

  // Clear Disruptions
  const handleClearDisruptions = async () => {
    try {
      await fetch('/api/disruption/clear', { method: 'POST' });
      setSimStatus(prev => ({
        ...prev,
        active_disruptions: [],
        active_disruptions_data: []
      }));
      setShowDisruptionModal(false);
      setActiveSideTab('events');
      fetchStatus();
    } catch (err) {
      console.error('Clear disruptions error:', err);
    }
  };

  // Manual Override Handler
  const handleApplyOverride = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        vehicle_id: overrideForm.vehicle_id,
        override_type: overrideForm.override_type,
        target_platform: overrideForm.target_platform ? Number(overrideForm.target_platform) : undefined,
        hold_duration_sec: overrideForm.hold_duration_sec ? Number(overrideForm.hold_duration_sec) : undefined
      };
      const res = await fetch('/api/override/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => null);
      if (data?.active_overrides) {
        setSimStatus(prev => ({
          ...prev,
          active_overrides: data.active_overrides
        }));
      }
      if (data?.recent_actions) {
        setEvents(data.recent_actions);
      }
      setShowOverrideModal(false);
      setActiveSideTab('events');
      fetchStatus();
    } catch (err) {
      console.error('Override action error:', err);
    }
  };

  // Human-formatted AI / Dispatcher Event Card Renderer (NO raw JSON)
  const renderEventCard = (ev, idx) => {
    let rawMsg = ev.details || ev.message;
    if (typeof rawMsg === 'object' && rawMsg !== null) {
      rawMsg = rawMsg.details || rawMsg.message || rawMsg.desc || JSON.stringify(rawMsg);
    }
    let cleanText = String(rawMsg || '');
    if (cleanText.startsWith('{') && cleanText.endsWith('}')) {
      try {
        const parsed = JSON.parse(cleanText.replace(/'/g, '"'));
        cleanText = parsed.details || parsed.message || parsed.desc || `${parsed.type || 'Dispatch decision'}`;
      } catch {
        const match = cleanText.match(/'(?:details|desc)':\s*'([^']+)'/);
        if (match) cleanText = match[1];
      }
    }

    const typeStr = String(ev.action_type || ev.type || 'DISPATCH_ACTION').toLowerCase();
    const vid = ev.vehicle_id || ev.vid || '';

    let severity = ev.severity || 'info';
    let icon = <CheckCircle2 size={14} />;
    let badgeLabel = ev.title || 'DISPATCH EVENT';

    if (typeStr.includes('disruption') || typeStr.includes('incident') || typeStr.includes('stall') || typeStr.includes('blockage') || severity === 'danger') {
      severity = 'danger';
      icon = <AlertTriangle size={14} />;
      badgeLabel = ev.title || 'DISRUPTION INCIDENT';
    } else if (typeStr.includes('manual') || typeStr.includes('override') || severity === 'purple') {
      severity = 'purple';
      icon = <Sliders size={14} />;
      badgeLabel = ev.title || 'OPERATOR OVERRIDE';
    } else if (typeStr.includes('reroute') || typeStr.includes('reassigned') || typeStr.includes('divert') || typeStr.includes('switch')) {
      severity = 'cyan';
      icon = <GitFork size={14} />;
      badgeLabel = ev.title || 'AI REROUTE ADVISORY';
    } else if (typeStr.includes('hold') || typeStr.includes('delay') || severity === 'warning' || severity === 'amber') {
      severity = 'amber';
      icon = <Clock size={14} />;
      badgeLabel = ev.title || 'HEADWAY HOLD';
    } else if (typeStr.includes('speed') || typeStr.includes('bypass')) {
      severity = 'emerald';
      icon = <Zap size={14} />;
      badgeLabel = ev.title || 'SPEED PROFILING';
    } else if (typeStr.includes('headway') || typeStr.includes('nominal') || typeStr.includes('lock')) {
      severity = 'emerald';
      icon = <ShieldCheck size={14} />;
      badgeLabel = ev.title || 'HEADWAY LOCK';
    }

    const timeStr = ev.timestamp || ev.time_formatted || '06:00:00';
    const modelStr = ev.dispatcher_model || simStatus.current_model || 'Centralized PPO';

    return (
      <div key={ev.id || idx} className={`event-card event-card-${severity}`}>
        <div className="event-card-header">
          <div className="event-card-badge-row">
            <span className={`event-category-badge badge-${severity}`}>
              {icon}
              <span>{badgeLabel}</span>
            </span>
            {vid && vid !== 'Fleet' && vid !== 'Infrastructure' && vid !== 'Network' && vid !== 'Signals' && (
              <span className="event-train-tag">#{vid}</span>
            )}
          </div>
          <span className="event-time-pill">{timeStr}</span>
        </div>

        <p className="event-card-body">{cleanText || 'Nominal headway synchronization verified.'}</p>

        <div className="event-card-footer">
          <span className="event-model-tag">
            {severity === 'purple' ? '👤 ' : '🤖 '}
            {modelStr.replace(/_/g, ' ')}
          </span>
        </div>
      </div>
    );
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
              onClick={() => sendControl('step')} 
              className="btn btn-hud" 
              title="Step Single Tick (15s)"
            >
              <ChevronRight size={18} />
              <span>Step</span>
            </button>

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
            {[1, 2, 5, 10, 20].map((s) => (
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

          {/* Quick Scenario Time-Jump Pills */}
          <div className="hud-timejumps">
            <span className="hud-select-label">Jump:</span>
            {TIME_JUMPS.map((jump) => (
              <button
                key={jump.label}
                onClick={() => handleTimeJump(jump.sec)}
                className="btn-timejump-pill"
                title={`Jump to ${jump.label}`}
              >
                {jump.label}
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
        </div>

        {/* HUD Right Actions */}
        <div className="hud-right-group">
          <button 
            onClick={() => setShowDisruptionModal(true)} 
            className="btn btn-secondary btn-hud-alert"
          >
            <AlertTriangle size={15} />
            <span>Inject Disruption</span>
            {simStatus.active_disruptions && simStatus.active_disruptions.length > 0 && (
              <span className="badge badge-disruptions-count">
                {simStatus.active_disruptions.length}
              </span>
            )}
          </button>

          <button 
            onClick={() => {
              if (selectedTrain) setOverrideForm(prev => ({ ...prev, vehicle_id: selectedTrain.id }));
              setShowOverrideModal(true);
            }} 
            className="btn btn-secondary btn-hud-override"
          >
            <Sliders size={15} />
            <span>Manual Override</span>
          </button>
        </div>
      </div>

      {/* Main Simulation Viewport */}
      <div className="sim-viewport-container">
        {/* HTML5 Canvas */}
        <div className="canvas-wrapper">
          {loadingGeometry && (
            <div className="canvas-loader-overlay">
              <RefreshCw size={36} className="loader-spin" />
              <span>Parsing 776 Network Lanes & Platform Topology...</span>
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
              <span className={`sim-state-chip ${simStatus.running && !simStatus.paused ? 'chip-live' : 'chip-paused'}`}>
                {simStatus.running && !simStatus.paused ? 'RUNNING' : 'PAUSED'}
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

          {/* Selected Train Inspector Modal/Card */}
          {selectedTrain && (
            <div className="selected-train-card glass-panel">
              <div className="selected-train-header">
                <div className="selected-train-title">
                  <Train size={18} className="selected-train-icon" />
                  <h4>Train #{selectedTrain.train_number || selectedTrain.id}</h4>
                  <span className={`badge badge-category-${selectedTrain.category === 'HighSpeed' ? 'hs' : selectedTrain.category === 'Regional' ? 'reg' : 'frt'}`}>
                    {selectedTrain.category || 'Train'}
                  </span>
                </div>
                <button onClick={() => setSelectedTrain(null)} className="btn-close-train">
                  <X size={16} />
                </button>
              </div>

              <div className="selected-train-details">
                <div className="detail-row">
                  <span className="detail-lbl">Current Speed:</span>
                  <span className="detail-val">{Math.round((selectedTrain.speed || 0) * 3.6)} km/h</span>
                </div>
                <div className="detail-row">
                  <span className="detail-lbl">Current Delay:</span>
                  <span className={`detail-val ${(selectedTrain.delay_sec || 0) > 0 ? 'text-rose' : 'text-emerald'}`}>
                    +{(selectedTrain.delay_sec || 0).toFixed(1)} sec
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-lbl">Platform / Edge:</span>
                  <span className="detail-val">{selectedTrain.scheduled_platform || selectedTrain.road_id || 'In-Transit'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-lbl">Upcoming Station:</span>
                  <span className="detail-val text-cyan">{selectedTrain.upcoming_station || 'Terminal Line'}</span>
                </div>
              </div>

              <div className="selected-train-actions">
                <button 
                  onClick={() => {
                    setOverrideForm(prev => ({ ...prev, vehicle_id: selectedTrain.id }));
                    setShowOverrideModal(true);
                  }}
                  className="btn btn-secondary btn-sm"
                >
                  <Sliders size={14} />
                  <span>Override Train</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Dispatcher Control Panel */}
        <aside className="sim-sidebar glass-panel">
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
              className={`sidebar-tab ${activeSideTab === 'events' ? 'active' : ''}`}
              onClick={() => setActiveSideTab('events')}
            >
              <Radio size={15} />
              <span>AI Events ({events.length})</span>
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
                    placeholder="Search train ID..." 
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
                    <button onClick={() => sendControl('play')} className="btn btn-secondary btn-sm">
                      <Play size={14} /> Run Time Forward
                    </button>
                  </div>
                ) : (
                  filteredTrains.map((t) => (
                    <div 
                      key={t.id}
                      onClick={() => {
                        setSelectedTrain(t);
                        // Center camera on train
                        if (canvasRef.current && geometry && geometry.bounds) {
                          const [, minY, , maxY] = geometry.bounds;
                          const cWidth = canvasRef.current.clientWidth;
                          const cHeight = canvasRef.current.clientHeight;
                          const { scale } = transformRef.current;
                          const screenTrainX = t.x;
                          const screenTrainY = maxY - t.y + minY;
                          transformRef.current.offsetX = cWidth / 2 - screenTrainX * scale;
                          transformRef.current.offsetY = cHeight / 2 - screenTrainY * scale;
                        }
                      }}
                      className={`train-row-item ${selectedTrain && selectedTrain.id === t.id ? 'active' : ''}`}
                    >
                      <div className="train-row-left">
                        <span className="train-row-number">#{t.train_number || t.id}</span>
                        <span className="train-row-cat">{t.category}</span>
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

          {/* Real-Time Events Tab */}
          {activeSideTab === 'events' && (
            <div className="sidebar-tab-content events-tab-content">
              <div className="events-header-bar">
                <div className="events-live-pill">
                  <span className="live-dot pulse"></span>
                  <span>AI DECISION STREAM</span>
                </div>
                <span className="events-count-pill">{events.length} Actions</span>
              </div>

              {events.length === 0 ? (
                <div className="empty-events-notice">
                  <Radio size={28} className="empty-events-icon pulse" />
                  <p>Monitoring dispatcher decision feed...</p>
                  <span>Routine AI synchronization events and disruption advisories will appear here in real time.</span>
                </div>
              ) : (
                <div className="events-scroll-list">
                  {events.map((ev, idx) => renderEventCard(ev, idx))}
                </div>
              )}
            </div>
          )}
        </aside>
      </div>

      {/* Disruption Injection Modal */}
      {showDisruptionModal && (
        <div className="modal-backdrop">
          <div className="modal-content glass-panel">
            <div className="modal-header">
              <div className="modal-title-row">
                <AlertTriangle size={20} className="modal-icon-alert" />
                <h3>Inject Network Disruption</h3>
              </div>
              <button onClick={() => setShowDisruptionModal(false)} className="btn-modal-close"><X size={18} /></button>
            </div>

            <form onSubmit={handleInjectDisruption} className="modal-form">
              <div className="form-group">
                <label>Disruption Scenario:</label>
                <select 
                  value={disruptionForm.mode} 
                  onChange={(e) => setDisruptionForm(prev => ({ ...prev, mode: e.target.value }))}
                  className="modal-select"
                >
                  <option value="fleet_surge">Fleet Surge (Dwell Jitter)</option>
                  <option value="train_delay">Train Breakdown / Mechanical Stall</option>
                  <option value="platform_blockage">Platform Track Closure</option>
                  <option value="compound_failure">Compound Failure (Breakdown + Closure)</option>
                </select>
              </div>

              <div className="form-group">
                <label>Delay Duration (Seconds):</label>
                <input 
                  type="number" 
                  min="10" 
                  max="1800" 
                  value={disruptionForm.delay_duration_sec}
                  onChange={(e) => setDisruptionForm(prev => ({ ...prev, delay_duration_sec: e.target.value }))}
                  className="modal-input"
                />
              </div>

              {disruptionForm.mode === 'train_delay' && (
                <div className="form-group">
                  <label>Target Train:</label>
                  <select 
                    value={disruptionForm.vehicle_id}
                    onChange={(e) => setDisruptionForm(prev => ({ ...prev, vehicle_id: e.target.value }))}
                    className="modal-select"
                  >
                    <option value="">-- Auto-select leading train --</option>
                    {filteredTrains.map(t => (
                      <option key={t.id} value={t.id}>
                        #{t.train_number || t.id} ({t.category} • {Math.round(t.speed_kmh || (t.speed || 0) * 3.6)} km/h)
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {disruptionForm.mode === 'platform_blockage' && (
                <div className="form-group">
                  <label>Target Station & Platform Track:</label>
                  <select 
                    value={disruptionForm.platform_id}
                    onChange={(e) => setDisruptionForm(prev => ({ ...prev, platform_id: e.target.value }))}
                    className="modal-select"
                  >
                    <option value="">-- City 1 Central (Track 1) --</option>
                    {geometry?.stations?.map(st => (
                      <optgroup key={st.station_name} label={st.display_name || st.station_name}>
                        <option value={st.station_name}>
                          {st.display_name} - All Platforms
                        </option>
                        {st.platforms?.map(p => (
                          <option key={p.platform_id} value={p.platform_id}>
                            {st.display_name} - Track {p.track} ({p.direction.toUpperCase()})
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>
              )}

              {disruptionForm.mode === 'compound_failure' && (
                <>
                  <div className="form-group">
                    <label>Target Train (Breakdown):</label>
                    <select 
                      value={disruptionForm.vehicle_id}
                      onChange={(e) => setDisruptionForm(prev => ({ ...prev, vehicle_id: e.target.value }))}
                      className="modal-select"
                    >
                      <option value="">-- Auto-select leading train --</option>
                      {filteredTrains.map(t => (
                        <option key={t.id} value={t.id}>
                          #{t.train_number || t.id} ({t.category})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Target Station & Track (Closure):</label>
                    <select 
                      value={disruptionForm.platform_id}
                      onChange={(e) => setDisruptionForm(prev => ({ ...prev, platform_id: e.target.value }))}
                      className="modal-select"
                    >
                      <option value="">-- City 1 Central (Track 1) --</option>
                      {geometry?.stations?.map(st => (
                        <optgroup key={st.station_name} label={st.display_name || st.station_name}>
                          <option value={st.station_name}>{st.display_name} - All Tracks</option>
                          {st.platforms?.map(p => (
                            <option key={p.platform_id} value={p.platform_id}>
                              {st.display_name} - Track {p.track} ({p.direction.toUpperCase()})
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                </>
              )}

              <div className="modal-actions">
                <button type="button" onClick={handleClearDisruptions} className="btn btn-secondary">
                  Clear All Incidents
                </button>
                <button type="submit" className="btn btn-danger">
                  Inject Disruption
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manual Override Modal */}
      {showOverrideModal && (
        <div className="modal-backdrop">
          <div className="modal-content glass-panel">
            <div className="modal-header">
              <div className="modal-title-row">
                <Sliders size={20} className="modal-icon-override" />
                <h3>Manual Dispatcher Override (HITL)</h3>
              </div>
              <button onClick={() => setShowOverrideModal(false)} className="btn-modal-close"><X size={18} /></button>
            </div>

            <form onSubmit={handleApplyOverride} className="modal-form">
              <div className="form-group">
                <label>Target Train:</label>
                <select 
                  required
                  value={overrideForm.vehicle_id}
                  onChange={(e) => setOverrideForm(prev => ({ ...prev, vehicle_id: e.target.value }))}
                  className="modal-select"
                >
                  <option value="">-- Select train to override --</option>
                  {filteredTrains.map(t => (
                    <option key={t.id} value={t.id}>
                      #{t.train_number || t.id} ({t.category} • {Math.round(t.speed_kmh || (t.speed || 0) * 3.6)} km/h)
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Override Action:</label>
                <select 
                  value={overrideForm.override_type} 
                  onChange={(e) => setOverrideForm(prev => ({ ...prev, override_type: e.target.value }))}
                  className="modal-select"
                >
                  <option value="departure_hold">Hold Train at Station / Signal</option>
                  <option value="platform_switch">Switch Platform Track (1..6)</option>
                  <option value="bypass_divert">Bypass / Passing Loop Divert</option>
                  <option value="release_hold">Release Active Hold Immediately</option>
                </select>
              </div>

              {overrideForm.override_type === 'departure_hold' && (
                <div className="form-group">
                  <label>Hold Duration (seconds):</label>
                  <input 
                    type="number" 
                    min="10" 
                    max="600" 
                    value={overrideForm.hold_duration_sec}
                    onChange={(e) => setOverrideForm(prev => ({ ...prev, hold_duration_sec: e.target.value }))}
                    className="modal-input"
                  />
                </div>
              )}

              {overrideForm.override_type === 'platform_switch' && (
                <div className="form-group">
                  <label>Target Platform Number (1..6):</label>
                  <input 
                    type="number" 
                    min="1" 
                    max="6" 
                    value={overrideForm.target_platform}
                    onChange={(e) => setOverrideForm(prev => ({ ...prev, target_platform: e.target.value }))}
                    className="modal-input"
                  />
                </div>
              )}

              <div className="modal-actions">
                <button type="button" onClick={() => setShowOverrideModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  <Send size={15} />
                  <span>Execute Override</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
