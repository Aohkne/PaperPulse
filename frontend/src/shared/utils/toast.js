import { toast } from 'sonner';
import { friendlyError } from '@/shared/utils/errorMessage';

// Single toast chokepoint for the whole app — match the existing warm
// paper/amber theme instead of sonner's defaults (see Toaster.jsx for the
// shared color tokens, kept in sync with PDFAgentPage's prior inline Toast).
const BASE_STYLE = {
  fontFamily: "'Noto Serif', serif",
  fontSize: '14px',
  borderRadius: '4px',
  border: 'none',
};

export function showSuccess(message) {
  toast.success(message, {
    style: { ...BASE_STYLE, background: 'var(--color-paper-dark)', color: 'var(--color-paper-bg)' },
  });
}

export function showError(err, fallback) {
  toast.error(friendlyError(err, fallback), {
    style: { ...BASE_STYLE, background: '#c0392b', color: '#fff' },
  });
}

export function showInfo(message) {
  toast(message, {
    style: { ...BASE_STYLE, background: 'var(--color-paper-surface)', color: 'var(--color-paper-dark)' },
  });
}
