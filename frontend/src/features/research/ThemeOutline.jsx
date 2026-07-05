import { Icon } from '@iconify/react';

const ThemeCard = ({ theme, content, isLoading, onGenerate }) => {
  const isDone = Boolean(content);

  return (
    <div
      style={{
        border: `1px solid ${isDone ? 'var(--color-paper-mid)' : 'var(--color-paper-surface)'}`,
        borderRadius: '8px',
        padding: '16px',
        background: isDone ? 'rgba(90,107,51,0.04)' : 'var(--color-paper-bg)',
        transition: 'border-color 0.2s',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '12px',
        }}
      >
        <div style={{ flex: 1 }}>
          <h3
            style={{
              fontSize: '14px',
              fontWeight: 600,
              color: 'var(--color-paper-dark)',
              margin: '0 0 4px',
              fontFamily: 'var(--font-inknut)',
            }}
          >
            {theme.title}
          </h3>
          <p
            style={{
              fontSize: '12px',
              color: 'var(--color-paper-mid)',
              margin: 0,
              lineHeight: '1.5',
            }}
          >
            {theme.description}
          </p>
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-end',
            gap: '6px',
            flexShrink: 0,
          }}
        >
          {theme.paper_ids?.length > 0 && (
            <span
              style={{
                fontSize: '11px',
                background: 'var(--color-paper-surface)',
                color: 'var(--color-paper-mid)',
                borderRadius: '20px',
                padding: '2px 8px',
              }}
            >
              {theme.paper_ids.length} papers
            </span>
          )}
          {onGenerate && (
            <button
              onClick={() => !isDone && !isLoading && onGenerate(theme)}
              disabled={isDone || isLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 12px',
                fontSize: '12px',
                fontWeight: 600,
                borderRadius: '5px',
                border: 'none',
                cursor: isDone || isLoading ? 'default' : 'pointer',
                background: isDone
                  ? 'var(--color-paper-surface)'
                  : isLoading
                    ? 'var(--color-paper-surface)'
                    : 'var(--color-brand-600)',
                color: isDone || isLoading ? 'var(--color-paper-mid)' : '#fff',
                transition: 'background 0.15s',
              }}
            >
              {isLoading ? (
                <Icon icon="mdi:loading" className="animate-spin" style={{ fontSize: '13px' }} />
              ) : isDone ? (
                <Icon icon="mdi:check" style={{ fontSize: '13px' }} />
              ) : (
                <Icon icon="mdi:pencil-outline" style={{ fontSize: '13px' }} />
              )}
              {isDone ? 'Done' : isLoading ? 'Generating…' : 'Generate'}
            </button>
          )}
        </div>
      </div>

      {isDone && content && (
        <div
          style={{
            marginTop: '12px',
            paddingTop: '12px',
            borderTop: '1px solid var(--color-paper-surface)',
            fontSize: '12px',
            color: 'var(--color-paper-dark)',
            lineHeight: '1.7',
            maxHeight: '160px',
            overflowY: 'auto',
            whiteSpace: 'pre-wrap',
          }}
        >
          {content.slice(0, 400)}
          {content.length > 400 ? '…' : ''}
        </div>
      )}
    </div>
  );
};

// ── ThemeOutline ─────────────────────────────────────────────────────────────

const ThemeOutline = ({
  themes = [],
  themeContents = {},
  themeLoadingSet = new Set(),
  onGenerate,
  onAssemble,
  // v2 interrupt props
  pendingInterrupt = null,
  onApproveOutline,
  v2Running = false,
}) => {
  const isInterrupt = pendingInterrupt?.type === 'outline';
  const allGenerated = themes.length > 0 && themes.every((t) => themeContents[t.title]);

  if (themes.length === 0 && !v2Running) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          color: 'var(--color-paper-light)',
          gap: '10px',
        }}
      >
        <Icon icon="mdi:format-list-bulleted" style={{ fontSize: '40px' }} />
        <p style={{ fontSize: '14px', margin: 0 }}>Outline will appear here after Step ④</p>
      </div>
    );
  }

  if (themes.length === 0 && v2Running) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          color: 'var(--color-paper-light)',
          gap: '10px',
        }}
      >
        <Icon icon="mdi:loading" className="animate-spin" style={{ fontSize: '32px' }} />
        <p style={{ fontSize: '14px', margin: 0 }}>
          Pipeline running… outline will appear at Step ④
        </p>
      </div>
    );
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '12px',
          flexShrink: 0,
          gap: '12px',
        }}
      >
        <h2
          style={{
            fontSize: '16px',
            fontWeight: 700,
            color: 'var(--color-paper-dark)',
            margin: 0,
            fontFamily: 'var(--font-inknut)',
          }}
        >
          Outline — {themes.length} themes
        </h2>

        <div style={{ display: 'flex', gap: '8px' }}>
          {/* v2: approve outline interrupt */}
          {isInterrupt && (
            <button
              onClick={() => onApproveOutline?.(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                fontSize: '13px',
                fontWeight: 700,
                background: '#f59e0b',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                boxShadow: '0 0 0 2px rgba(245,158,11,0.3)',
              }}
            >
              <Icon icon="mdi:check-circle-outline" style={{ fontSize: '15px' }} />
              Approve & Continue →
            </button>
          )}

          {/* v1: assemble (shown when all themes generated manually) */}
          {!isInterrupt && allGenerated && onAssemble && (
            <button
              onClick={onAssemble}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                fontSize: '13px',
                fontWeight: 600,
                background: 'var(--color-paper-dark)',
                color: 'var(--color-paper-bg)',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              <Icon icon="mdi:book-open-outline" style={{ fontSize: '14px' }} />
              Assemble Review
            </button>
          )}
        </div>
      </div>

      {/* Interrupt notice */}
      {isInterrupt && (
        <div
          style={{
            marginBottom: '12px',
            padding: '10px 14px',
            background: 'rgba(245,158,11,0.08)',
            border: '1px solid rgba(245,158,11,0.3)',
            borderRadius: '6px',
            fontSize: '12px',
            color: '#92400e',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flexShrink: 0,
          }}
        >
          <Icon
            icon="mdi:pause-circle"
            style={{ fontSize: '16px', color: '#f59e0b', flexShrink: 0 }}
          />
          Pipeline paused at Step ④. Review the outline below and click
          <strong style={{ marginLeft: '2px' }}>Approve &amp; Continue</strong> to proceed.
        </div>
      )}

      {/* Theme cards */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        {themes.map((theme) => (
          <ThemeCard
            key={theme.title}
            theme={theme}
            content={themeContents[theme.title]}
            isLoading={themeLoadingSet.has(theme.title)}
            onGenerate={onGenerate}
          />
        ))}
      </div>
    </div>
  );
};

export default ThemeOutline;
