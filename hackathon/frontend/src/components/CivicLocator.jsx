import React, { useState, useEffect, useRef, useMemo } from 'react';
import { taskEnhancers } from '../../../backend/src/taskMappings.js';
import { isMockMode, getGoogleMapsApiKey } from '../config/env.js';
import './CivicLocator.css';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:3001';

// Default demo locations
const DEMO_LOCATIONS = [
  { label: 'Central Mumbai (Demo)', lat: 19.0760, lng: 72.8777, isDemo: true },
  { label: 'New Delhi Center (Demo)', lat: 28.6139, lng: 77.2090, isDemo: true },
  { label: 'Bengaluru CBD (Demo)', lat: 12.9716, lng: 77.5946, isDemo: true },
];

const QUICK_TASKS = [
  'update Aadhaar card',
  'renew driving license',
  'pay property tax',
  'renew my gas connection',
  'apply for caste certificate',
  'passport renewal'
];

// Dark theme map styling for Google Maps JS API
const DARK_MAP_STYLE = [
  { elementType: 'geometry', stylers: [{ color: '#1e293b' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#0f172a' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#94a3b8' }] },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#f8fafc' }]
  },
  {
    featureType: 'poi',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#38bdf8' }]
  },
  {
    featureType: 'poi.park',
    elementType: 'geometry',
    stylers: [{ color: '#0f2e2e' }]
  },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#334155' }]
  },
  {
    featureType: 'road',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#1e293b' }]
  },
  {
    featureType: 'road',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#cbd5e1' }]
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry',
    stylers: [{ color: '#475569' }]
  },
  {
    featureType: 'transit',
    elementType: 'geometry',
    stylers: [{ color: '#1e293b' }]
  },
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#0b192c' }]
  },
  {
    featureType: 'water',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#38bdf8' }]
  }
];

/**
 * CivicLocator Component
 * =====================
 * A standalone, self-contained Civic Task Nearest Office Locator.
 * Generates an interactive map and list interface for ANY government task.
 * 
 * Works 100% offline out-of-the-box in Mock Mode without requiring a Google Maps API key,
 * while automatically transitioning to live Google Maps & Places when a key is provided.
 *
 * @param {Object} props
 * @param {string} [props.initialTask="update Aadhaar card"] - Pre-filled task string
 * @param {Object} [props.initialLocation] - Default { lat, lng, label }
 * @param {Function} [props.onSelectOffice] - Callback invoked when user selects an office
 * @param {boolean} [props.autoSearchOnMount=true] - Whether to trigger initial search on load
 */
