import { useState } from 'react';
import { Icon } from '@iconify/react';

const statusColor = {
  supported: 'var(--color-paper-mid)',
  partial: '#d97706',
  unsupported: '#dc2626',
  uncertain: '#6366f1',
  pending: 'var(--color-paper-light)',
};

const ClaimItem = ({ claim, onApprove, onReject }) => {
  const [snippetOpen, setSnippetOpen] = useState(false);

  return (
    <li style={{
      padding: '12px',
      borderBottom: '1px solid var(--color-paper-surface)',
      background: 'var(--color-paper-bg)',
    }}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
        <span style={{
          flexShrink: 0,
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          marginTop: '5px',
          background: statusColor[claim.status] ?? statusColor.pending,
        }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontSize: '12px', color: 'var(--color-paper-dark)', margin: 0, lineHeight: '1.5' }}>
            {claim.text}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '5px', flexWrap: 'wrap' }}>
            <span style={{
              fontSize: '10px',
              fontFamily: 'monospace',
              background: 'var(--color-paper-surface)',
              color: 'var(--color-paper-mid)',
              padding: '1px 6px',
              borderRadius: '3px',
            }}>
              {claim.paperId}
            </span>
            {claim.snippet && (
              <button
                onClick={() => setSnippetOpen(!snippetOpen)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '10px',
                  color: 'var(--color-brand-500)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '2px',
                  padding: 0,
                }}
              >
                <Icon icon={snippetOpen ? 'mdi:eye-off-outline' : 'mdi:eye-outline'} style={{ fontSize: '12px' }} />
                {snippetOpen ? 'Hide snippet' : 'View snippet'}
              </button>
            )}
          </div>

          {snippetOpen && claim.snippet && (
            <blockquote style={{
              margin: '8px 0 0',
              padding: '8px 10px',
              borderLeft: '3px solid var(--color-paper-light)',
              background: 'var(--color-paper-surface)',
              borderRadius: '0 4px 4px 0',
              fontSize: '11px',
              color: 'var(--color-paper-mid)',
              lineHeight: '1.6',
              fontStyle: 'italic',
            }}>
              {claim.snippet}
            </blockquote>
          )}

          {claim.human_review && (
            <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
              <button
                onClick={() => onApprove(claim.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '3px 10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  background: 'var(--color-paper-dark)',
                  color: 'var(--color-paper-bg)',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                <Icon icon="mdi:check" style={{ fontSize: '12px' }} />
                Approve
              </button>
              <button
                onClick={() => onReject(claim.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '3px 10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  background: 'transparent',
                  color: '#dc2626',
                  border: '1px solid #dc2626',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                <Icon icon="mdi:close" style={{ fontSize: '12px' }} />
                Reject
              </button>
            </div>
          )}
        </div>
      </div>
    </li>
  );
};

const ClaimVerifier = ({ claims = [], onApprove, onReject, onFinalise }) => {
  const pendingReview = claims.filter((c) => c.human_review);
  const unsupported = claims.filter((c) => c.status === 'unsupported' && !c.human_review);

  if (claims.length === 0) return null;

  return (
    <div style={{ marginTop: '12px' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '8px',
      }}>
        <p style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-paper-mid)', margin: 0 }}>
          Claims · {claims.length} total
          {pendingReview.length > 0 && (
            <span style={{ color: '#6366f1', marginLeft: '6px' }}>
              {pendingReview.length} need review
            </span>
          )}
          {unsupported.length > 0 && (
            <span style={{ color: '#dc2626', marginLeft: '6px' }}>
              {unsupported.length} unsupported
            </span>
          )}
        </p>
        {pendingReview.length === 0 && claims.length > 0 && (
          <button
            onClick={onFinalise}
            style={{
              fontSize: '11px',
              fontWeight: 600,
              padding: '3px 10px',
              background: 'var(--color-paper-dark)',
              color: 'var(--color-paper-bg)',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Finalise ✓
          </button>
        )}
      </div>

      <ul style={{
        listStyle: 'none',
        margin: 0,
        padding: 0,
        border: '1px solid var(--color-paper-surface)',
        borderRadius: '6px',
        maxHeight: '300px',
        overflowY: 'auto',
      }}>
        {/* Show pending review first */}
        {[...pendingReview, ...claims.filter((c) => !c.human_review)].map((c) => (
          <ClaimItem key={c.id} claim={c} onApprove={onApprove} onReject={onReject} />
        ))}
      </ul>
    </div>
  );
};

export default ClaimVerifier;
