import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';

function Badge({ value }) {
  const cls = value === 'ACCEPT' || value === 'VALID' ? 'accept' : value === 'REJECT' || value === 'CONTRADICTED' ? 'reject' : 'nme';
  return <span className={`vote-badge ${cls}`}>{value}</span>;
}

export default function SubmitClaim() {
  const [claim, setClaim] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  async function submit(event) {
    event.preventDefault();
    if (!claim.trim()) return;
    setSubmitting(true); setError(''); setResult(null);
    try { setResult(await api.curateClaim(claim.trim())); } catch (err) { setError(err.message); } finally { setSubmitting(false); }
  }
  return <div className="animate-fade-in">
    <div className="page-header"><h1 className="page-title">Submit Claim</h1><p className="page-subtitle">Research, validation, review, and knowledge-base curation.</p></div>
    <form onSubmit={submit} className="card" style={{ marginBottom: 24 }}><label className="form-label">Factual claim</label><textarea className="form-textarea" value={claim} onChange={e => setClaim(e.target.value)} placeholder="Enter a factual claim to evaluate..." /><button className="btn btn-primary" style={{ marginTop: 12 }} disabled={submitting || !claim.trim()}>{submitting ? 'Researching and reviewing...' : 'Submit for curation'}</button>{error && <p style={{ color: '#f43f5e', marginTop: 12 }}>{error}</p>}</form>
    {result && <><div className="card" style={{ marginBottom: 20 }}><div className="card-title">Knowledge Base Context</div>{result.kb_context.facts.length ? <ul>{result.kb_context.facts.map((fact, i) => <li key={i}>{fact}</li>)}</ul> : <p>No relevant accepted facts found.</p>}</div>
      <div className="card" style={{ marginBottom: 20 }}><div className="card-title">Research Evidence</div>{result.research.sources.length ? result.research.sources.map((source, i) => <div key={i} style={{ marginTop: 12 }}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a><div className="card-subtitle">{source.domain}</div><p>{source.snippet}</p></div>) : <p>No external sources were retrieved.</p>}</div>
      <div className="card" style={{ marginBottom: 20 }}><div className="card-title">Editor Verdict <Badge value={result.editor_verdict.verdict} /></div><p>{result.editor_verdict.reason}</p><p>Confidence: {(result.editor_verdict.confidence * 100).toFixed(0)}%</p></div>
      <div className="card"><div className="card-title">Final Decision <Badge value={result.review.consensus?.decision || result.review.status} /></div><p>{result.review.consensus?.reason}</p><p>{result.kb_updated ? 'Knowledge Base updated with this accepted fact.' : 'Knowledge Base was not updated.'}</p><Link className="btn btn-ghost" to={`/proposals/${result.proposal_id}`}>Open proposal details</Link></div></>}
  </div>;
}
