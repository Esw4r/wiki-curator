import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, Legend
} from 'recharts';
import { api } from '../api/client';

export default function Reputation() {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAgents();
  }, []);

  async function loadAgents() {
    setLoading(true);
    try {
      const data = await api.getAllReputations();
      setAgents(data.agents || []);
    } catch (err) {
      console.error('Failed to load reputations:', err);
    }
    setLoading(false);
  }

  async function selectAgent(agentId) {
    setSelectedAgent(agentId);
    try {
      const data = await api.getReputationHistory(agentId);
      setHistory(data.history || []);
    } catch (err) {
      console.error('Failed to load history:', err);
      setHistory([]);
    }
  }

  if (loading) {
    return (
      <div className="loading-spinner">
        <div className="spinner" />
      </div>
    );
  }

  // Chart data
  const reputationBarData = agents.map(a => ({
    name: a.name.replace(' Reviewer', '').replace(' Agent', ''),
    id: a.id,
    reputation: Number((a.reputation * 100).toFixed(0)),
    role: a.role,
  }));

  // History chart data (reverse to chronological)
  const historyData = [...history].reverse().map((h, i) => ({
    step: i + 1,
    score: Number((h.new_score * 100).toFixed(1)),
    reason: h.reason,
  }));

  // Get bar color based on reputation level
  function getRepColor(value) {
    if (value >= 70) return '#10b981';
    if (value >= 40) return '#f59e0b';
    return '#f43f5e';
  }

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <h1 className="page-title">⭐ Reputation System</h1>
        <p className="page-subtitle">Agent trust scores and reputation history</p>
      </div>

      {/* ── Reputation Overview ──────────────────────── */}
      <div className="content-grid" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>Agent Reputation Scores</div>
          {reputationBarData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={reputationBarData} barSize={40}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(v) => [`${v}%`, 'Reputation']}
                  contentStyle={{
                    background: '#111827',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 8,
                  }}
                />
                <Bar
                  dataKey="reputation"
                  radius={[6, 6, 0, 0]}
                  onClick={(data) => selectAgent(data.id)}
                  cursor="pointer"
                >
                  {reputationBarData.map((entry) => {
                    const color = entry.role === 'BYZANTINE'
                      ? '#a855f7'
                      : getRepColor(entry.reputation);
                    return (
                      <rect key={entry.id} fill={color} />
                    );
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state">
              <div className="empty-state-text">No agents found</div>
            </div>
          )}
        </div>

        {/* History chart */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>
            Reputation History
            {selectedAgent && (
              <span style={{ color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 8 }}>
                — {selectedAgent}
              </span>
            )}
          </div>
          {historyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={historyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="step" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(v) => [`${v}%`, 'Reputation']}
                  labelFormatter={(l) => `Step ${l}`}
                  contentStyle={{
                    background: '#111827',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 8,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#3b82f6' }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state">
              <div className="empty-state-text">
                {selectedAgent
                  ? 'No history for this agent yet'
                  : 'Click an agent bar to view history'}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Agent Table ──────────────────────────────── */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 16 }}>Agent Details</div>
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Role</th>
              <th>Reputation</th>
              <th>Score Bar</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => {
              const repPercent = (a.reputation * 100).toFixed(0);
              const color = a.role === 'BYZANTINE'
                ? '#a855f7'
                : getRepColor(Number(repPercent));
              return (
                <tr key={a.id}>
                  <td className="mono">{a.id}</td>
                  <td>{a.name}</td>
                  <td>
                    <span className={`vote-badge ${a.role === 'BYZANTINE' ? 'byzantine' : 'accept'}`}
                      style={{ fontSize: 11 }}>
                      {a.role}
                    </span>
                  </td>
                  <td className="mono" style={{ color, fontWeight: 600 }}>
                    {repPercent}%
                  </td>
                  <td style={{ minWidth: 120 }}>
                    <div className="confidence-bar" style={{ margin: 0 }}>
                      <div className="confidence-bar-fill"
                        style={{
                          width: `${repPercent}%`,
                          backgroundColor: color,
                        }}
                      />
                    </div>
                  </td>
                  <td>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => selectAgent(a.id)}
                    >
                      📈 History
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
