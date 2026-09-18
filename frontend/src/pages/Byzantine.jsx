import { useState, useEffect } from 'react';
import { api } from '../api/client';

export default function Byzantine() {
  const [modes, setModes] = useState([]);
  const [config, setConfig] = useState({ enabled: false, default_attack_mode: 'FALSE_CLAIM', intensity: 0.8 });
  const [claim, setClaim] = useState('');
  const [attackType, setAttackType] = useState('FALSE_CLAIM');
  const [result, setResult] = useState(null);
  const [attacks, setAttacks] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const [modesData, configData] = await Promise.all([
        api.getAttackModes(),
        api.getByzantineConfig(),
      ]);
      setModes(modesData.modes || []);
      setConfig(configData);
    } catch (err) {
      console.error('Failed to load byzantine data:', err);
    }
  }

  async function toggleEnabled() {
    try {
      const updated = await api.updateByzantineConfig({ enabled: !config.enabled });
      setConfig(updated);
    } catch (err) {
      console.error('Toggle failed:', err);
    }
  }

  async function handleAttack(e) {
    e.preventDefault();
    if (!claim.trim()) return;

    setLoading(true);
    try {
      const attackResult = await api.generateAttack(claim.trim(), attackType);
      setResult(attackResult);
      setAttacks(prev => [attackResult, ...prev].slice(0, 20));
    } catch (err) {
      console.error('Attack generation failed:', err);
      alert('Attack generation failed. Is the backend running with a valid API key?');
    }
    setLoading(false);
  }

  // Separate attack modes into three categories
  const intelligentModes = modes.filter(m =>
    ['ADVERSARIAL_REFUTATION'].includes(m.mode)
  );
  const proposerModes = modes.filter(m =>
    ['FALSE_CLAIM', 'CONTRADICT_EXISTING_FACT', 'FAKE_SOURCE', 'IRRELEVANT_SOURCE'].includes(m.mode)
  );
  const reviewerModes = modes.filter(m =>
    ['ALWAYS_ACCEPT', 'ALWAYS_REJECT', 'RANDOM_VOTE', 'CONFIDENCE_MANIPULATION'].includes(m.mode)
  );

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <h1 className="page-title">🎭 Byzantine Agent</h1>
        <p className="page-subtitle">Control the adversarial agent for fault-tolerance testing</p>
      </div>

      {/* ── Config ──────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div className="card-title">Agent Configuration</div>
          <div className="toggle-wrapper">
            <div className={`toggle ${config.enabled ? 'active' : ''}`} onClick={toggleEnabled}>
              <div className="toggle-knob" />
            </div>
            <span className="toggle-label">
              {config.enabled ? 'Active' : 'Disabled'}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
          <div className="metric-pill">
            <span className="metric-pill-label">Mode:</span>
            <span className="metric-pill-value">{config.default_attack_mode}</span>
          </div>
          <div className="metric-pill">
            <span className="metric-pill-label">Intensity:</span>
            <span className="metric-pill-value">{config.intensity}</span>
          </div>
        </div>
      </div>

      <div className="content-grid">
        {/* ── Attack Generator ───────────────────────── */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>Generate Attack</div>

          <form onSubmit={handleAttack}>
            <div className="form-group">
              <label className="form-label">Target Claim (true fact to attack)</label>
              <input
                className="form-input"
                placeholder="e.g., Python was created by Guido van Rossum"
                value={claim}
                onChange={(e) => setClaim(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Attack Type</label>
              <select className="form-select" value={attackType} onChange={(e) => setAttackType(e.target.value)}>
                <optgroup label="Intelligent Adversary">
                  {intelligentModes.map(m => (
                    <option key={m.mode} value={m.mode}>{m.mode} — {m.description}</option>
                  ))}
                </optgroup>
                <optgroup label="Proposer Attacks">
                  {proposerModes.map(m => (
                    <option key={m.mode} value={m.mode}>{m.mode} — {m.description}</option>
                  ))}
                </optgroup>
                <optgroup label="Reviewer Attacks">
                  {reviewerModes.map(m => (
                    <option key={m.mode} value={m.mode}>{m.mode} — {m.description}</option>
                  ))}
                </optgroup>
              </select>
            </div>

            <button className="btn btn-accent" type="submit" disabled={loading || !claim.trim()}>
              {loading ? '⏳ Generating...' : '⚡ Generate Attack'}
            </button>
          </form>

          {/* Latest result */}
          {result && (
            <div style={{ marginTop: 20 }}>
              <div className="card-subtitle" style={{ marginBottom: 8 }}>Generated Attack</div>
              <div className="attack-entry">
                <div className="attack-entry-type">{result.attack_type}</div>
                {result.malicious_claim && (
                  <div className="attack-entry-claim">
                    <strong>Malicious Claim:</strong> "{result.malicious_claim}"
                  </div>
                )}
                {result.source_strategy && (
                  <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 6 }}>
                    Strategy: {result.source_strategy}
                  </div>
                )}
                {result.fake_sources?.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-byzantine)', marginBottom: 4 }}>
                      Fake Sources:
                    </div>
                    {result.fake_sources.map((s, i) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--text-tertiary)', marginLeft: 12 }}>
                        • {s.title} ({s.domain})
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Attack History ─────────────────────────── */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>Attack History</div>

          {attacks.length > 0 ? (
            <div className="attack-log">
              {attacks.map((a, i) => (
                <div key={i} className="attack-entry">
                  <div className="attack-entry-type">{a.attack_type}</div>
                  <div className="attack-entry-claim">
                    {a.malicious_claim || a.source_strategy || 'Reviewer attack mode'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">🎭</div>
              <div className="empty-state-text">No attacks generated yet</div>
            </div>
          )}
        </div>
      </div>

      {/* ── Attack Modes Reference ───────────────────── */}
      <div className="card" style={{ marginTop: 24 }}>
        <div className="card-title" style={{ marginBottom: 16 }}>Available Attack Modes</div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Mode</th>
              <th>Description</th>
              <th>Type</th>
            </tr>
          </thead>
          <tbody>
            {modes.map((m) => (
              <tr key={m.mode}>
                <td>
                  <span className="vote-badge byzantine" style={{ fontSize: 11 }}>{m.mode}</span>
                </td>
                <td>{m.description}</td>
                <td className="mono">
                  {m.mode === 'ADVERSARIAL_REFUTATION'
                    ? 'Intelligent Adversary'
                    : ['ALWAYS_ACCEPT', 'ALWAYS_REJECT', 'RANDOM_VOTE', 'CONFIDENCE_MANIPULATION'].includes(m.mode)
                    ? 'Reviewer'
                    : 'Proposer'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
