import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  FastForward, 
  Volume2, 
  AlertTriangle, 
  Sliders, 
  Filter, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Radio, 
  ShieldAlert, 
  Compass, 
  Clock, 
  Layers, 
  Search, 
  Train, 
  X,
  ChevronRight,
  Send,
  Eye,
  MapPin,
  RefreshCw,
  Gauge
} from 'lucide-react';
import './SimulationPage.css';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const MODELS = [
  { id: 'Centralized_PPO', label: 'Centralized PPO (Lead AI)' },
  { id: 'MAPPO', label: 'MAPPO Multi-Agent' },
  { id: 'Decentralized_DQN', label: 'Decentralized DQN' },
  { id: 'Dynamic_Priority_Heuristic', label: 'Dynamic Priority' },
  { id: 'Priority_Heuristic', label: 'Priority Heuristic' },
  { id: 'Rule_Based_FIFO', label: 'Rule-Based FIFO' },
  { id: 'First_Come_First_Served', label: 'First-Come First-Served' },
  { id: 'SUMO_Default', label: 'SUMO Default (No Dispatcher)' }
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
    active_disruptions: []
  });

  // Telemetry stream
  const [trains, setTrains] = useState([]);
  const [kpis, setKpis] = useState({
    active_trains: 0,
    punctuality_pct: 99.4,
    avg_delay_sec: 12.0,
    max_delay_sec: 45.0,
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
  const [activeSideTab, setActiveSideTab] = useState('trains'); // 'trains' | 'events' | 'stations'

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

  // Canvas Refs
  const canvasRef = useRef(null);
  const transformRef = useRef({ scale: 0.03, offsetX: 100, offsetY: 100 });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const wsRef = useRef(null);

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
              const [minX, minY, maxX, maxY] = data.bounds;
              const netWidth = maxX - minX;
              const netHeight = maxY - minY;
              const cWidth = canvasRef.current.clientWidth || 1000;
              const cHeight = canvasRef.current.clientHeight || 700;
              const scale = Math.min(cWidth / netWidth, cHeight / netHeight) * 0.9;
              transformRef.current = {
                scale: Math.max(scale, 0.015),
                offsetX: (cWidth - netWidth * scale) / 2 - minX * scale,
                offsetY: (cHeight - netHeight * scale) / 2 - minY * scale
              };
            }
          }
        }
      } catch (err) {
        console.error('Error fetching geometry:', err);
      }
    };
    fetchGeometry();
    return () => { mounted = false; };
  }, []);

  // 2. Fetch Initial Sim Status
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/sim/status');
      if (res.ok) {
        const data = await res.json();
        setSimStatus(data);
        if (data.current_day) setSelectedDay(data.current_day);
        if (data.current_model) setSelectedModel(data.current_model);
      }
    } catch (e) {
      console.warn('Status poll error:', e);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // 3. Connect WebSocket for Real-Time Telemetry
  useEffect(() => {
    let isMounted = true;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.port === '5173' ? `${window.location.hostname}:8000` : window.location.host;
    const wsUrl = `${protocol}//${wsHost}/ws/telemetry`;
    let ws = null;
    let reconnectTimeout = null;

    const connectWS = () => {
      if (!isMounted) return;
      try {
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!isMounted && ws) {
            try { ws.close(); } catch (_) {}
          }
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            if (data.active_trains) {
              setTrains(data.active_trains);
            }
            if (data.kpi) {
              setKpis(data.kpi);
            }
            if (data.sim_time_formatted) {
              setSimStatus(prev => ({
                ...prev,
                sim_time_formatted: data.sim_time_formatted,
                sim_time_sec: data.sim_time_sec,
                running: data.running,
                paused: data.paused,
                current_model: data.current_model,
                current_day: data.current_day
              }));
            }
            if (data.recent_events && data.recent_events.length > 0) {
              setEvents(prev => [...data.recent_events, ...prev].slice(0, 50));
            }
          } catch (err) {
            console.error('WebSocket parse error:', err);
          }
        };

        ws.onclose = () => {
          if (isMounted) {
            reconnectTimeout = setTimeout(connectWS, 3000);
          }
        };
        ws.onerror = () => {
          // Handled by onclose
        };
      } catch (_) {
        if (isMounted) {
          reconnectTimeout = setTimeout(connectWS, 3000);
        }
      }
    };

    connectWS();
    return () => {
      isMounted = false;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) {
        if (ws.readyState === WebSocket.OPEN) {
          try { ws.close(); } catch (_) {}
        } else if (ws.readyState === WebSocket.CONNECTING) {
          ws.onopen = () => {
            try { ws.close(); } catch (_) {}
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

    // Dark grid background
    ctx.fillStyle = '#06090e';
    ctx.fillRect(0, 0, width, height);

    // Apply viewport pan & zoom
    const { scale, offsetX, offsetY } = transformRef.current;
    ctx.save();
    ctx.translate(offsetX, offsetY);
    ctx.scale(scale, scale);

    // Draw Track Lanes
    if (geometry && geometry.lanes) {
      for (let i = 0; i < geometry.lanes.length; i++) {
        const lane = geometry.lanes[i];
        const shape = lane.shape;
        if (!shape || shape.length < 2) continue;

        const isPlatform = lane.category === 'platform';
        const isSiding = lane.category === 'siding';

        ctx.beginPath();
        // Invert Y coordinate because SUMO Y grows upward, Canvas Y grows downward
        ctx.moveTo(shape[0][0], -shape[0][1]);
        for (let j = 1; j < shape.length; j++) {
          ctx.lineTo(shape[j][0], -shape[j][1]);
        }

        if (isPlatform) {
          ctx.strokeStyle = '#f59e0b'; // amber for platform track
          ctx.lineWidth = 14 / scale;
          ctx.stroke();
          ctx.strokeStyle = '#fbbf24';
          ctx.lineWidth = 6 / scale;
          ctx.stroke();
        } else if (isSiding) {
          ctx.strokeStyle = '#475569';
          ctx.lineWidth = 4 / scale;
          ctx.stroke();
        } else {
          ctx.strokeStyle = '#1e293b'; // mainline ballast
          ctx.lineWidth = 8 / scale;
          ctx.stroke();
          ctx.strokeStyle = '#38bdf8'; // mainline rail glow
          ctx.lineWidth = 2.5 / scale;
          ctx.stroke();
        }
      }
    }

    // Draw Stations
    if (geometry && geometry.stations) {
      for (const st of geometry.stations) {
        const sx = st.x;
        const sy = -st.y;

        // Station hub circle
        ctx.beginPath();
        ctx.arc(sx, sy, 35 / scale, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(7, 47, 95, 0.7)';
        ctx.fill();
        ctx.strokeStyle = '#00f0ff';
        ctx.lineWidth = 3 / scale;
        ctx.stroke();

        // Station Label
        ctx.font = `bold ${Math.max(14 / scale, 12)}px Inter, sans-serif`;
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText(st.name, sx, sy - (40 / scale));
      }
    }

    // Filter trains
    const filteredTrains = trains.filter(t => {
      if (categoryFilter !== 'ALL' && t.category !== categoryFilter) return false;
      if (delayOnlyFilter && (!t.delay_sec || t.delay_sec <= 0)) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const num = String(t.train_number || t.id).toLowerCase();
        if (!num.includes(q)) return false;
      }
      return true;
    });

    // Draw Trains
    for (const train of filteredTrains) {
      const tx = train.x;
      const ty = -train.y;
      const angleRad = (train.angle || 0) * (Math.PI / 180);

      const isSelected = selectedTrain && (selectedTrain.id === train.id);
      const isHighSpeed = train.category === 'HighSpeed';
      const isFreight = train.category === 'Freight';
      const isDelayed = train.delay_sec > 30;

      ctx.save();
      ctx.translate(tx, ty);
      ctx.rotate(angleRad);

      // Train Body
      const trainLen = 45 / scale;
      const trainWidth = 14 / scale;

      // Glow if selected
      if (isSelected) {
        ctx.shadowColor = '#00f0ff';
        ctx.shadowBlur = 20;
      }

      ctx.beginPath();
      ctx.roundRect(-trainLen / 2, -trainWidth / 2, trainLen, trainWidth, 4 / scale);

      if (isDelayed) {
        ctx.fillStyle = '#ef4444'; // Red if heavily delayed
      } else if (isHighSpeed) {
        ctx.fillStyle = '#00f0ff'; // Cyan for High-Speed Express
      } else if (isFreight) {
        ctx.fillStyle = '#f97316'; // Orange for Freight
      } else {
        ctx.fillStyle = '#10b981'; // Emerald for Regional
      }
      ctx.fill();

      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5 / scale;
      ctx.stroke();

      // Heading indicator (nose)
      ctx.beginPath();
      ctx.moveTo(trainLen / 2, 0);
      ctx.lineTo(trainLen / 2 - 8 / scale, -trainWidth / 3);
      ctx.lineTo(trainLen / 2 - 8 / scale, trainWidth / 3);
      ctx.closePath();
      ctx.fillStyle = '#ffffff';
      ctx.fill();

      ctx.restore();

      // Train Label (non-rotated)
      ctx.font = `600 ${Math.max(11 / scale, 10)}px Inter, sans-serif`;
      ctx.fillStyle = isSelected ? '#00f0ff' : '#e2e8f0';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const label = `${train.train_number || train.id} (${Math.round((train.speed || 0) * 3.6)} km/h)`;
      ctx.fillText(label, tx, ty + (15 / scale));
    }

    ctx.restore();
    ctx.restore();
  }, [geometry, trains, selectedTrain, categoryFilter, searchQuery, delayOnlyFilter]);

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
      const [minX, minY, maxX, maxY] = geometry.bounds;
      const netWidth = maxX - minX;
      const netHeight = maxY - minY;
      const cWidth = canvasRef.current.clientWidth || 1000;
      const cHeight = canvasRef.current.clientHeight || 700;
      const scale = Math.min(cWidth / netWidth, cHeight / netHeight) * 0.9;
      transformRef.current = {
        scale: Math.max(scale, 0.015),
        offsetX: (cWidth - netWidth * scale) / 2 - minX * scale,
        offsetY: (cHeight - netHeight * scale) / 2 - minY * scale
      };
    }
  };

  // Click on Canvas to Select Nearest Train
  const handleCanvasClick = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const { scale, offsetX, offsetY } = transformRef.current;
    const worldX = (clickX - offsetX) / scale;
    const worldY = -(clickY - offsetY) / scale;

    let closest = null;
    let minDist = 30 / scale; // click tolerance

    for (const t of trains) {
      const dist = Math.hypot(t.x - worldX, t.y - worldY);
      if (dist < minDist) {
        minDist = dist;
        closest = t;
      }
    }
    setSelectedTrain(closest);
  };

  // Playback Control Handlers
  const sendControl = async (action, speed = 1.0) => {
    try {
      await fetch('/api/sim/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, speed })
      });
      fetchStatus();
    } catch (err) {
      console.error('Sim control error:', err);
    }
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

  // Inject Disruption Handler
  const handleInjectDisruption = async (e) => {
    e.preventDefault();
    try {
      await fetch('/api/disruption/inject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: disruptionForm.mode,
          vehicle_id: disruptionForm.vehicle_id || undefined,
          platform_id: disruptionForm.platform_id || undefined,
          delay_duration_sec: Number(disruptionForm.delay_duration_sec)
        })
      });
      setShowDisruptionModal(false);
      fetchStatus();
    } catch (err) {
      console.error('Disruption injection error:', err);
    }
  };

  // Clear Disruptions
  const handleClearDisruptions = async () => {
    try {
      await fetch('/api/disruption/clear', { method: 'POST' });
      fetchStatus();
    } catch (err) {
      console.error('Clear disruptions error:', err);
    }
  };

  // Manual Override Handler
  const handleApplyOverride = async (e) => {
    e.preventDefault();
    try {
      await fetch('/api/override/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vehicle_id: overrideForm.vehicle_id,
          override_type: overrideForm.override_type,
          target_platform: overrideForm.target_platform ? Number(overrideForm.target_platform) : undefined,
          hold_duration_sec: overrideForm.hold_duration_sec ? Number(overrideForm.hold_duration_sec) : undefined
        })
      });
      setShowOverrideModal(false);
      fetchStatus();
    } catch (err) {
      console.error('Override action error:', err);
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
              onClick={() => sendControl('step')} 
              className="btn btn-hud" 
              title="Step Single Tick (1s)"
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
                onClick={() => sendControl('set_speed', s)}
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
              if (selectedTrain) setOverrideForm(prev => ({ ...prev, train_id: selectedTrain.id }));
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
                <span className="kpi-mini-val text-emerald">{(kpis.punctuality_pct || 99.4).toFixed(1)}%</span>
              </div>
              <div className="kpi-mini-item">
                <span className="kpi-mini-lbl">Avg Delay</span>
                <span className="kpi-mini-val text-amber">{(kpis.avg_delay_sec || 0).toFixed(1)}s</span>
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
                  <span className={`detail-val ${selectedTrain.delay_sec > 0 ? 'text-rose' : 'text-emerald'}`}>
                    +{Math.round(selectedTrain.delay_sec || 0)} sec
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-lbl">Current Platform:</span>
                  <span className="detail-val">{selectedTrain.current_platform || 'In-Transit'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-lbl">Bypass Divert:</span>
                  <span className="detail-val">{selectedTrain.bypass_divert ? 'ACTIVE (Overtake)' : 'Normal'}</span>
                </div>
              </div>

              <div className="selected-train-actions">
                <button 
                  onClick={() => {
                    setOverrideForm(prev => ({ ...prev, train_id: selectedTrain.id }));
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
                {trains.length === 0 ? (
                  <div className="empty-trains-notice">
                    <span>No active trains at current simulation time.</span>
                    <button onClick={() => sendControl('play')} className="btn btn-secondary btn-sm">
                      <Play size={14} /> Run Time Forward
                    </button>
                  </div>
                ) : (
                  trains.map((t) => (
                    <div 
                      key={t.id}
                      onClick={() => {
                        setSelectedTrain(t);
                        // Center camera on train
                        if (canvasRef.current) {
                          const cWidth = canvasRef.current.clientWidth;
                          const cHeight = canvasRef.current.clientHeight;
                          const { scale } = transformRef.current;
                          transformRef.current.offsetX = cWidth / 2 - t.x * scale;
                          transformRef.current.offsetY = cHeight / 2 + t.y * scale;
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
                        <span className={`train-row-delay ${t.delay_sec > 0 ? 'delayed' : 'ontime'}`}>
                          {t.delay_sec > 0 ? `+${Math.round(t.delay_sec)}s` : 'ON TIME'}
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
              {events.length === 0 ? (
                <div className="empty-events-notice">
                  <span>Waiting for dispatcher telemetry events...</span>
                </div>
              ) : (
                <div className="events-scroll-list">
                  {events.map((ev, idx) => (
                    <div key={ev.id || idx} className={`event-item event-${ev.severity || 'info'}`}>
                      <div className="event-item-header">
                        <span className="event-type">{ev.type || 'DISPATCH_ACTION'}</span>
                        <span className="event-time">{ev.timestamp || 'Now'}</span>
                      </div>
                      <p className="event-msg">{ev.message}</p>
                    </div>
                  ))}
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
                  <label>Target Train ID (Optional):</label>
                  <input 
                    type="text" 
                    placeholder="e.g. 68402" 
                    value={disruptionForm.vehicle_id}
                    onChange={(e) => setDisruptionForm(prev => ({ ...prev, vehicle_id: e.target.value }))}
                    className="modal-input"
                  />
                </div>
              )}

              {disruptionForm.mode === 'platform_blockage' && (
                <div className="form-group">
                  <label>Platform Track ID (Optional):</label>
                  <input 
                    type="text" 
                    placeholder="e.g. City_4_EW_plat_1_fw_0" 
                    value={disruptionForm.platform_id}
                    onChange={(e) => setDisruptionForm(prev => ({ ...prev, platform_id: e.target.value }))}
                    className="modal-input"
                  />
                </div>
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
                <label>Target Train ID:</label>
                <input 
                  type="text" 
                  required
                  placeholder="e.g. 68402" 
                  value={overrideForm.vehicle_id}
                  onChange={(e) => setOverrideForm(prev => ({ ...prev, vehicle_id: e.target.value }))}
                  className="modal-input"
                />
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
