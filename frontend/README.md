# Autonomous Rail Dispatcher — Modern Web UI & Simulation Dashboard

Welcome to the **Frontend Web UI & Simulation Dashboard** subsystem of the Autonomous Rail Dispatcher platform. Built with **React 19** and **Vite 8**, this application serves as an interactive diagnostic and operational console for monitoring real-time microscopic railway simulation, inspecting high-frequency vehicle telemetry, querying commercial timetables, and exploring deep reinforcement learning dispatching decisions.

---

## 1. System Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                Modern Web UI Dashboard                                 │
│                                (React 19 + Vite 8 SPA)                                 │
│                                                                                        │
│  [Navigation & Layout]                                                                 │
│  ├── Navbar              - Persistent telemetry status indicator, route switcher       │
│  ├── Footer              - Academic attribution & repository links (HomePage only)     │
│  └── ErrorBoundary       - Catastrophic rendering protection & recovery trigger        │
│                                                                                        │
│  [Core Views]                                                                          │
│  ├── /                   - Overview Home (Architecture Blueprint, KPIs, Features)      │
│  ├── /simulation         - 60 FPS Canvas 2D Vector Map, Live WebSocket Telemetry       │
│  ├── /query              - Fleet & Timetable Explorer (Services, Station Boards, Rakes)│
│  └── /about              - Mathematical MDP Formulation, Spline Diurnal Curve, Audits │
└─────────────────────────────────▲────────────────────────────▲─────────────────────────┘
                                  │                            │
                     HTTP REST API│                            │WebSocket Telemetry (/ws)
             (Proxied via Vite to │                            │(4 Hz vehicle vectors,
              http://localhost:8000)                           │ platform occupancies)
                                  │                            │
┌─────────────────────────────────┴────────────────────────────┴─────────────────────────┐
│                           FastAPI Simulation Backend Server                            │
│                  (Microscopic Eclipse SUMO + 8 Dispatcher AI Models)                   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Layout

```
frontend/
├── index.html                    # Root HTML5 template with Google Fonts & metadata
├── package.json                  # Dependencies (React 19, Lucide React) and npm scripts
├── package-lock.json             # Deterministic dependency lockfile
├── vite.config.js                # Vite 8 config with reverse proxy (/api, /ws) to port 8000
├── .oxlintrc.json                # Oxlint static analysis configuration
├── .gitignore                    # Subsystem ignore rules for Node, Vite, and build caches
├── README.md                     # This frontend architecture and operation guide
└── src/
    ├── main.jsx                  # Application entrypoint mounting App to DOM
    ├── App.jsx                   # BrowserRouter root with ErrorBoundary wrapper
    ├── App.css                   # Global shell styling
    ├── index.css                 # Cyber-railway dark design system tokens & utilities
    ├── components/
    │   ├── Navbar.jsx            # Top navigation bar and route switcher
    │   ├── Navbar.css            # Navigation bar layout and responsive styling
    │   ├── Footer.jsx            # Contributor attribution, copyright, and smooth scroll links
    │   ├── Footer.css            # Footer styling and responsive link columns
    │   ├── ScrollToTop.jsx       # Route change scroll reset and hash anchor deep-linking
    │   └── ErrorBoundary.jsx     # Fallback UI preventing blank-screen render crashes
    └── pages/
        ├── HomePage.jsx          # Overview blueprint, headline KPIs, and subsystem cards
        ├── HomePage.css          # Grid layouts, gradient stat ribbons, and hero styling
        ├── SimulationPage.jsx    # 60 FPS Canvas 2D track renderer, WS telemetry, AI controls
        ├── SimulationPage.css    # Full-viewport simulation workbench, modals, and dials
        ├── QueryPage.jsx         # Diagnostic console (Services, Station Boards, Rakes, Fleet)
        ├── QueryPage.css         # Tab navigation, search ribbons, and paginated tables
        ├── AboutPage.jsx         # MDP math, Fritsch-Carlson spline chart, 56-run benchmark
        └── AboutPage.css         # LaTeX formula cards, interactive chart controls, narratives
```

---

## 3. The Four Core Application Views

### A. Overview Home (`/`)
* **Project Blueprint:** High-level executive overview of the autonomous rail dispatching platform.
* **Headline KPI Ribbon:** Highlights verified scale metrics:
  * **2,413 Track Lanes** across 4 corridors, microscopic switch throats, bypasses, crossovers, and alpine sidings.
  * **18 Station Nodes** (6 intercity hubs, 12 regional town stations).
  * **242 Scheduled Services** with calibrated dwell times.
  * **31 Continuous Physical Rakes** with 1-to-1 stabling track assignments.
  * **96.7% AI Punctuality** under microscopic multi-day simulation.
* **Subsystem Feature Cards:** Direct access cards linking to track generation, timetabling, AI dispatching, backend streaming, and benchmark analytics.
* **Academic Attribution:** Formal credits for project contributors and institutional affiliation.

### B. Real-Time Simulation Studio (`/simulation`)
* **60 FPS Canvas 2D Vector Map:** High-performance HTML5 Canvas renderer drawing all 2,413 microscopic track lanes with authentic railway graphics:
  * UIC dual parallel steel rails with gleaming silver railheads (`#f8fafc`).
  * Dark ballast bed with borders and periodic cross-ties (sleepers isolated strictly to running tracks to keep complex station throats pristine).
  * Clean steel switch blades (`#94a3b8`) bridging turnout departure points without ballast bloating.
  * Scale-adaptive non-clamping formulas (`wYard`, `wPlatform`, `wPocket`, `wSpur`, `wSwitch`) preventing sub-pixel dropouts at overview zoom.
  * Double-Diamond X Crossovers (Amber/Coral `#f59e0b`), Dynamic Passing Loops (Emerald Teal `#14b8a6`), High-Speed Bypasses (Cyan `#00f0ff`), Buffer Stops with alternating red/white hazard stripes, and Multi-Aspect Signal plates.
* **Google Maps-Style Infrastructure Toolbar & Peer Navigation:**
  * Top floating toolbar with element counters: *Passing Loops (23)*, *X Crossovers (8)*, *Buffer Stops (23)*, *Signals (268)*.
  * Cyclic Feature Peer Navigation (`[ < Prev ] Feature X of Y [ Next > ]`) with keyboard arrow bindings (`ArrowLeft`/`ArrowRight`/`ArrowUp`/`ArrowDown`) and smooth camera flight.
  * `Clean Map` filter mode and `🏷️ Labels ON / OFF` toggle to eliminate map clutter.
  * Interactive **Railway Network Legend** HUD card detailing design speeds, swatches, and track roles.
* **Spatial UI Workbench (Resizable & Draggable):**
  * **Resizable & Collapsible Sidebar:** Features an interactive drag handle (`.sidebar-resize-handle`) and full collapse button, allowing operators to maximize the Canvas 2D map to full viewport width.
  * **Draggable Station Focus Card:** Freeform draggable HUD card with live departures, arrivals, and real-time platform occupancy.
* **24-Hour Operational Cycle Completion Modal:**
  * Automatically triggers when simulation reaches cycle end (`start_time_sec + 86400.0s`).
  * Displays cumulative 24-hour performance: Punctuality %, Mean Fleet Delay, Max Delay, AI Interventions Count, and Active Trains.
  * Dual operational workflows: "Replay Same Day (06:00)" and "Advance to Next Day" (e.g. `Mon` $\to$ `Tue`).
* **Canvas Screen-Space Alert Banners:**
  * Overlaid warning banners (`.canvas-hud-alerts-container`) on the canvas alerting operators to active disruptions and manual overrides.
* **Rich Commercial Train Telemetry:**
  * Real-time train inspection panel displaying commercial train name (e.g. *Express Sunrise*), train number, origin-to-destination corridor route, and physical rake ID.
* **Live WebSocket Telemetry Bridge (`/ws/telemetry`):** Streams real-time vehicle vectors at 4 Hz with heading angle, speed, delay, upcoming station, and active platform halts, with seamless 3-second fallback polling.
* **Predefined Operational Time Jumps:** Quick-jump buttons to fast-forward simulation time to key timetable waves:
  * **Dawn (06:00):** Initial morning fleet rollout
  * **Peak (07:30):** High-density morning commuter rush
  * **Midday (12:00):** Balanced base clockface traffic
  * **Rush (17:00):** Evening commuter surge
* **Real-Time Client-Side Train Filtering:** Instantly filters active trains by rolling stock category (`All`, `HighSpeed`, `Regional`, `Intercity`, `Freight`), delay status (`All`, `On-Time`, `Delayed > 60s`), and text search queries.
* **Dispatcher AI Model Selector:** Dynamically switch active traffic control in-flight across all 8 supported paradigms:
  1. `Centralized_PPO` (Single-focus actor-critic)
  2. `Hierarchical_Hybrid` (15-min lookahead ensemble)
  3. `Decentralized_MAPPO` (7 CTDE agents)
  4. `Comm_MAPPO` (Inter-agent message passing)
  5. `Multi_Train_Centralized_PPO` (Concurrent fleet)
  6. `Priority_Greedy_Heuristic` (Multi-class priority rules)
  7. `FIFO_Heuristic` (First-in, first-out)
  8. `Static_Baseline` (Unmanaged physical baseline)
* **Calendar Day Switcher:** Toggle operating schedules across all 7 days (`Mon` through `Sun`).
* **De-Jittered Optimistic Speed Slider:** Smooth speed acceleration (`1x` to `20x`) with client-side promise queueing and monotonic request IDs to eliminate rubber-banding from network latency.
* **Disruption Injection Modal:** Interactive operator tool with active vehicle and platform dropdown selectors, supporting:
  * Mechanical train breakdown / stall
  * Station platform blockage / closure
  * Fleet-wide dwell jitter and commuter surge
  * Compound multi-point failure scenarios
* **Executive AI Event Log:** Rich, color-coded event stream with severity badges (`danger`, `warning`, `info`, `purple`, `cyan`, `amber`, `emerald`), humanized incident titles, and automatic periodic 30s AI operational status checks.
* **Human-in-the-Loop Manual Override:** Dispatcher intervention console to manually reroute trains to alternate platforms, enforce departure holds, or divert consists over bypasses.

### C. Railway Fleet & Timetable Explorer (`/query`)
A technical railway engineering and diagnostic console structured into 4 interactive tabs:

1. **Scheduled Services Directory (242 Runs):**
   * Multi-field search (train number, train name, corridor, origin, destination, service class).
   * **Advanced Multi-Field Sorting:** Bidirectional sorting by Departure Time, Arrival Time, Train Number, Name, Corridor, Class, Origin, Destination, Distance, and Duration.
   * Expandable intermediate stopping schedules showing scheduled arrival, departure, and dwell durations.
   * Client-side pagination (15, 25, 50, or all items per page) with smart ellipsis navigation (`First`, `Prev`, page buttons, `Next`, `Last`).
2. **Interactive Station Schedule Board:**
   * Station-centric perspective modeling real-world passenger departure and arrival boards.
   * Dropdown selector covering 24 station query entries with custom aggregation logic for multi-level platforms (`City_3` East-West and North-South viaducts) and passing loops (`Town_8`).
   * Chronological movement events tagged by type: `DEPARTURE`, `ARRIVAL`, or `PASSENGER_HALT`.
   * Operating calendar day filtering, multi-field sorting, and client-side pagination.
3. **Physical Rakes Roster (31 Trainsets):**
   * Rake lifecycle inspection detailing consist type, total daily revenue services, initial rollout facility, and designated overnight stabling track.
   * Filterable by rolling stock class with multi-field sorting and client-side pagination.
4. **Rolling Stock Engineering Specifications (7 Classes):**
   * Deep technical specifications for all 7 consist models: power supply, track gauge, maximum velocity, carriage count, train length, gross weight, passenger capacity, and civil track permissions.

### D. System Architecture & Metrics Blueprint (`/about`)
* **5-Tier System Architecture Diagram:** Expanded visual architecture encompassing the UI layer, API gateway, AI inference engines, microscopic SUMO physics, and a **5th Tier for Data & Infrastructure Persistence** (SQLite database, compiled XML definitions, TraCI socket state, and Redis/session caching).
* **Deep-Link Hash Anchor Routing:** Seamless deep-linking across sections (e.g., `#architecture`, `#benchmark`, `#diurnal-spline`) with fixed-header scroll offset compensation and `prefers-reduced-motion` detection.
* **Mathematical Formalization of the MDP:**
  * State space vector $\mathcal{S} \in \mathbb{R}^{28}$ with global context, focus vehicle kinetics, leading train proximity, and 6-platform occupancy matrices.
  * Action space $\mathcal{A} \in \text{MultiDiscrete}([3, 7, 4])$ governing route choice, platform allocation, and timetable holds.
  * Multi-objective reward engine $R_t$ incorporating value-of-time priority weights and secondary knock-on penalties.
* **Authoritative 56-Run Benchmark Audit:**
  * Side-by-side empirical performance metrics across all 8 models over 11,568 simulated train journeys with floating CSS tooltips for metric clarity.
* **Interactive Diurnal Timeline Visualization:**
  * Displays 24-hour hour-by-hour fleet delay progression.
  * **Fritsch-Carlson Monotone Cubic Spline:** Custom mathematical curve interpolation guaranteeing zero unnatural overshoots/undershoots through hourly telemetry points.
  * Interactive day selector pills (`Mon` through `Sun`) and model comparisons.
  * Morning and evening rush key metrics ribbon.
  * 3-card narrative breakdown of morning peak surges, midday base recovery, and nocturnal freight operations.
* **International Rail Engineering Foundations:**
  * Swiss *Taktfahrplan* periodic timetable principles.
  * Double scissors crossovers and parallel conflict resolution.
  * Dynamic mountain passing loops (*Überholgleis*).

---

## 4. Technology Stack & Design System

* **Core Framework:** React 19 (`react`, `react-dom`) with client-side routing via `react-router-dom` v7.
* **Build Tooling:** Vite 8 with `@vitejs/plugin-react` utilizing lightning-fast native Rollup bundling.
* **Iconography:** `lucide-react` high-clarity iconography.
* **Styling Architecture:** Pure Vanilla CSS design system (`index.css`) with:
  * High-contrast cyber-railway dark aesthetic (HSL-tailored dark background `#0c1017`, deep navy surface `#121824`).
  * Accent palette: Railway cyan (`#00e5ff`), signal amber (`#ffb300`), emerald pass (`#00e676`), and disruption rose (`#ff1744`).
  * Custom scrollbars, glowing status indicators, and glassmorphism backdrops.
* **Zero Console Errors:** Clean React 19 lifecycle management with explicit WebSocket ready-state disposal.

---

## 5. Development & Production Commands

All commands should be executed from within the `frontend/` directory:

```bash
# 1. Install dependencies
npm install

# 2. Start local development server (Port 5173 with proxy to backend)
npm run dev

# 3. Compile optimized production build (into dist/)
npm run build

# 4. Preview local production bundle
npm run preview

# 5. Run Oxlint static analysis
npm run lint
```

---

## 6. Vite Reverse Proxy Configuration

During local development, `frontend/vite.config.js` transparently proxies API and WebSocket requests to the FastAPI backend running on port 8000:

```javascript
// frontend/vite.config.js
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
```

This prevents Cross-Origin Resource Sharing (CORS) complications and allows seamless WebSocket streaming.

---

## 7. Subsystem Documentation Links

* **Monorepo Architecture:** [Root README](../README.md)
* **FastAPI Simulation Backend:** [backend/README.md](../backend/README.md)
* **Track Infrastructure & Topology:** [tracks/README.md](../tracks/README.md)
* **Fleet Scheduling & Database:** [trains/README.md](../trains/README.md)
* **Autonomous Dispatcher AI:** [dispatcher/README.md](../dispatcher/README.md)
* **Unified Project History:** [project_history.md](../project_history.md)
