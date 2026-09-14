import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import { api } from '../api/client';

const VOTE_COLORS = {
  ACCEPT: '#10b981',
  REJECT: '#f43f5e',
  NEEDS_MORE_EVIDENCE: '#f59e0b',
};

function VoteBadge({ vote }) {
  const cls = vote === 'ACCEPT' ? 'accept' : vote === 'REJECT' ? 'reject' : 'nme';
  return <span className={`vote-badge ${cls}`}>{vote}</span>;
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [claim, setClaim] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [dashData, propData] = await Promise.all([
        api.getDashboard(),
        api.listProposals(20),
      ]);
      setStats(dashData);
      setProposals(propData.proposals || []);
    } catch (err) {
      console.error('Dashboard load failed:', err);
    }
    setLoading(false);
  }

  async function handleQuickSubmit(e) {
    e.preventDefault();
    if (!claim.trim()) return;

    setSubmitting(true);
    try {
      // Create a mock editor verdict for testing
      const editorVerdict = {
        proposal_id: `P-${Date.now().toString(36)}`,
        claim: claim.trim(),
        verdict: 'VALID',
        confidence: 0.85,
        supporting_sources: [
          {
            title: 'Mock Source',
            url: 'https://example.com',
            snippet: `Evidence supporting: ${claim}`,
            domain: 'example.com',
          },
        ],
        conflicts: [],
        reason: 'Mock editor verdict for testing.',
        existing_kb_facts: [],
      };

      await api.submitForReview(editorVerdict);
      setClaim('');
      await loadData();
    } catch (err) {
      console.error('Submit failed:', err);
      alert('Submission failed. Is the backend running?');
    }
    setSubmitting(false);
  }

  if (loading) {
    return (
      <div className="loading-spinner">
        <div className="spinner" />
      </div>
    );
  }

  // Prepare chart data
  const decisionData = stats?.decision_counts
    ? Object.entries(stats.decision_counts).map(([name, value]) => ({ name, value }))
    : [];

  const reputationData = stats?.agents?.map(a => ({
    name: a.name.replace(' Reviewer', '').replace(' Agent', ''),
    reputation: Number((a.reputation * 100).toFixed(0)),
  })) || [];

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">Overview of the decision engine</p>
      </div>

      {/* ── Quick Submit ────────────────────────────── */}
      <form onSubmit={handleQuickSubmit} style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>Quick Submit — Test Claim</div>
          <div style={{ display: 'flex', gap: 12 }}>
            <input
              className="form-input"
              placeholder="Enter a factual claim to evaluate..."
              value={claim}
              onChange={(e) => setClaim(e.target.value)}
              style={{ flex: 1 }}
            />
            <button className="btn btn-primary" type="submit" disabled={submitting || !claim.trim()}>
              {submitting ? '⏳ Reviewing...' : '🚀 Submit'}
            </button>
          </div>
        </div>
      </form>

      {/* ── Stat Cards ──────────────────────────────── */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Proposals</div>
          <div className="stat-value">{stats?.total_proposals || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Decisions Made</div>
          <div className="stat-value">{stats?.total_decisions || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Acceptance Rate</div>
          <div className="stat-value accept">{stats?.acceptance_rate || 0}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Votes</div>
          <div className="stat-value">{stats?.total_votes || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Byzantine Votes</div>
          <div className="stat-value byzantine">{stats?.byzantine_votes || 0}</div>
        </div>
      </div>

      {/* ── Charts ──────────────────────────────────── */}
      <div className="content-grid" style={{ marginBottom: 24 }}>
        {/* Decision distribution */}
        <div className="card">
          <div className="card-title">Decision Distribution</div>
          {decisionData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={decisionData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={4}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {decisionData.map((entry) => (
                    <Cell key={entry.name} fill={VOTE_COLORS[entry.name] || '#64748b'} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state">
              <div className="empty-state-text">No decisions yet</div>
            </div>
          )}
        </div>

        {/* Agent reputations */}
        <div className="card">
          <div className="card-title">Agent Reputations</div>
          {reputationData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={reputationData} barSize={32}>
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
                <Bar dataKey="reputation" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state">
              <div className="empty-state-text">No agents found</div>
            </div>
          )}
        </div>
      </div>

      {/* ── Recent Proposals ────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Recent Proposals</div>
        </div>
        {proposals.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Claim</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {proposals.map((p) => (
                <tr key={p.id}>
                  <td className="mono">
                    <Link to={`/proposals/${p.id}`} style={{ color: '#3b82f6', textDecoration: 'none' }}>
                      {p.id}
                    </Link>
                  </td>
                  <td style={{ maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.claim}
                  </td>
                  <td><VoteBadge vote={p.status} /></td>
                  <td className="mono">{new Date(p.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-text">No proposals yet. Submit a claim above!</div>
          </div>
        )}
      </div>
    </div>
  );
}
