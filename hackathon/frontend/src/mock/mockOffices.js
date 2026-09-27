/**
 * Mock data for civic offices and service centers
 * Used when VITE_USE_MOCK_DATA is true or when running offline
 */
export const mockOffices = [
  {
    id: 'mock-1',
    name: 'District Municipal Corporation Office',
    department: 'Revenue & Civic Administration',
    category: 'Municipal Corporation',
    address: 'Civic Centre, Central Avenue, City Center',
    distanceKm: 1.8,
    operatingHours: '09:30 AM - 05:30 PM (Mon-Sat)',
    contactNumber: '+1 (555) 019-2834',
    supportedTasks: ['register a small business', 'trade license', 'property tax', 'building permit'],
    coordinates: { lat: 28.6139, lng: 77.2090 },
  },
  {
    id: 'mock-2',
    name: 'Regional Transport Office (RTO)',
    department: 'Transport Department',
    category: 'RTO / DMV',
    address: 'Sector 12, Outer Ring Road',
    distanceKm: 3.4,
    operatingHours: '10:00 AM - 04:30 PM (Mon-Fri)',
    contactNumber: '+1 (555) 014-9821',
    supportedTasks: ['renew driving license', 'vehicle registration', 'learner permit', 'vehicle fitness'],
    coordinates: { lat: 28.6250, lng: 77.2180 },
  },
  {
    id: 'mock-3',
    name: 'Citizen Service Center (Aadhaar / Seva Kendra)',
    department: 'UIDAI & Identity Services',
    category: 'Citizen Service Center',
    address: 'Metro Station Concourse, Level 1',
    distanceKm: 0.9,
    operatingHours: '09:00 AM - 06:00 PM (Daily)',
    contactNumber: '+1 (555) 018-7744',
    supportedTasks: ['update aadhaar card', 'biometric update', 'address change', 'voter id enrollment'],
    coordinates: { lat: 28.6189, lng: 77.2140 },
  }
];

export default mockOffices;
