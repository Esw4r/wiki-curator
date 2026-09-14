import { useState, useEffect } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Legend
} from 'recharts';
import { api } from '../api/client';

const ATTACK_MODES = [
  'FALSE_CLAIM', 'CONTRADICT_EXISTING_FACT', 'FAKE_SOURCE',
  'IRRELEVANT_SOURCE', 'ALWAYS_ACCEPT', 'ALWAYS_REJECT',
  'RANDOM_VOTE', 'CONFIDENCE_MANIPULATION'
];

export default function Experiments() {
  const [experiments, setExperiments] = useState([]);
  const [running, setRunning] = useState(false);
  const [latestResult, setLatestResult] = useState(null);

  // Config form
  const [name, setName] = useState('');
  const [numByzantine, setNumByzantine] = useState(0);
  const [attackMode, setAttackMode] = useState('FALSE_CLAIM');
  const [consensusMethod, setConsensusMethod] = useState('majority');
  const [numProposals, setNumProposals] = useState(10);
  const [useReputation, setUseReputation] = useState(false);

  useEffect(() => {
    loadExperiments();
  }, []);

  async function loadExperiments() {
    try {
      const data = await api.listExperiments(20);
      setExperiments(data.experiments || []);
    } catch (err) {
      console.error('Failed to load experiments:', err);
    }
  }

  async function handleRun(e) {
    e.preventDefault();
    setRunning(true);
    try {
      const result = await api.runExperiment({
        name: name || `Exp ${numByzantine}byz ${attackMode}`,
        num_byzantine_agents: numByzantine,
        byzantine_attack_mode: attackMode,
        consensus_method: consensusMethod,
        num_proposals: numProposals,
        use_reputation: useReputation,
      });
      setLatestResult(result);
      await loadExperiments();
    } catch (err) {
      console.error('Experiment failed:', err);
      alert('Experiment failed. Check the backend logs.');
    }
    setRunning(false);
  }

  // Prepare comparison data from past experiments
  const comparisonData = experiments
    .filter(e => e.results_json?.metrics)
    .map(e => ({
      name: e.name || e.id,
      accuracy: Number((e.results_json.metrics.accuracy * 100).toFixed(1)),
      far: Number((e.results_json.metrics.false_acceptance_rate * 100).toFixed(1)),
      frr: Number((e.results_json.metrics.false_rejection_rate * 100).toFixed(1)),
      agreement: Number((e.results_json.metrics.reviewer_agreement * 100).toFixed(1)),
    }))
    .reverse()
    .slice(0, 10);

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <h1 className="page-title">🧪 Experiments</h1>
        <p className="page-subtitle">Run fault-tolerance experiments under different Byzantine conditions</p>
      </div>

      {/* ── Config Form ─────────────────────────────── */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-title" style={{ marginBottom: 16 }}>Configure Experiment</div>

        <form onSubmit={handleRun}>
          <div className="experiment-config">
            <div className="form-group">
              <label className="form-label">Experiment Name</label>
              <input className="form-input" placeholder="Optional name..."
                value={name} onChange={(e) => setName(e.target.value)} />
            </div>

            <div className="form-group">
              <label className="form-label">Byzantine Agents (0–3)</label>
              <select className="form-select" value={numByzantine}
                onChange={(e) => setNumByzantine(parseInt(e.target.value))}>
                <option value={0}>0 — No adversaries</option>
                <option value={1}>1 — One malicious agent</option>
                <option value={2}>2 — Two malicious agents</option>
                <option value={3}>3 — Three malicious agents</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Attack Mode</label>
              <select className="form-select" value={attackMode}
                onChange={(e) => setAttackMode(e.target.value)}>
                {ATTACK_MODES.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Consensus Method</label>
              <select className="form-select" value={consensusMethod}
                onChange={(e) => setConsensusMethod(e.target.value)}>
                <option value="majority">Simple Majority</option>
                <option value="weighted">Reputation-Weighted</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Number of Proposals</label>
              <select className="form-select" value={numProposals}
                onChange={(e) => setNumProposals(parseInt(e.target.value))}>
                <option value={6}>6 (quick test)</option>
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={30}>30</option>
                <option value={50}>50 (full)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Use Reputation</label>
              <div className="toggle-wrapper" style={{ marginTop: 6 }}>
                <div className={`toggle ${useReputation ? 'active' : ''}`}
                  onClick={() => setUseReputation(!useReputation)}>
                  <div className="toggle-knob" />
                </div>
                <span className="toggle-label">{useReputation ? 'Yes' : 'No'}</span>
              </div>
            </div>
          </div>

          <button className="btn btn-primary" type="submit" disabled={running}>
            {running ? '⏳ Running Experiment...' : '▶ Run Experiment'}
          </button>
        </form>
      </div>

      {/* ── Latest Result ───────────────────────────── */}
      {latestResult?.metrics && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-title" style={{ marginBottom: 16 }}>
            Latest Result: {latestResult.config?.name || latestResult.id}
          </div>

          <div className="experiment-result-header">
            <div className="metric-pill">
              <span className="metric-pill-label">Accuracy:</span>
              <span className="metric-pill-value">
                {(latestResult.metrics.accuracy * 100).toFixed(1)}%
              </span>
            </div>
            <div className="metric-pill">
              <span className="metric-pill-label">False Accept:</span>
              <span className="metric-pill-value" style={{ color: '#f43f5e' }}>
                {(latestResult.metrics.false_acceptance_rate * 100).toFixed(1)}%
              </span>
            </div>
            <div className="metric-pill">
              <span className="metric-pill-label">False Reject:</span>
              <span className="metric-pill-value" style={{ color: '#f59e0b' }}>
                {(latestResult.metrics.false_rejection_rate * 100).toFixed(1)}%
              </span>
            </div>
            <div className="metric-pill">
              <span className="metric-pill-label">Consensus Rate:</span>
              <span className="metric-pill-value">
                {(latestResult.metrics.consensus_rate * 100).toFixed(1)}%
              </span>
            </div>
            <div className="metric-pill">
              <span className="metric-pill-label">Agreement:</span>
              <span className="metric-pill-value">
                {(latestResult.metrics.reviewer_agreement * 100).toFixed(1)}%
              </span>
            </div>
            <div className="metric-pill">
              <span className="metric-pill-label">Avg Latency:</span>
              <span className="metric-pill-value">
                {latestResult.metrics.avg_latency_ms.toFixed(0)}ms
              </span>
            </div>
          </div>

          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-label">Correct</div>
              <div className="stat-value accept">{latestResult.metrics.correct_decisions}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">False Acceptances</div>
              <div className="stat-value reject">{latestResult.metrics.false_acceptances}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">False Rejections</div>
              <div className="stat-value nme">{latestResult.metrics.false_rejections}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total Proposals</div>
              <div className="stat-value">{latestResult.metrics.total_proposals}</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Comparison Chart ─────────────────────────── */}
      {comparisonData.length > 0 && (
        <div className="content-grid" style={{ marginBottom: 24 }}>
          <div className="card">
            <div className="card-title" style={{ marginBottom: 16 }}>Accuracy Comparison</div>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={comparisonData} barSize={24}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={50} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    background: '#111827', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 8,
                  }}
                />
                <Legend />
                <Bar dataKey="accuracy" fill="#10b981" name="Accuracy %" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <div className="card-title" style={{ marginBottom: 16 }}>Error Rates Comparison</div>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={comparisonData} barSize={20}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={50} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    background: '#111827', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 8,
                  }}
                />
                <Legend />
                <Bar dataKey="far" fill="#f43f5e" name="False Accept %" radius={[4, 4, 0, 0]} />
                <Bar dataKey="frr" fill="#f59e0b" name="False Reject %" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── Past Experiments Table ────────────────────── */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 16 }}>Experiment History</div>
        {experiments.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Byzantine</th>
                <th>Attack</th>
                <th>Method</th>
                <th>Accuracy</th>
                <th>FAR</th>
                <th>FRR</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((e) => {
                const cfg = e.config_json || {};
                const met = e.results_json?.metrics || {};
                return (
                  <tr key={e.id}>
                    <td>{e.name || e.id}</td>
                    <td className="mono">{cfg.num_byzantine_agents ?? '-'}</td>
                    <td>
                      <span className="vote-badge byzantine" style={{ fontSize: 10 }}>
                        {cfg.byzantine_attack_mode || '-'}
                      </span>
                    </td>
                    <td className="mono">{cfg.consensus_method || '-'}</td>
                    <td className="mono" style={{ color: '#10b981' }}>
                      {met.accuracy != null ? `${(met.accuracy * 100).toFixed(1)}%` : '-'}
                    </td>
                    <td className="mono" style={{ color: '#f43f5e' }}>
                      {met.false_acceptance_rate != null ? `${(met.false_acceptance_rate * 100).toFixed(1)}%` : '-'}
                    </td>
                    <td className="mono" style={{ color: '#f59e0b' }}>
                      {met.false_rejection_rate != null ? `${(met.false_rejection_rate * 100).toFixed(1)}%` : '-'}
                    </td>
                    <td className="mono" style={{ fontSize: 12 }}>
                      {e.created_at ? new Date(e.created_at).toLocaleDateString() : '-'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">
            <div className="empty-state-icon">🧪</div>
            <div className="empty-state-text">No experiments run yet. Configure and run one above!</div>
          </div>
        )}
      </div>
    </div>
  );
}
