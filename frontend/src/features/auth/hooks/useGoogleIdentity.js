import { useEffect, useRef } from 'react';

let scriptPromise = null;

function loadGoogleScript() {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }
  return scriptPromise;
}

function toHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

function generateNonce() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return toHex(bytes);
}

async function sha256Hex(value) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return toHex(new Uint8Array(digest));
}

/**
 * Loads Google Identity Services and exposes prompt() to trigger the
 * One Tap / sign-in popup. onCredential receives the Google ID token (JWT)
 * plus the raw nonce — Supabase's sign_in_with_id_token needs both the
 * token and the matching raw nonce to verify it (the hashed nonce is what
 * gets embedded in the token's "nonce" claim by Google). Skipping this is
 * what causes GIS's "Passed nonce and nonce in id_token should either both
 * exist or not" error.
 */
export function useGoogleIdentity(onCredential) {
  const callbackRef = useRef(onCredential);
  const nonceRef = useRef(null);

  useEffect(() => {
    callbackRef.current = onCredential;
  }, [onCredential]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const rawNonce = generateNonce();
      const hashedNonce = await sha256Hex(rawNonce);
      await loadGoogleScript();
      if (cancelled) return;
      nonceRef.current = rawNonce;
      window.google.accounts.id.initialize({
        client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
        nonce: hashedNonce,
        callback: (response) => callbackRef.current(response.credential, nonceRef.current),
      });
    })();
    return () => { cancelled = true; };
  }, []);

  /**
   * `onBlocked` fires when Google silently declines to show the One Tap UI
   * (third-party cookies disabled, FedCM restrictions, recently dismissed,
   * etc.) — without it the button looks like it did nothing on click.
   */
  const prompt = (onBlocked) => {
    if (!import.meta.env.VITE_GOOGLE_CLIENT_ID) {
      console.error('VITE_GOOGLE_CLIENT_ID is not set — Google sign-in is not configured.');
      onBlocked?.();
      return;
    }
    if (!window.google?.accounts?.id) {
      onBlocked?.();
      return;
    }
    window.google.accounts.id.prompt((notification) => {
      if (notification.isNotDisplayed?.() || notification.isSkippedMoment?.()) {
        onBlocked?.();
      }
    });
  };

  return { prompt };
}
