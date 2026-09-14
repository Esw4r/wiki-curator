import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';

function VoteBadge({ vote }) {
  const cls = vote === 'ACCEPT' ? 'accept' : vote === 'REJECT' ? 'reject' : 'nme';
  return <span className={`vote-badge ${cls}`}>{vote}</span>;
}

function VoteCard({ vote }) {
  const voteType = vote.vote || vote.vote;
  const cls = vote.is_byzantine
    ? 'byzantine'
    : voteType === 'ACCEPT' ? 'accept' : voteType === 'REJECT' ? 'reject' : 'nme';

  const confPercent = ((vote.confidence || 0) * 100).toFixed(0);
  const confColor = voteType === 'ACCEPT' ? '#10b981' : voteType === 'REJECT' ? '#f43f5e' : '#f59e0b';

  return (
    <div className={`vote-card ${cls}`}>
      <div className="vote-card-header">
        <div>
          <div className="vote-card-reviewer">
            {vote.is_byzantine ? '🎭 ' : ''}{vote.agent_id || vote.reviewer_id}
          </div>
          {vote.is_byzantine && (
            <span className="vote-badge byzantine" style={{ marginTop: 4 }}>BYZANTINE</span>
          )}
        </div>
        <div className="vote-card-confidence" style={{ color: confColor }}>
          {confPercent}%
        </div>
      </div>

      <VoteBadge vote={voteType} />

      <div className="confidence-bar">
        <div
          className={`confidence-bar-fill ${cls}`}
          style={{ width: `${confPercent}%`, backgroundColor: confColor }}
        />
      </div>

      <div className="vote-card-reason">
        {vote.reason || 'No reason provided.'}
      </div>
    </div>
  );
}

export default function ProposalDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProposal();
  }, [id]);

  async function loadProposal() {
    setLoading(true);
    try {
      const result = await api.getProposal(id);
      setData(result);
    } catch (err) {
      console.error('Failed to load proposal:', err);
    }
    setLoading(false);
  }

  if (loading) {
    return (
      <div className="loading-spinner">
        <div className="spinner" />
      </div>
    );
  }

  if (!data?.proposal) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🔍</div>
        <div className="empty-state-text">Proposal not found</div>
        <Link to="/" className="btn btn-ghost" style={{ marginTop: 16 }}>
          ← Back to Dashboard
        </Link>
      </div>
    );
  }

  const { proposal, votes, decision } = data;

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <Link to="/" style={{ color: 'var(--text-tertiary)', textDecoration: 'none' }}>←</Link>
          <h1 className="page-title">Proposal {proposal.id}</h1>
          <VoteBadge vote={proposal.status} />
        </div>
      </div>

      {/* ── Claim ───────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-title" style={{ marginBottom: 8 }}>Claim</div>
        <p style={{ fontSize: 18, fontWeight: 500, lineHeight: 1.5 }}>
          "{proposal.claim}"
        </p>
        <div style={{ marginTop: 12, display: 'flex', gap: 16, fontSize: 13, color: 'var(--text-tertiary)' }}>
          <span>Proposer: {proposal.proposer_agent}</span>
          <span>Created: {new Date(proposal.created_at).toLocaleString()}</span>
          {proposal.editor_verdict && (
            <span>Editor: <VoteBadge vote={proposal.editor_verdict} /></span>
          )}
        </div>
      </div>

      {/* ── Votes ───────────────────────────────────── */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>Reviewer Votes</h2>
        {votes && votes.length > 0 ? (
          <div className="vote-cards-grid">
            {votes.map((v, i) => (
              <VoteCard key={i} vote={v} />
            ))}
          </div>
        ) : (
          <div className="card">
            <div className="empty-state">
              <div className="empty-state-text">No votes recorded.</div>
            </div>
          </div>
        )}
      </div>

      {/* ── Consensus ───────────────────────────────── */}
      {decision && (
        <div className="card">
          <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>Consensus Decision</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
            <VoteBadge vote={decision.decision} />
            <span className="mono" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
              Method: {decision.consensus_method}
            </span>
          </div>

          <div className="stats-grid" style={{ marginBottom: 16 }}>
            <div className="stat-card">
              <div className="stat-label">Accept</div>
              <div className="stat-value accept">{decision.accept_votes}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Reject</div>
              <div className="stat-value reject">{decision.reject_votes}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Needs More Evidence</div>
              <div className="stat-value nme">{decision.needs_more_evidence_votes}</div>
            </div>
          </div>

          <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
            <strong>Reason:</strong> {decision.reason}
          </div>
        </div>
      )}
    </div>
  );
}
