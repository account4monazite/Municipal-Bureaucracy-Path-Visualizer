# Civic Locator Backend (`civic-locator-backend`)

A standalone Express REST API server wrapping the core civic task resolution and office location services. It exposes endpoints to analyze municipal and government task descriptions and find nearest government counters, seva kendras, and administrative offices.

---

## Getting Started

### 1. Installation

From the `backend` directory, install dependencies:

```bash
cd backend
npm install
```

### 2. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Default configuration in `.env`:
```env
PORT=3001
USE_MOCK_DATA=true
GOOGLE_MAPS_API_KEY=
```

- **`USE_MOCK_DATA=true` (Default)**: Runs completely offline without making external calls to Google Places API. Generates contextual office locations and distances.
- **`USE_MOCK_DATA=false`**: Connects to the live Google Places API (requires setting `GOOGLE_MAPS_API_KEY`).

### 3. Running the Server

Start the production server:
```bash
npm start
```

Or run in development mode:
```bash
npm run dev
```

The server will listen at `http://localhost:3001` (or the configured `PORT`).

---

## API Endpoints

### 1. Resolve Civic Task

Translates a natural language description of an administrative or civic task into an enhanced target search query, administrative department, and category.

- **Method**: `POST`
- **Path**: `/api/resolve-task`
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "task": "update Aadhaar card"
  }
  ```

#### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task` | string | Yes | The natural language description of the government task (e.g. `"renew driving license"`, `"pay property tax"`) |

#### Response Shape

- **Status Code**: `200 OK`
- **Body**:
  ```json
  {
    "query": "Aadhaar Seva Kendra UIDAI center",
    "category": "Identity & Biometrics",
    "searchTerms": [
      "Aadhaar Seva Kendra",
      "UIDAI Enrollment Center",
      "CSC Aadhaar Center",
      "Bank Aadhaar Seva Kendra"
    ],
    "isEnhanced": true,
    "subject": "aadhaar card",
    "department": "Unique Identification Authority of India (UIDAI)",
    "enhancerId": "aadhaar"
  }
  ```

---

### 2. Find Nearby Offices

Searches for physical service counters, municipal offices, or kendras near a given latitude/longitude.

- **Method**: `GET`
- **Path**: `/api/nearby-offices`

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | `""` | Search query or resolved target (e.g. `"Aadhaar Seva Kendra UIDAI center"`) |
| `userLat` | number | No | `28.6139` | User or city center latitude |
| `userLng` | number | No | `77.2090` | User or city center longitude |
| `radiusMeters` | number | No | `10000` | Search radius in meters (default: 10km) |

#### Example Request
```http
GET /api/nearby-offices?query=Aadhaar+Seva+Kendra&userLat=19.0760&userLng=72.8777
```

#### Response Shape

- **Status Code**: `200 OK`
- **Body**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "mock-office-1",
        "name": "District Aadhaar Seva Kendra",
        "formattedAddress": "Plot 14-B, Institutional Area, Sector 5",
        "geometry": {
          "location": {
            "lat": 19.088,
            "lng": 72.891
          }
        },
        "lat": 19.088,
        "lng": 72.891,
        "rating": 4.6,
        "userRatingsTotal": 312,
        "isOpen": true,
        "openNow": true,
        "operatingHours": "Mon-Sat: 9:00 AM - 5:30 PM",
        "phoneNumber": "011-23414902",
        "distanceKm": 1.9,
        "distanceFormatted": "1.9 km away",
        "estimatedWaitMinutes": 25,
        "types": ["local_government_office", "civic_service_center"],
        "googleMapsUrl": "https://www.google.com/maps/search/?api=1&query=District%20Aadhaar%20Seva%20Kendra",
        "isMock": true,
        "lastVerified": "Offline Civic Dataset Cache"
      }
    ],
    "error": null,
    "isMock": true
  }
  ```

---

## Health Check

- **Method**: `GET`
- **Path**: `/health`
- **Response**:
  ```json
  {
    "status": "ok",
    "service": "civic-locator-backend",
    "mockMode": true
  }
  ```

---

## Directory Structure

```
backend/
├── .env                  # Local environment file (gitignored)
├── .env.example          # Environment template
├── .gitignore            # Git exclusion rules
├── package.json          # Node package configuration
├── README.md             # Backend API documentation
└── src/
    ├── server.js         # Express server & API routes
    ├── civicTaskResolver.js # NLP task resolver (unmodified original logic)
    ├── placesService.js     # Nearby office search (unmodified original logic)
    ├── taskMappings.js      # Task enhancer dictionaries (unmodified original)
    ├── mockPlaces.js        # Offline places mock generator (unmodified)
    └── env.js               # Node environment configuration (reads process.env)
```
