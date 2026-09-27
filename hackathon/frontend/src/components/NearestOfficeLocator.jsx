import React from 'react';
import { isMockMode } from '../config/env';

/**
 * NearestOfficeLocator Component
 * Standalone component that can be embedded into the larger Civic Task Navigator app.
 */
export function NearestOfficeLocator({ task = '' }) {
  const mockActive = isMockMode();

  return (
    <div className="civic-locator-container">
      <div className="civic-locator-badge">
        <span className="badge-dot"></span>
        {mockActive ? 'Civic Locator - mock mode active' : 'Civic Locator - live mode active'}
      </div>
      <h1 className="civic-locator-title">Nearest Office Locator</h1>
      <p className="civic-locator-desc">
        Find physical government offices and civic service centers for any task without requiring a live Google Maps key during development.
      </p>
      {task && (
        <div className="civic-locator-task-preview">
          Active Task: <strong>{task}</strong>
        </div>
      )}
    </div>
  );
}

export default NearestOfficeLocator;
