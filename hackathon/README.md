# Civic Locator (`civic-locator`)

> **Nearest Office Locator** component for the **Civic Task Navigator** (Municipal Bureaucracy Path Visualizer).

A standalone, self-contained frontend module built with React and Vite. Given any civic or government task described in natural language (e.g., *"register a small business"*, *"renew driving license"*, *"update Aadhaar card"*), this component finds and displays relevant local government offices, civic service centers, and administrative departments.

---

## Architecture & Integration

This module is designed to be completely decoupled from the rest of the hackathon platform. It makes no assumptions about global routing, external state management, or backend infrastructure, allowing teammates to drop `<NearestOfficeLocator />` directly into the larger dependency graph or workflow screen.

### Directory Structure
```
civic-locator/
├── .env                  # Local environment file (gitignored)
├── .env.example          # Environment template
├── .gitignore            # Git exclusion rules
├── index.html            # Entry HTML
├── package.json          # Project metadata & dependencies
├── vite.config.js        # Vite build configuration
├── src/
│   ├── components/       # Standalone reusable UI components
│   │   ├── NearestOfficeLocator.jsx
│   │   └── index.js
│   ├── services/         # Office resolution & Maps/Places data services
│   │   └── officeService.js
│   ├── config/           # Configuration and environment loaders
│   │   └── env.js
│   ├── mock/             # Offline mock datasets for civic centers
│   │   └── mockOffices.js
│   ├── App.jsx           # Standalone sandbox harness for development
│   ├── index.css         # Component styling system
│   └── main.jsx          # React DOM entry point
└── README.md
```

---

## Getting Started

### 1. Installation
Install project dependencies:
```bash
npm install
```

### 2. Run Backend & Development Server
The frontend communicates with the backend Express service (`/backend`) via `VITE_BACKEND_URL` (default: `http://localhost:3001`).

Start the backend server:
```bash
cd backend
npm install
npm start
```

Launch the local Vite development server:
```bash
npm run dev
```

Vite will start the dev server (typically at `http://localhost:5173/`).

---

## Mock Mode vs. Live Google Maps Mode

To allow visual testing and development without requiring an immediate Google Cloud billing setup or exposing API keys, this project supports an offline **Mock Mode**.

### What `VITE_USE_MOCK_DATA` Does:
- **`VITE_USE_MOCK_DATA=true` (Default)**:
  - The application runs completely offline.
  - Queries are resolved against structured mock government facilities (`src/mock/mockOffices.js`).
  - No external Google Maps or Places API requests are made.
  - The UI displays an active mock mode indicator.
- **`VITE_USE_MOCK_DATA=false`**:
  - The application uses live Google Maps JavaScript and Places API services.

### Where to Plug in a Real API Key:
When ready to switch to live services:
1. Open your `.env` file in the root directory.
2. Provide your Google Cloud API key:
   ```env
   VITE_GOOGLE_MAPS_API_KEY=YOUR_GOOGLE_MAPS_API_KEY_HERE
   VITE_USE_MOCK_DATA=false
   ```
3. Restart the dev server (`npm run dev`).
