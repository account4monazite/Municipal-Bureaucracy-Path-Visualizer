import React from 'react';
import CivicLocator from './components/CivicLocator';

function App() {
  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="logo-group">
          <div className="logo-icon">🏛️</div>
          <div>
            <div className="logo-title">Civic Task Navigator</div>
            <div className="logo-subtitle">Municipal Bureaucracy Path Visualizer • Nearest Office Locator</div>
          </div>
        </div>
      </header>

      <main className="app-main">
        <CivicLocator initialTask="update Aadhaar card" />
      </main>

      <footer className="app-footer">
        <p>Standalone Module: <code>civic-locator</code> • Ready for team integration</p>
      </footer>
    </div>
  );
}

export default App;