export default function CivicLocator({
  initialTask = 'update Aadhaar card',
  initialLocation = DEMO_LOCATIONS[0],
  onSelectOffice = null,
  autoSearchOnMount = true
}) {
  const [taskInput, setTaskInput] = useState(initialTask);
  const [selectedLocation, setSelectedLocation] = useState(initialLocation);
  const [isLocating, setIsLocating] = useState(false);
  const [showLocationModal, setShowLocationModal] = useState(false);
  const [manualLat, setManualLat] = useState(initialLocation.lat.toString());
  const [manualLng, setManualLng] = useState(initialLocation.lng.toString());

  // Search state
  const [resolution, setResolution] = useState(null);
  const [offices, setOffices] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [activeOfficeId, setActiveOfficeId] = useState(null);
  const [hoveredOfficeId, setHoveredOfficeId] = useState(null);
  const [sortBy, setSortBy] = useState('nearest'); // 'nearest' | 'rating' | 'open'

  // Suggestions state
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const suggestionsRef = useRef(null);
  const cardRefs = useRef({});

  // Mode & Key Detection
  const mockActive = isMockMode();
  const rawApiKey = getGoogleMapsApiKey();
  const hasValidApiKey = Boolean(
    rawApiKey &&
    rawApiKey.trim() !== '' &&
    !rawApiKey.includes('YOUR_') &&
    rawApiKey !== 'undefined'
  );

  // Live Google Maps Refs
  const googleMapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const userMarkerRef = useRef(null);
  const activeInfoWindowRef = useRef(null);

  // Filter live suggestions from taskMappings & common civic services
  useEffect(() => {
    const trimmed = taskInput.trim().toLowerCase();
    if (!trimmed || trimmed.length < 2) {
      setSuggestions([]);
      return;
    }

    const matched = [];
    for (const enhancer of taskEnhancers) {
      for (const alias of enhancer.aliases) {
        if (alias.toLowerCase().includes(trimmed) && !matched.some(m => m.text.toLowerCase() === alias.toLowerCase())) {
          matched.push({
            text: alias,
            category: enhancer.category,
            department: enhancer.department
          });
          if (matched.length >= 5) break;
        }
      }
      if (matched.length >= 5) break;
    }

    // Add generic fallback suggestion if few matches
    if (matched.length < 4 && !matched.some(m => m.text.toLowerCase() === trimmed)) {
      matched.push({
        text: taskInput.trim(),
        category: 'Custom Civic Task',
        department: 'Generic Government Service'
      });
    }

    setSuggestions(matched);
  }, [taskInput]);

  // Close suggestions when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (suggestionsRef.current && !suggestionsRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Execute Search
  const executeSearch = async (queryText = taskInput, loc = selectedLocation) => {
    const textToSearch = (queryText || '').trim();
    if (!textToSearch) return;

    setIsLoading(true);
    setErrorMessage(null);
    setShowSuggestions(false);

    try {
      // 1. Resolve task via backend API
      const resolveRes = await fetch(`${BACKEND_URL}/api/resolve-task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: textToSearch })
      });
      if (!resolveRes.ok) {
        throw new Error(`Failed to resolve task: ${resolveRes.statusText}`);
      }
      const resolved = await resolveRes.json();
      setResolution(resolved);

      // 2. Fetch nearest offices via backend API
      const queryParams = new URLSearchParams({
        query: resolved.query || '',
        userLat: loc.lat,
        userLng: loc.lng,
        radiusMeters: 10000
      });
      const officesRes = await fetch(`${BACKEND_URL}/api/nearby-offices?${queryParams.toString()}`);
      if (!officesRes.ok) {
        throw new Error(`Failed to locate offices: ${officesRes.statusText}`);
      }
      const response = await officesRes.json();

      if (response.success) {
        setOffices(response.data);
        if (response.data.length > 0) {
          setActiveOfficeId(response.data[0].id);
          if (onSelectOffice) onSelectOffice(response.data[0]);
        }
      } else {
        setErrorMessage(response.error || 'Failed to locate offices');
        setOffices([]);
      }
    } catch (err) {
      setErrorMessage(err.message || 'An unexpected error occurred');
      setOffices([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Run initial search on mount
  useEffect(() => {
    if (autoSearchOnMount && initialTask) {
      executeSearch(initialTask, initialLocation);
    }
  }, []);

  // ==========================================
  // Real Google Maps Initialization & Sync
  // ==========================================
  useEffect(() => {
    // Only initialize real Google Maps if mock mode is FALSE and a valid key exists
    if (mockActive || !hasValidApiKey || !googleMapContainerRef.current) return;

    let isCancelled = false;

    async function initLiveGoogleMap() {
      try {
        const { setOptions, importLibrary } = await import('@googlemaps/js-api-loader');
        setOptions({
          key: rawApiKey,
          v: 'weekly'
        });

        await Promise.all([
          importLibrary('maps'),
          importLibrary('places')
        ]);
        if (isCancelled || !googleMapContainerRef.current) return;

        const google = window.google;

        // Initialize Map instance if not already created
        if (!mapInstanceRef.current) {
          mapInstanceRef.current = new google.maps.Map(googleMapContainerRef.current, {
            center: { lat: selectedLocation.lat, lng: selectedLocation.lng },
            zoom: 13,
            styles: DARK_MAP_STYLE,
            disableDefaultUI: false,
            zoomControl: true,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: true
          });
        }

        const map = mapInstanceRef.current;

        // Clear existing office markers
        markersRef.current.forEach(item => item.marker.setMap(null));
        markersRef.current = [];

        // Clear existing user marker
        if (userMarkerRef.current) {
          userMarkerRef.current.setMap(null);
        }

        // Add user location marker (pulsing blue center point)
        userMarkerRef.current = new google.maps.Marker({
          position: { lat: selectedLocation.lat, lng: selectedLocation.lng },
          map,
          title: `You are here (${selectedLocation.label})`,
          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            scale: 9,
            fillColor: '#38bdf8',
            fillOpacity: 1,
            strokeColor: '#ffffff',
            strokeWeight: 2.5
          }
        });

        const bounds = new google.maps.LatLngBounds();
        bounds.extend({ lat: selectedLocation.lat, lng: selectedLocation.lng });

        // Add office markers matching the result cards
        offices.forEach((office, idx) => {
          const pos = { lat: office.lat, lng: office.lng };
          bounds.extend(pos);

          const marker = new google.maps.Marker({
            position: pos,
            map,
            title: office.name,
            label: {
              text: String(idx + 1),
              color: '#ffffff',
              fontWeight: 'bold',
              fontSize: '12px'
            }
          });

          const infoWindow = new google.maps.InfoWindow({
            content: `
              <div style="color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 6px; max-width: 230px;">
                <div style="font-weight: 700; font-size: 13px; margin-bottom: 4px; color: #0f172a;">${office.name}</div>
                <div style="font-size: 11px; color: #475569; margin-bottom: 6px; line-height: 1.35;">${office.formattedAddress}</div>
                <div style="font-size: 11px; font-weight: 600; color: #0284c7; margin-bottom: 6px;">
                  ★ ${office.rating} • ${office.distanceFormatted}
                </div>
                <a href="${office.googleMapsUrl}" target="_blank" rel="noopener noreferrer" style="display: inline-block; font-size: 11px; color: #0284c7; font-weight: 700; text-decoration: underline;">
                  Get Directions ↗
                </a>
              </div>
            `
          });

          // Marker click listener
          marker.addListener('click', () => {
            handleSelectOffice(office);
            if (activeInfoWindowRef.current) activeInfoWindowRef.current.close();
            infoWindow.open(map, marker);
            activeInfoWindowRef.current = infoWindow;
          });

          markersRef.current.push({ officeId: office.id, marker, infoWindow });
        });

        // Fit map bounds to view all markers
        if (offices.length > 0) {
          map.fitBounds(bounds, { top: 50, bottom: 50, left: 50, right: 50 });
        }
      } catch (err) {
        console.error('Failed to load Google Maps SDK:', err);
      }
    }

    initLiveGoogleMap();

    return () => {
      isCancelled = true;
    };
  }, [mockActive, hasValidApiKey, offices, selectedLocation, rawApiKey]);

  // Synchronize active card selection with real Google Map
  useEffect(() => {
    if (mockActive || !hasValidApiKey || !mapInstanceRef.current || !activeOfficeId) return;

    const target = markersRef.current.find(m => m.officeId === activeOfficeId);
    if (target && mapInstanceRef.current) {
      mapInstanceRef.current.panTo(target.marker.getPosition());
      if (activeInfoWindowRef.current) activeInfoWindowRef.current.close();
      target.infoWindow.open(mapInstanceRef.current, target.marker);
      activeInfoWindowRef.current = target.infoWindow;

      // Bounce marker on selection
      if (window.google?.maps?.Animation) {
        target.marker.setAnimation(window.google.maps.Animation.BOUNCE);
        setTimeout(() => {
          target.marker.setAnimation(null);
        }, 800);
      }
    }
  }, [activeOfficeId, mockActive, hasValidApiKey]);

  // Browser Geolocation
  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser. Using demo location.');
      return;
    }

    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const userLoc = {
          label: 'Your Current Location',
          lat: Number(pos.coords.latitude.toFixed(6)),
          lng: Number(pos.coords.longitude.toFixed(6)),
          isDemo: false
        };
        setSelectedLocation(userLoc);
        setManualLat(userLoc.lat.toString());
        setManualLng(userLoc.lng.toString());
        setIsLocating(false);
        executeSearch(taskInput, userLoc);
      },
      (error) => {
        setIsLocating(false);
        console.warn('Geolocation denied or failed:', error.message);
        setShowLocationModal(true);
      },
      { timeout: 7000, enableHighAccuracy: true }
    );
  };

  // Manual location save
  const handleSaveManualLocation = () => {
    const lat = parseFloat(manualLat);
    const lng = parseFloat(manualLng);
    if (isNaN(lat) || isNaN(lng)) {
      alert('Please enter valid numeric latitude and longitude.');
      return;
    }
    const customLoc = {
      label: `Custom (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
      lat,
      lng,
      isDemo: false
    };
    setSelectedLocation(customLoc);
    setShowLocationModal(false);
    executeSearch(taskInput, customLoc);
  };

  // Card click / Selection handler
  const handleSelectOffice = (office) => {
    setActiveOfficeId(office.id);
    if (onSelectOffice) onSelectOffice(office);

    // Scroll card into view if needed
    const cardEl = cardRefs.current[office.id];
    if (cardEl) {
      cardEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  };

  // Sorted list of offices
  const sortedOffices = useMemo(() => {
    const list = [...offices];
    if (sortBy === 'rating') {
      return list.sort((a, b) => (b.rating || 0) - (a.rating || 0));
    }
    if (sortBy === 'open') {
      return list.sort((a, b) => (b.isOpen === a.isOpen ? 0 : b.isOpen ? 1 : -1));
    }
    // Default: nearest
    return list.sort((a, b) => a.distanceKm - b.distanceKm);
  }, [offices, sortBy]);

  // Coordinate projections for the Mock Map Canvas
  const mapProjection = useMemo(() => {
    if (offices.length === 0) return { getCoords: () => ({ left: '50%', top: '50%' }) };

    const allPoints = [
      { lat: selectedLocation.lat, lng: selectedLocation.lng },
      ...offices.map(o => ({ lat: o.lat, lng: o.lng }))
    ];

    const minLat = Math.min(...allPoints.map(p => p.lat));
    const maxLat = Math.max(...allPoints.map(p => p.lat));
    const minLng = Math.min(...allPoints.map(p => p.lng));
    const maxLng = Math.max(...allPoints.map(p => p.lng));

    const latSpan = maxLat - minLat || 0.02;
    const lngSpan = maxLng - minLng || 0.02;
    const padLat = latSpan * 0.2;
    const padLng = lngSpan * 0.2;

    const normMinLat = minLat - padLat;
    const normMaxLat = maxLat + padLat;
    const normMinLng = minLng - padLng;
    const normMaxLng = maxLng + padLng;

    return {
      getCoords: (lat, lng) => {
        const x = ((lng - normMinLng) / (normMaxLng - normMinLng)) * 100;
        const y = (1 - (lat - normMinLat) / (normMaxLat - normMinLat)) * 100;
        return {
          left: `${Math.min(90, Math.max(10, x))}%`,
          top: `${Math.min(88, Math.max(12, y))}%`
        };
      }
    };
  }, [offices, selectedLocation]);

  return (
    <div className="civic-locator-root" id="civic-locator-app">
      {/* Search Header Section */}
      <section className="civic-search-section">
        <div className="civic-search-header">
          <div className="civic-search-title-wrap">
            <h2>
              <span>🏛️</span> Nearest Civic Office Locator
            </h2>
            <p>Describe any municipal task to locate physical application counters and service kendras.</p>
          </div>
          <div
            className={`civic-mode-badge ${
              mockActive
                ? 'is-mock'
                : hasValidApiKey
                ? ''
                : 'is-warning'
            }`}
          >
            <span>●</span>
            {mockActive
              ? 'Offline Mock Mode Active'
              : hasValidApiKey
              ? 'Live Google Places Active'
              : 'Live Mode (API Key Missing)'}
          </div>
        </div>

        {/* Input Form */}
        <form
          className="civic-search-form"
          onSubmit={(e) => {
            e.preventDefault();
            executeSearch(taskInput);
          }}
        >
          <div className="civic-input-row" ref={suggestionsRef}>
            <div className="civic-input-container">
              <span className="civic-input-icon">🔍</span>
              <input
                id="civic-task-input"
                type="text"
                className="civic-search-input"
                placeholder="e.g. update Aadhaar card, renew driving license, pay property tax..."
                value={taskInput}
                onChange={(e) => {
                  setTaskInput(e.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => {
                  if (suggestions.length > 0) setShowSuggestions(true);
                }}
                autoComplete="off"
              />
              {taskInput && (
                <button
                  type="button"
                  className="civic-clear-btn"
                  title="Clear input"
                  onClick={() => {
                    setTaskInput('');
                    setSuggestions([]);
                  }}
                >
                  ✕
                </button>
              )}
            </div>

            <button
              id="civic-search-submit-btn"
              type="submit"
              className="civic-submit-btn"
              disabled={isLoading || !taskInput.trim()}
            >
              {isLoading ? (
                <>
                  <span>Searching...</span>
                </>
              ) : (
                <>
                  <span>Find Offices</span>
                  <span>→</span>
                </>
              )}
            </button>

            {/* Live Suggestions Dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <ul className="civic-suggestions-dropdown" id="civic-suggestions-list">
                {suggestions.map((s, idx) => (
                  <li
                    key={idx}
                    className="civic-suggestion-item"
                    onClick={() => {
                      setTaskInput(s.text);
                      setShowSuggestions(false);
                      executeSearch(s.text);
                    }}
                  >
                    <span className="suggestion-text">📌 {s.text}</span>
                    <span className="suggestion-meta">{s.category}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Location Bar & Quick Actions */}
          <div className="civic-location-bar">
            <div className="civic-location-info">
              <span>Center:</span>
              <span className="location-tag">{selectedLocation.label}</span>
              {selectedLocation.isDemo && (
                <span className="location-demo-badge">Demo Location</span>
              )}
            </div>

            <div className="civic-location-actions">
              <button
                type="button"
                id="civic-geo-btn"
                className="civic-geo-btn"
                onClick={handleUseMyLocation}
                disabled={isLocating}
                title="Detect your current location via browser GPS"
              >
                <span>{isLocating ? '📡 Locating...' : '🎯 Use my location'}</span>
              </button>

              <button
                type="button"
                className="civic-geo-btn"
                onClick={() => setShowLocationModal(true)}
                title="Switch demo city or enter custom coordinates"
              >
                <span>📍 Change City / LatLng</span>
              </button>
            </div>
          </div>

          {/* Quick Pill Suggestions */}
          <div className="civic-quick-tags">
            <span className="quick-tag-label">Try Examples:</span>
            {QUICK_TASKS.map((task, idx) => (
              <button
                key={idx}
                type="button"
                className="quick-tag-pill"
                onClick={() => {
                  setTaskInput(task);
                  executeSearch(task);
                }}
              >
                {task}
              </button>
            ))}
          </div>
        </form>
      </section>

      {/* Manual Location Modal */}
      {showLocationModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(4px)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem'
          }}
        >
          <div
            style={{
              background: '#1e293b',
              border: '1px solid #475569',
              borderRadius: '1rem',
              padding: '1.75rem',
              maxWidth: '440px',
              width: '100%',
              boxShadow: '0 20px 40px rgba(0,0,0,0.6)'
            }}
          >
            <h3 style={{ marginBottom: '1rem', color: '#f8fafc', fontSize: '1.2rem' }}>
              📍 Select or Enter Location
            </h3>

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.5rem' }}>
                Preset Demo Cities:
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {DEMO_LOCATIONS.map((loc, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="civic-geo-btn"
                    style={{
                      borderColor: selectedLocation.label === loc.label ? '#38bdf8' : '#475569',
                      background: selectedLocation.label === loc.label ? 'rgba(56,189,248,0.2)' : undefined
                    }}
                    onClick={() => {
                      setSelectedLocation(loc);
                      setManualLat(loc.lat.toString());
                      setManualLng(loc.lng.toString());
                      setShowLocationModal(false);
                      executeSearch(taskInput, loc);
                    }}
                  >
                    {loc.label.replace(' (Demo)', '')}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ borderTop: '1px solid #334155', paddingTop: '1rem', marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.5rem' }}>
                Custom Coordinates:
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Latitude</span>
                  <input
                    type="text"
                    className="civic-search-input"
                    style={{ padding: '0.5rem 0.75rem', fontSize: '0.9rem' }}
                    value={manualLat}
                    onChange={(e) => setManualLat(e.target.value)}
                    placeholder="e.g. 19.0760"
                  />
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Longitude</span>
                  <input
                    type="text"
                    className="civic-search-input"
                    style={{ padding: '0.5rem 0.75rem', fontSize: '0.9rem' }}
                    value={manualLng}
                    onChange={(e) => setManualLng(e.target.value)}
                    placeholder="e.g. 72.8777"
                  />
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button
                type="button"
                className="card-btn secondary"
                onClick={() => setShowLocationModal(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="card-btn primary"
                onClick={handleSaveManualLocation}
              >
                Apply Coordinates
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Task Resolution Banner */}
      {resolution && (
        <div className="civic-resolution-banner" id="civic-resolution-banner">
          <div className="resolution-left">
            <span
              className={`resolution-badge ${resolution.isEnhanced ? 'enhanced' : 'generic'}`}
            >
              {resolution.isEnhanced ? '⚡ Enhanced Match' : '🛡️ Generic Fallback'}
            </span>
            <span className="resolution-target">
              Target Query: <strong>"{resolution.query}"</strong>
            </span>
          </div>
          <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
            Category: <strong style={{ color: '#38bdf8' }}>{resolution.category}</strong>
          </div>
        </div>
      )}

      {/* Controls Bar: Count & Sorting */}
      {offices.length > 0 && !isLoading && (
        <div className="civic-controls-bar">
          <div className="results-count-text">
            Found <strong>{offices.length} service centers</strong> near {selectedLocation.label}
          </div>

          <div className="civic-sort-controls">
            <label htmlFor="civic-sort-select" className="sort-label">Sort by:</label>
            <select
              id="civic-sort-select"
              className="sort-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="nearest">Nearest Distance</option>
              <option value="rating">Highest Rated</option>
              <option value="open">Open Now First</option>
            </select>
          </div>
        </div>
      )}

      {/* Error state */}
      {errorMessage && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '0.75rem',
            padding: '1rem 1.25rem',
            color: '#fca5a5',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}
        >
          <span>⚠️</span>
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Split-View Layout */}
      <div className="civic-split-view">
        {/* Results List Column */}
        <div className="civic-results-column" id="civic-results-list">
          {isLoading ? (
            // Skeleton loaders
            Array.from({ length: 4 }).map((_, idx) => (
              <div key={idx} className="skeleton-card">
                <div className="skeleton-shimmer skeleton-line title"></div>
                <div className="skeleton-shimmer skeleton-line sub"></div>
                <div className="skeleton-shimmer skeleton-line meta"></div>
              </div>
            ))
          ) : sortedOffices.length > 0 ? (
            sortedOffices.map((office, idx) => {
              const isActive = activeOfficeId === office.id;
              const originalIndex = offices.findIndex(o => o.id === office.id) + 1;

              return (
                <div
                  key={office.id}
                  id={`office-card-${office.id}`}
                  ref={(el) => (cardRefs.current[office.id] = el)}
                  className={`civic-card ${isActive ? 'is-active' : ''}`}
                  onClick={() => handleSelectOffice(office)}
                  onMouseEnter={() => setHoveredOfficeId(office.id)}
                  onMouseLeave={() => setHoveredOfficeId(null)}
                >
                  <div className="card-header">
                    <div className="card-title-group">
                      <span className="card-number-badge">{originalIndex}</span>
                      <span className="card-name">{office.name}</span>
                    </div>
                    <div className="card-rating-badge">
                      <span>★</span>
                      <span>{office.rating}</span>
                      <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 'normal' }}>
                        ({office.userRatingsTotal})
                      </span>
                    </div>
                  </div>

                  <div className="card-address">
                    <span>📍</span>
                    <span>{office.formattedAddress}</span>
                  </div>

                  <div className="card-meta-row">
                    <span className="meta-pill distance">
                      <span>🚗</span>
                      <span>{office.distanceFormatted}</span>
                    </span>

                    <span className={`meta-pill ${office.isOpen ? 'open' : 'closed'}`}>
                      <span>●</span>
                      <span>{office.isOpen ? 'Open Now' : 'Closed'}</span>
                    </span>

                    <span className="meta-pill">
                      <span>🕒</span>
                      <span>{office.operatingHours}</span>
                    </span>
                  </div>

                  <div className="card-actions-row">
                    <a
                      href={office.googleMapsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="card-btn primary"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span>🗺️ Get Directions</span>
                    </a>
                    {office.phoneNumber && (
                      <a
                        href={`tel:${office.phoneNumber}`}
                        className="card-btn secondary"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <span>📞 {office.phoneNumber}</span>
                      </a>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="civic-empty-state">
              <div className="empty-icon">🏛️</div>
              <div className="empty-title">No service centers found</div>
              <p className="empty-desc">
                Try searching for a different government task or selecting another city center.
              </p>
            </div>
          )}
        </div>

        {/* Map Column */}
        <div className="civic-map-column">
          <div className="civic-map-container" id="civic-map-view">
            {/* Header overlay badge */}
            <div className="civic-map-badge-header">
              <div className={`map-status-pill ${!mockActive && hasValidApiKey ? 'live' : ''}`}>
                <span>🗺️</span>
                <span>
                  {!mockActive && hasValidApiKey
                    ? 'Google Maps JavaScript API Active'
                    : !mockActive && !hasValidApiKey
                    ? 'Live mode: API key missing'
                    : 'Map preview — connect API key for live map'}
                </span>
              </div>
            </div>

            {/* Mode 1: Live mode with valid API key -> Real Google Maps JavaScript API Canvas */}
            {!mockActive && hasValidApiKey && (
              <div
                ref={googleMapContainerRef}
                id="google-maps-canvas"
                className="real-google-map-canvas"
              />
            )}

            {/* Mode 2: Live mode requested, but no valid API key found -> Clear inline error state */}
            {!mockActive && !hasValidApiKey && (
              <div className="civic-map-api-missing-error" id="civic-api-missing-view">
                <div className="api-missing-card">
                  <span className="api-missing-icon">⚠️</span>
                  <h3>Live Map Configuration</h3>
                  <p className="api-missing-msg">
                    Add a Google Maps API key in .env to enable live maps
                  </p>
                  <div className="api-missing-code">
                    <code>VITE_GOOGLE_MAPS_API_KEY=your_actual_key_here</code>
                  </div>
                  <p className="api-missing-sub">
                    Live mode is currently active (<code>VITE_USE_MOCK_DATA=false</code>), but no valid Google Maps API key was found in your <code>.env</code> file. Configure your key and restart Vite to view live Google Maps.
                  </p>
                </div>
              </div>
            )}

            {/* Mode 3: Mock Mode (Default) -> Interactive Vector Placeholder Map */}
            {mockActive && (
              <div className="mock-map-canvas">
                <div className="map-grid-overlay"></div>

                {/* Decorative SVG Roads / Metro Lines */}
                <svg className="map-svg-roads" xmlns="http://www.w3.org/2000/svg">
                  <line x1="0%" y1="35%" x2="100%" y2="40%" stroke="rgba(255,255,255,0.07)" strokeWidth="6" />
                  <line x1="15%" y1="0%" x2="80%" y2="100%" stroke="rgba(255,255,255,0.05)" strokeWidth="4" />
                  <line x1="0%" y1="75%" x2="100%" y2="65%" stroke="rgba(56,189,248,0.09)" strokeWidth="3" strokeDasharray="6,4" />
                  <circle cx="50%" cy="50%" r="180" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="2" />
                </svg>

                {/* User Location Beacon */}
                <div
                  className="mock-user-pin"
                  style={mapProjection.getCoords(selectedLocation.lat, selectedLocation.lng)}
                  title={selectedLocation.label}
                >
                  <div className="user-beacon">
                    <div className="beacon-pulse"></div>
                  </div>
                  <div className="user-label-bubble">You (Center)</div>
                </div>

                {/* Interactive Office Pins */}
                {offices.map((office, idx) => {
                  const isActive = activeOfficeId === office.id;
                  const isHovered = hoveredOfficeId === office.id;
                  const coords = mapProjection.getCoords(office.lat, office.lng);

                  return (
                    <div
                      key={office.id}
                      id={`map-pin-${office.id}`}
                      className={`mock-pin ${isActive ? 'is-active' : ''}`}
                      style={coords}
                      onClick={() => handleSelectOffice(office)}
                      onMouseEnter={() => setHoveredOfficeId(office.id)}
                      onMouseLeave={() => setHoveredOfficeId(null)}
                    >
                      <div className="pin-bubble">
                        <span className="pin-number">{idx + 1}</span>
                      </div>

                      {/* Tooltip on active or hover */}
                      {(isActive || isHovered) && (
                        <div className="pin-tooltip">
                          <div className="pin-tooltip-title">{office.name}</div>
                          <div className="pin-tooltip-sub">
                            <span>{office.distanceFormatted}</span>
                            <span>★ {office.rating}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Map Canvas Footer Controls */}
            <div className="map-canvas-footer">
              <div className="map-compass-scale">
                <span>🧭 N • Scale: ~10km radius</span>
              </div>
              <button
                type="button"
                className="map-status-pill"
                style={{ cursor: 'pointer', border: '1px solid #38bdf8' }}
                onClick={() => {
                  if (offices.length > 0) setActiveOfficeId(offices[0].id);
                }}
              >
                <span>🎯 Center Nearest</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
