/**
 * API client — fetch wrapper for the FastAPI backend.
 */

const API_BASE = 'http://localhost:8000/api';

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };

  const res = await fetch(url, config);

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`API error ${res.status}: ${errorBody}`);
  }

  return res.json();
}

// ── Review Pipeline ──────────────────────────────────────────────

export const api = {
  // Dashboard
  getDashboard: () => request('/dashboard'),

  // Proposals
  listProposals: (limit = 50, offset = 0) =>
    request(`/proposals?limit=${limit}&offset=${offset}`),

  getProposal: (id) => request(`/proposals/${id}`),

  submitForReview: (editorVerdict) =>
    request('/review', {
      method: 'POST',
      body: JSON.stringify(editorVerdict),
    }),

  // Votes
  getVotes: (proposalId) => request(`/votes/${proposalId}`),

  // Consensus
  getConsensus: (proposalId) => request(`/consensus/${proposalId}`),

  // Reputation
  getAllReputations: () => request('/reputation'),
  getReputationHistory: (agentId, limit = 100) =>
    request(`/reputation/${agentId}/history?limit=${limit}`),

  // Byzantine
  getAttackModes: () => request('/byzantine/modes'),
  generateAttack: (targetClaim, attackType, existingFacts = []) =>
    request('/byzantine/attack', {
      method: 'POST',
      body: JSON.stringify({
        target_claim: targetClaim,
        attack_type: attackType,
        existing_facts: existingFacts,
      }),
    }),
  castByzantineVote: (proposalId, claim, attackMode) =>
    request('/byzantine/vote', {
      method: 'POST',
      body: JSON.stringify({
        proposal_id: proposalId,
        claim: claim,
        attack_mode: attackMode,
      }),
    }),
  getByzantineConfig: () => request('/byzantine/config'),
  updateByzantineConfig: (config) =>
    request('/byzantine/config', {
      method: 'PUT',
      body: JSON.stringify(config),
    }),

  // Experiments
  runExperiment: (config) =>
    request('/experiments/run', {
      method: 'POST',
      body: JSON.stringify(config),
    }),
  listExperiments: (limit = 50, offset = 0) =>
    request(`/experiments/?limit=${limit}&offset=${offset}`),
  getExperiment: (id) => request(`/experiments/${id}`),

  // Health
  health: () => request('/health'),
};
