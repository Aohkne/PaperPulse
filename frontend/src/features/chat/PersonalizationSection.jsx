import { useEffect, useRef, useState } from 'react';
import { Icon } from '@iconify/react';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { personalizationApi } from './personalizationApi';

// Small-caps section label — same treatment as ProfileModal's sectionLabelStyle.
const sectionLabelStyle = {
  fontSize: 11,
  fontWeight: 600,
  color: 'var(--color-paper-mid)',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  fontFamily: "'Lora', 'Newsreader', serif",
  marginBottom: 4,
};

const fieldLabelStyle = {
  fontSize: 13,
  color: 'var(--color-paper-dark)',
  fontFamily: "'Newsreader', serif",
  marginBottom: 6,
};

const inputBase = {
  width: '100%',
  border: '1px solid rgba(41, 17, 0, 0.14)',
  borderRadius: 8,
  background: 'var(--color-paper-bg)',
  padding: '9px 11px',
  fontSize: 14,
  fontFamily: "'Newsreader', serif",
  color: 'var(--color-paper-dark)',
  outline: 'none',
  resize: 'vertical',
};

// ChatGPT-style custom-instructions form — name + a single free-text
// instructions box (covers "who you are" and how you'd like replies). Stored
// as source='user' facts and injected into the greeting/reply system prompt.
const MAX = { call_name: 80, instructions: 1500 };

const Field = ({ label, hint, children, count, max }) => (
  <div>
    <div style={fieldLabelStyle}>{label}</div>
    {children}
    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
      <span style={{ fontSize: 11, color: 'var(--color-paper-mid)' }}>{hint}</span>
      {typeof count === 'number' && (
        <span style={{ fontSize: 11, color: count > max ? '#c0392b' : 'var(--color-paper-light)' }}>
          {count}/{max}
        </span>
      )}
    </div>
  </div>
);

const PersonalizationSection = () => {
  const token = useAuthStore((s) => s.token);
  const [form, setForm] = useState({ call_name: '', instructions: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [savedAt, setSavedAt] = useState(false);
  const savedTimer = useRef(null);

  useEffect(() => {
    let cancelled = false;
    if (!token) return undefined;
    personalizationApi
      .getInstructions(token)
      .then((data) => {
        if (cancelled) return;
        setForm({
          call_name: data?.call_name ?? '',
          instructions: data?.instructions ?? '',
        });
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => () => clearTimeout(savedTimer.current), []);

  const update = (key) => (e) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
    setSavedAt(false);
  };

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await personalizationApi.saveInstructions(token, {
        call_name: form.call_name.trim() || null,
        instructions: form.instructions.trim() || null,
      });
      setForm({
        call_name: saved?.call_name ?? '',
        instructions: saved?.instructions ?? '',
      });
      setSavedAt(true);
      clearTimeout(savedTimer.current);
      savedTimer.current = setTimeout(() => setSavedAt(false), 2500);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div style={sectionLabelStyle}>Personalization</div>
      <div
        style={{ fontSize: 12, color: 'var(--color-paper-mid)', lineHeight: 1.5, marginBottom: 14 }}
      >
        PaperPulse keeps these in mind across chats.
      </div>

      {loading ? (
        <div style={{ fontSize: 13, color: 'var(--color-paper-mid)' }}>Loading…</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field
            label="What should PaperPulse call you?"
            hint="Your name or nickname"
            count={form.call_name.length}
            max={MAX.call_name}
          >
            <input
              type="text"
              value={form.call_name}
              onChange={update('call_name')}
              maxLength={MAX.call_name}
              placeholder="e.g. Khoa"
              style={inputBase}
            />
          </Field>

          <Field
            label="Instructions for PaperPulse"
            hint="Who you are and how you'd like replies — role, field, tone, language, length…"
            count={form.instructions.length}
            max={MAX.instructions}
          >
            <textarea
              value={form.instructions}
              onChange={update('instructions')}
              maxLength={MAX.instructions}
              rows={5}
              placeholder="e.g. I'm an NLP master's student researching retrieval-augmented generation. Reply in Vietnamese, keep answers concise, prefer recent papers."
              style={inputBase}
            />
          </Field>

          {error && <div style={{ fontSize: 12, color: '#8c3b3b', lineHeight: 1.4 }}>{error}</div>}

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 7,
                padding: '9px 16px',
                border: '1px solid var(--color-brand-500)',
                borderRadius: 10,
                background: 'var(--color-brand-500)',
                color: 'white',
                fontFamily: "'Lora', 'Newsreader', serif",
                fontSize: 14,
                fontWeight: 600,
                cursor: saving ? 'not-allowed' : 'pointer',
                opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            {savedAt && (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  fontSize: 12,
                  color: 'var(--color-brand-600)',
                }}
              >
                <Icon icon="mdi:check" style={{ fontSize: 15 }} />
                Saved
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PersonalizationSection;
