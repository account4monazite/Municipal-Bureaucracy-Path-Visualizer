/**
 * Mock Places Generator
 * =====================
 * Fabricates realistic civic office results for offline development and visual verification.
 * Generates plausible office names, addresses, ratings, and coordinates offset from the user's location.
 */

// Realistic Indian administrative center addresses
const REALISTIC_STREET_TEMPLATES = [
  'Plot 14-B, Institutional Area, Sector 5',
  'Civic Centre Complex, 2nd Floor, Ring Road',
  'SCO 42-44, Commercial Hub, Sector 17',
  'Tehsil Office Compound, Near District Court',
  'Block C, Community Centre, Main Market',
  'Vikas Bhawan, Near Metro Station Gate 3',
  'Municipal Ward Office No. 12, Civil Lines',
  'Mini Secretariat Complex, Sub-Divisional Road'
];

const PHONE_PREFIXES = ['011-2341', '011-2678', '011-2890', '011-2456', '011-2912'];

/**
 * Calculates Haversine distance in kilometers between two lat/lng points.
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
 * Derives contextual office names based on the search query.
 */
function deriveOfficeNames(query) {
  const qClean = (query || 'Civic Services')
    .replace(/government office|service center|seva kendra|center|office/gi, '')
    .trim();

  const titleCaseQuery = qClean
    .split(' ')
    .filter(Boolean)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ') || 'Civic';

  return [
    `District ${titleCaseQuery} Seva Kendra`,
    `Zonal Municipal Corporation ${titleCaseQuery} Office`,
    `Central Facilitation Counter - ${titleCaseQuery} Services`,
    `Sector 18 Citizen Service Point (${titleCaseQuery})`,
    `Sub-Divisional Administrative Complex (${titleCaseQuery})`,
    `Public Delivery Center & Helpdesk for ${titleCaseQuery}`,
    `Tehsildar & Sub-Registrar Office (${titleCaseQuery} Branch)`
  ];
}

/**
 * Fabricates 5 to 7 realistic-looking government office results
 * located within a plausible radius of the user's coordinates.
 *
 * @param {Object} params
 * @param {string} params.query Search query resolved from user task
 * @param {number|string} [params.userLat=28.6139] User latitude (defaults to New Delhi)
 * @param {number|string} [params.userLng=77.2090] User longitude (defaults to New Delhi)
 * @returns {Array<Object>} Normalized list of mock office objects
 */
export function generateMockResults({ query = '', userLat = 28.6139, userLng = 77.2090 } = {}) {
  const originLat = Number(userLat) || 28.6139;
  const originLng = Number(userLng) || 77.2090;

  const names = deriveOfficeNames(query);

  // Plausible directional scatter offsets (approx 0.8 km to 5.5 km)
  const scatterOffsets = [
    { dLat: 0.0075, dLng: 0.0052, estWait: 15, open: true },
    { dLat: -0.0112, dLng: 0.0084, estWait: 25, open: true },
    { dLat: 0.0145, dLng: -0.0121, estWait: 35, open: true },
    { dLat: -0.0088, dLng: -0.0156, estWait: 20, open: true },
    { dLat: 0.0210, dLng: 0.0165, estWait: 45, open: false },
    { dLat: -0.0234, dLng: -0.0078, estWait: 30, open: true },
    { dLat: 0.0035, dLng: -0.0225, estWait: 40, open: true }
  ];

  const results = scatterOffsets.map((offset, idx) => {
    const lat = Number((originLat + offset.dLat).toFixed(6));
    const lng = Number((originLng + offset.dLng).toFixed(6));
    const distanceKm = calculateHaversineKm(originLat, originLng, lat, lng);
    const officeName = names[idx % names.length];
    const streetAddress = REALISTIC_STREET_TEMPLATES[idx % REALISTIC_STREET_TEMPLATES.length];
    const rating = Number((4.0 + (idx * 0.13) % 0.8).toFixed(1));
    const ratingsCount = 45 + (idx * 137) % 680;
    const phone = `+91 ${PHONE_PREFIXES[idx % PHONE_PREFIXES.length]} ${1000 + idx * 243}`;

    return {
      id: `mock-office-${idx + 1}`,
      placeId: `mock_place_id_${idx + 1}`,
      name: officeName,
      formattedAddress: `${streetAddress}, Near Central Administrative Block`,
      geometry: {
        location: { lat, lng }
      },
      lat,
      lng,
      rating,
      userRatingsTotal: ratingsCount,
      isOpen: offset.open,
      openNow: offset.open,
      operatingHours: offset.open ? '09:30 AM - 05:30 PM (Mon-Sat)' : 'Closed Today (Holiday/Maintenance)',
      phoneNumber: phone,
      distanceKm,
      distanceFormatted: `${distanceKm} km away`,
      estimatedWaitMinutes: offset.estWait,
      types: ['local_government_office', 'government_office', 'point_of_interest'],
      googleMapsUrl: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${officeName} ${streetAddress}`)}`,
      isMock: true,
      lastVerified: 'Official Portal Sync (Verified)'
    };
  });

  // Sort by nearest distance first
  return results.sort((a, b) => a.distanceKm - b.distanceKm);
}

export default {
  generateMockResults
};
