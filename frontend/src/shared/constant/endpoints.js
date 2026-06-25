const BASE_URL = import.meta.env.VITE_API_URL ?? '';

export const API_ENDPOINTS = {
  AUTH: {
    LOGIN: `${BASE_URL}/api/auth/login`,
    REGISTER: `${BASE_URL}/api/auth/register`,
    LOGOUT: `${BASE_URL}/api/auth/logout`,
    REFRESH: `${BASE_URL}/api/auth/refresh`,
    ME: `${BASE_URL}/api/auth/me`,
  },
  CHAT: {
    SEND: `${BASE_URL}/api/chat`,
    HISTORY: `${BASE_URL}/api/chat/history`,
  },
  RESEARCH: {
    STREAM: `${BASE_URL}/api/research/stream`,
    RESUME: `${BASE_URL}/api/research/resume`,
    GRAPH: `${BASE_URL}/api/research/graph`,
  },
  SURVEY: {
    SEARCH: `${BASE_URL}/api/survey/search`,
  },
  GAP: {
    BASE: `${BASE_URL}/api/gap`,
    STREAM: `${BASE_URL}/api/gap/stream`,
  },
  REVIEWS: {
    BASE: `${BASE_URL}/api/reviews`,
    ITEM: (id) => `${BASE_URL}/api/reviews/${id}`,
    EXPORT: (id) => `${BASE_URL}/api/reviews/${id}/export`,
    DUPLICATE: (id) => `${BASE_URL}/api/reviews/${id}/duplicate`,
  },
  ADMIN: {
    STATS: `${BASE_URL}/api/admin/stats`,
    USERS: `${BASE_URL}/api/admin/users`,
    ACTIVITY: `${BASE_URL}/api/admin/activity`,
    USER_BAN: (id) => `${BASE_URL}/api/admin/users/${id}/ban`,
    USER_UNBAN: (id) => `${BASE_URL}/api/admin/users/${id}/unban`,
    CONTRIBUTIONS: `${BASE_URL}/api/admin/contributions`,
    CONTRIBUTION_APPROVE: (id) => `${BASE_URL}/api/admin/contributions/${id}/approve`,
    CONTRIBUTION_REJECT: (id) => `${BASE_URL}/api/admin/contributions/${id}/reject`,
    REVENUE: `${BASE_URL}/api/admin/revenue`,
  },
  COMMUNITY: {
    LIST: `${BASE_URL}/api/contributions`,
    ITEM: (id) => `${BASE_URL}/api/contributions/${id}`,
    VOTE: (id) => `${BASE_URL}/api/contributions/${id}/vote`,
    LEADERBOARD: `${BASE_URL}/api/leaderboard`,
  },
  PDF_AGENT: {
    UPLOAD: `${BASE_URL}/api/pdf-agent/upload`,
    BUNDLE: (docId) => `${BASE_URL}/api/pdf-agent/${docId}/bundle`,
    CONTENT: (docId) => `${BASE_URL}/api/pdf-agent/${docId}/content`,
    ANNOTATIONS: (docId) => `${BASE_URL}/api/pdf-agent/${docId}/annotations`,
    ANNOTATION_ITEM: (docId, id) => `${BASE_URL}/api/pdf-agent/${docId}/annotations/${id}`,
    EXPLAIN: (docId) => `${BASE_URL}/api/pdf-agent/${docId}/explain`,
    REWRITE: (docId) => `${BASE_URL}/api/pdf-agent/${docId}/rewrite`,
    APPLY: (docId) => `${BASE_URL}/api/pdf-agent/${docId}/apply`,
    SAVE: (docId) => `${BASE_URL}/api/pdf-agent/${docId}/save`,
    RESUME: (reviewId) => `${BASE_URL}/api/pdf-agent/resume/${reviewId}`,
  },
  BILLING: {
    ME: `${BASE_URL}/api/billing/me`,
    CHECKOUT_SUBSCRIPTION: `${BASE_URL}/api/billing/checkout/subscription`,
    CHECKOUT_TOPUP: `${BASE_URL}/api/billing/checkout/topup`,
    DOWNGRADE: `${BASE_URL}/api/billing/downgrade`,
    TRANSACTION: (id) => `${BASE_URL}/api/billing/transactions/${id}`,
  },
};
