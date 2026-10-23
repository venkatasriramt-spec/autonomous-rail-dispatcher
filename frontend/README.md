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
    │   ├── Navbar.jsx            # Top navigation bar with live simulation status badge
    │   ├── Navbar.css            # Navigation bar layout and glowing indicator styling
    │   ├── Footer.jsx            # Contributor attribution and academic citations
    │   ├── Footer.css            # Footer styling and responsive link columns
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
  * **776 Track Lanes** across 4 corridors, bypasses, crossovers, and alpine sidings.
  * **18 Station Nodes** (6 intercity hubs, 12 regional town stations).
  * **242 Scheduled Services** with calibrated dwell times.
  * **31 Continuous Physical Rakes** with 1-to-1 stabling track assignments.
  * **96.7% AI Punctuality** under microscopic multi-day simulation.
* **Subsystem Feature Cards:** Direct access cards linking to track generation, timetabling, AI dispatching, backend streaming, and benchmark analytics.
* **Academic Attribution:** Formal credits for project contributors and institutional affiliation.

### B. Real-Time Simulation Studio (`/simulation`)
* **60 FPS Canvas 2D Vector Map:** High-performance HTML5 Canvas renderer drawing all 776 track lanes with functional color coding:
  * High-Speed Mainline (Cyan)
  * Regional Trunk (Steel Blue)
  * Alpine Passing Loop (Emerald Green)
  * Station Platforms (Amber / Yellow)
  * Universal Crossovers (Purple)
  * Storage Yards & Depots (Slate Gray)
* **Live WebSocket Telemetry Bridge (`/ws/telemetry`):** Streams real-time vehicle vectors at 4 Hz with heading angle, speed, current delay, upcoming station, and active platform halts.
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
* **Variable Speed Multiplier:** Smooth simulation speed acceleration from `1x` up to `20x`.
* **Disruption Injection Modal:** Interactive testing tool allowing operators to inject physical incidents into the live simulation:
  * Mechanical train breakdown / stall
  * Station platform blockage / closure
  * Fleet-wide dwell jitter and commuter surge
* **Human-in-the-Loop Manual Override:** Dispatcher intervention console to manually reroute trains to alternate platforms, enforce departure holds, or divert consists over bypasses.

### C. Railway Fleet & Timetable Explorer (`/query`)
A technical railway engineering and diagnostic console structured into 4 interactive tabs:

1. **Scheduled Services Directory (242 Runs):**
   * Multi-field search (train number, train name, corridor, origin, destination, service class).
   * Expandable intermediate stopping schedules showing scheduled arrival, departure, and dwell durations.
   * Client-side pagination (15, 25, 50, or all items per page) with smart ellipsis navigation (`First`, `Prev`, page buttons, `Next`, `Last`).
2. **Interactive Station Schedule Board:**
   * Station-centric perspective modeling real-world passenger departure and arrival boards.
   * Dropdown selector covering 24 station query entries with custom aggregation logic for multi-level platforms (`City_3` East-West and North-South viaducts) and passing loops (`Town_8`).
   * Chronological movement events tagged by type: `DEPARTURE`, `ARRIVAL`, or `PASSENGER_HALT`.
   * Operating calendar day filtering and client-side pagination.
3. **Physical Rakes Roster (31 Trainsets):**
   * Rake lifecycle inspection detailing consist type, total daily revenue services, initial rollout facility, and designated overnight stabling track.
   * Filterable by rolling stock class with client-side pagination.
4. **Rolling Stock Engineering Specifications (7 Classes):**
   * Deep technical specifications for all 7 consist models: power supply, track gauge, maximum velocity, carriage count, train length, gross weight, passenger capacity, and civil track permissions.

### D. System Architecture & Metrics Blueprint (`/about`)
* **Mathematical Formalization of the MDP:**
  * State space vector $\mathcal{S} \in \mathbb{R}^{28}$ with global context, focus vehicle kinetics, leading train proximity, and 6-platform occupancy matrices.
  * Action space $\mathcal{A} \in \text{MultiDiscrete}([3, 7, 4])$ governing route choice, platform allocation, and timetable holds.
  * Multi-objective reward engine $R_t$ incorporating value-of-time priority weights and secondary knock-on penalties.
* **Authoritative 56-Run Benchmark Audit:**
  * Side-by-side empirical performance metrics across all 8 models over 11,568 simulated train journeys.
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
