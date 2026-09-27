/**
 * Environment configuration for Civic Locator backend module
 * Reads directly from process.env in Node runtime
 */
const envSource = typeof process !== 'undefined' && process.env ? process.env : {};

export const config = {
  googleMapsApiKey: envSource.GOOGLE_MAPS_API_KEY || envSource.VITE_GOOGLE_MAPS_API_KEY || '',
  // Default to true if not explicitly set to 'false'
  useMockData: envSource.USE_MOCK_DATA !== 'false' && envSource.VITE_USE_MOCK_DATA !== 'false',
};

export const isMockMode = () => config.useMockData;
export const getGoogleMapsApiKey = () => config.googleMapsApiKey;

export default config;
