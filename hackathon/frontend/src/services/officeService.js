import { isMockMode } from '../config/env';
import { mockOffices } from '../mock/mockOffices';

/**
 * Service to search and locate nearest government offices for a given civic task.
 * Dynamically switches between mock data and real Google Places API.
 */
export async function findNearestOffices(taskQuery, userLocation = null) {
  if (isMockMode()) {
    // Return mock data for testing
    return {
      source: 'mock',
      query: taskQuery,
      location: userLocation,
      offices: mockOffices,
    };
  }

  // Live Google Places integration will be wired in when API key is provided
  return {
    source: 'live',
    query: taskQuery,
    location: userLocation,
    offices: [],
  };
}

export default {
  findNearestOffices,
};
