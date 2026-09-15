import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import ProposalDetail from './pages/ProposalDetail';
import Byzantine from './pages/Byzantine';
import Experiments from './pages/Experiments';
import Reputation from './pages/Reputation';

function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        {/* ── Sidebar ─────────────────────────────────── */}
        <aside className="sidebar">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">W</div>
            <div>
              <div className="sidebar-logo-text">Wiki Curator</div>
              <div className="sidebar-logo-sub">Decision Engine</div>
            </div>
          </div>

          <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            Dashboard
          </NavLink>

          <NavLink to="/byzantine" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            Byzantine Agent
          </NavLink>

          <NavLink to="/experiments" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            Experiments
          </NavLink>

          <NavLink to="/reputation" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            Reputation
          </NavLink>
        </aside>

        {/* ── Main Content ────────────────────────────── */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/proposals/:id" element={<ProposalDetail />} />
            <Route path="/byzantine" element={<Byzantine />} />
            <Route path="/experiments" element={<Experiments />} />
            <Route path="/reputation" element={<Reputation />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
