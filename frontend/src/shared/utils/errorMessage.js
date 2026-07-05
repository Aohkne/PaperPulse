// Translates raw errors (HTTP status text, backend exception dumps, network
// errors) into short, end-user-facing English sentences — never expose stack
// traces, status codes, or "Error: ..." prefixes directly in the UI.
const KNOWN_PATTERNS = [
  [
    /network ?error|failed to fetch|ECONNREFUSED/i,
    'Network error — please check your connection and try again.',
  ],
  [/timeout|timed out/i, 'That took too long to respond — please try again.'],
  [/HTTP 401|unauthorized/i, 'Your session has expired — please sign in again.'],
  [/HTTP 402|quota/i, "You've used up your quota for this — please upgrade your plan."],
  [/HTTP 403|forbidden/i, "You don't have permission to do that."],
  [/HTTP 404|not found/i, "We couldn't find what you were looking for."],
  [/HTTP 409/i, 'That changed since you last loaded it — please refresh and try again.'],
  [/HTTP 429|rate limit/i, 'Too many requests — please wait a moment and try again.'],
  [/HTTP 5\d\d|internal server error/i, 'Something went wrong on our end — please try again.'],
];

/**
 * @param {unknown} err - Error instance, string, or backend error payload.
 * @param {string} fallback - Shown when the error doesn't match a known
 *   pattern and isn't already a short, clean sentence.
 */
export function friendlyError(err, fallback = 'Something went wrong. Please try again.') {
  const raw = String(
    (typeof err === 'string' ? err : (err?.message ?? err?.detail ?? err)) ?? ''
  ).trim();

  for (const [pattern, message] of KNOWN_PATTERNS) {
    if (pattern.test(raw)) return message;
  }

  // Already a short, plain sentence with no stack-trace/status-code noise — show as-is.
  const looksLikeRawDump = /^(Error:|Traceback|HTTP \d|<\w+|\{.*\}$)/.test(raw);
  if (raw && raw.length < 160 && !looksLikeRawDump) return raw;

  return fallback;
}
