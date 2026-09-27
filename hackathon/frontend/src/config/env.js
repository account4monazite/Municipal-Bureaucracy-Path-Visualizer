/**
 * Environment configuration for Civic Locator module
 * Works seamlessly in both Vite client runtime and Node test scripts
 */
const envSource = (typeof import.meta !== 'undefined' && import.meta.env) 
  ? import.meta.env 
  : (typeof process !== 'undefined' && process.env ? process.env : {});

export const config = {
  googleMapsApiKey: envSource.VITE_GOOGLE_MAPS_API_KEY || envSource.GOOGLE_MAPS_API_KEY || '',
  // Default to true if not explicitly set to 'false'
  useMockData: envSource.VITE_USE_MOCK_DATA !== 'false',
};

export const isMockMode = () => config.useMockData;
export const getGoogleMapsApiKey = () => config.googleMapsApiKey;

export default config;
