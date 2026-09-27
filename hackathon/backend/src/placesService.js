import { generateMockResults } from '../mock/mockPlaces.js';
import { isMockMode, getGoogleMapsApiKey } from '../config/env.js';

let googleMapsLoader = null;
let googleMapsInstance = null;

/**
 * Calculates Haversine distance in kilometers between two lat/lng coordinates.
 */
function calculateHaversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371; // Earth's radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Number((R * c).toFixed(1));
}

/**
 * Loads the Google Maps JavaScript API with Places library on demand.
 */
async function loadGoogleMaps() {
  if (googleMapsInstance) return googleMapsInstance;

  const apiKey = getGoogleMapsApiKey();
  if (!apiKey) {
    throw new Error(
      'Google Maps API key is missing. Set VITE_GOOGLE_MAPS_API_KEY in your .env file or enable mock mode.'
    );
  }

  const { setOptions, importLibrary } = await import('@googlemaps/js-api-loader');
  setOptions({
    key: apiKey,
    v: 'weekly'
  });

  await importLibrary('places');
  googleMapsInstance = (typeof window !== 'undefined' ? window.google : (typeof globalThis !== 'undefined' ? globalThis.google : null));
  return googleMapsInstance;
}

/**
 * Searches for nearby government offices and civic centers.
 * 
 * In Mock Mode (VITE_USE_MOCK_DATA=true):
 * - Fabricates 5-8 realistic civic office results with calculated offsets,
 *   ratings, and working hours after a brief simulated network delay.
 * 
 * In Live Mode (VITE_USE_MOCK_DATA=false):
 * - Dynamically loads Google Maps PlacesService and performs textSearch.
 * 
 * Both modes return the exact same data shape:
 * { success: boolean, data: Array<Office>, error: string|null }
 *
 * @param {Object} options
 * @param {string} options.query Natural search query (e.g. "Aadhaar Seva Kendra UIDAI center")
 * @param {number|string} [options.userLat] Latitude of the user or city center
 * @param {number|string} [options.userLng] Longitude of the user or city center
 * @param {number} [options.radiusMeters=10000] Search radius in meters (default: 10km)
 * @returns {Promise<{ success: boolean, data: Array<Object>, error: string|null }>}
 */
export async function findNearbyOffices({
  query = '',
  userLat = 28.6139,
  userLng = 77.2090,
  radiusMeters = 10000
} = {}) {
  // Check if mock mode is active
  const useMock = isMockMode();

  if (useMock) {
    // Artificial latency (400ms) to simulate real-world network call
    await new Promise(resolve => setTimeout(resolve, 400));

    try {
      const mockData = generateMockResults({
        query,
        userLat,
        userLng
      });

      return {
        success: true,
        data: mockData,
        error: null,
        isMock: true
      };
    } catch (err) {
      return {
        success: false,
        data: [],
        error: err.message || 'Failed to generate mock places',
        isMock: true
      };
    }
  }

  // Live Google Places API Search
  try {
    const google = await loadGoogleMaps();

    // Headless container for PlacesService
    const container = document.createElement('div');
    const service = new google.maps.places.PlacesService(container);

    const originLat = Number(userLat) || 28.6139;
    const originLng = Number(userLng) || 77.2090;
    const location = new google.maps.LatLng(originLat, originLng);

    const request = {
      query,
      location,
      radius: radiusMeters
    };

    return new Promise((resolve) => {
      service.textSearch(request, (results, status) => {
        if (status === google.maps.places.PlacesServiceStatus.OK && results) {
          const normalized = results.map((place, idx) => {
            const lat = place.geometry?.location ? place.geometry.location.lat() : originLat;
            const lng = place.geometry?.location ? place.geometry.location.lng() : originLng;
            const distanceKm = calculateHaversineKm(originLat, originLng, lat, lng);
            const isOpen = place.opening_hours ? (place.opening_hours.isOpen ? place.opening_hours.isOpen() : place.opening_hours.open_now) : true;

            return {
              id: place.place_id || `place-${idx + 1}`,
              placeId: place.place_id,
              name: place.name,
              formattedAddress: place.formatted_address || 'Address not listed',
              geometry: {
                location: { lat, lng }
              },
              lat,
              lng,
              rating: place.rating || 4.0,
              userRatingsTotal: place.user_ratings_total || 0,
              isOpen,
              openNow: isOpen,
              operatingHours: isOpen ? 'Open during regular business hours' : 'Currently closed',
              phoneNumber: place.formatted_phone_number || 'Official municipal desk',
              distanceKm,
              distanceFormatted: `${distanceKm} km away`,
              estimatedWaitMinutes: 20,
              types: place.types || ['local_government_office'],
              googleMapsUrl: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name + ' ' + (place.formatted_address || ''))}&query_place_id=${place.place_id || ''}`,
              isMock: false,
              lastVerified: 'Live Google Places Sync'
            };
          });

          // Sort by nearest distance
          normalized.sort((a, b) => a.distanceKm - b.distanceKm);

          resolve({
            success: true,
            data: normalized,
            error: null,
            isMock: false
          });
        } else if (status === google.maps.places.PlacesServiceStatus.ZERO_RESULTS) {
          resolve({
            success: true,
            data: [],
            error: null,
            isMock: false
          });
        } else {
          resolve({
            success: false,
            data: [],
            error: `Google Places API returned status: ${status}`,
            isMock: false
          });
        }
      });
    });
  } catch (error) {
    return {
      success: false,
      data: [],
      error: error.message || 'Google Places lookup failed',
      isMock: false
    };
  }
}

export default {
  findNearbyOffices
};
