import { useState } from 'react';
import { Icon } from '@iconify/react';
import LatexPreview from '@/shared/components/LatexPreview';

const ReviewEditor = ({ latex, bibContent, query, onExportLatex, onExportBib }) => {
  const [tab, setTab] = useState('preview'); // 'preview' | 'source' | 'bib'

  if (!latex) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: 'var(--color-paper-light)',
        gap: '10px',
      }}>
        <Icon icon="mdi:book-open-page-variant-outline" style={{ fontSize: '40px' }} />
        <p style={{ fontSize: '14px', margin: 0 }}>
          Review will appear here after the pipeline completes (Step ⑩)
        </p>
      </div>
    );
  }

  const tabBtn = (id, icon, label) => (
    <button
      key={id}
      onClick={() => setTab(id)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '5px',
        padding: '4px 12px',
        fontSize: '12px',
        fontWeight: 600,
        border: 'none',
        borderRadius: '5px',
        cursor: 'pointer',
        background: tab === id ? 'var(--color-paper-bg)' : 'transparent',
        color: tab === id ? 'var(--color-paper-dark)' : 'var(--color-paper-light)',
        boxShadow: tab === id ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
        transition: 'all 0.15s',
      }}
    >
      <Icon icon={icon} style={{ fontSize: '13px' }} />
      {label}
    </button>
  );

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '12px',
        flexShrink: 0,
        gap: '12px',
        flexWrap: 'wrap',
      }}>
        <h2 style={{
          fontSize: '15px',
          fontWeight: 700,
          color: 'var(--color-paper-dark)',
          margin: 0,
          fontFamily: 'var(--font-inknut)',
        }}>
          {query ? `Review: ${query}` : 'Literature Review'}
        </h2>

        {/* Tab switcher */}
        <div style={{
          display: 'flex',
          gap: '1px',
          background: 'var(--color-paper-surface)',
          borderRadius: '6px',
          padding: '2px',
        }}>
          {tabBtn('preview', 'mdi:eye-outline', 'Preview')}
          {tabBtn('source', 'mdi:code-braces', '.tex')}
          {bibContent && tabBtn('bib', 'mdi:book-multiple-outline', '.bib')}
        </div>

        {/* Download buttons */}
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            onClick={onExportLatex}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '5px 12px',
              fontSize: '12px',
              fontWeight: 600,
              background: 'var(--color-paper-dark)',
              color: 'var(--color-paper-bg)',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            <Icon icon="mdi:download-outline" style={{ fontSize: '13px' }} />
            .tex
          </button>
          {bibContent && (
            <button
              onClick={onExportBib}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 12px',
                fontSize: '12px',
                fontWeight: 600,
                background: 'transparent',
                color: 'var(--color-paper-dark)',
                border: '1px solid var(--color-paper-light)',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              <Icon icon="mdi:download-outline" style={{ fontSize: '13px' }} />
              .bib
            </button>
          )}
        </div>
      </div>

      {/* Content area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: tab === 'preview' ? '20px' : '0',
        background: tab === 'preview' ? '#fff' : 'transparent',
        border: '1px solid var(--color-paper-surface)',
        borderRadius: '8px',
        fontFamily: tab === 'preview' ? "'Newsreader', serif" : 'monospace',
      }}>
        {tab === 'preview' && <LatexPreview content={latex} />}

        {tab === 'source' && (
          <textarea
            readOnly
            value={latex}
            style={{
              width: '100%',
              height: '100%',
              padding: '14px',
              border: 'none',
              outline: 'none',
              fontFamily: 'monospace',
              fontSize: '12px',
              lineHeight: '1.6',
              color: 'var(--color-paper-dark)',
              background: 'var(--color-paper-bg)',
              resize: 'none',
              boxSizing: 'border-box',
            }}
          />
        )}

        {tab === 'bib' && bibContent && (
          <textarea
            readOnly
            value={bibContent}
            style={{
              width: '100%',
              height: '100%',
              padding: '14px',
              border: 'none',
              outline: 'none',
              fontFamily: 'monospace',
              fontSize: '12px',
              lineHeight: '1.6',
              color: 'var(--color-paper-dark)',
              background: 'var(--color-paper-bg)',
              resize: 'none',
              boxSizing: 'border-box',
            }}
          />
        )}
      </div>
    </div>
  );
};

export default ReviewEditor;
