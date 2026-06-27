export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  SIGNUP: '/signup',
  APP: '/app',
  RESEARCH: '/app/research',
  SURVEY: '/survey',
  MY_REVIEWS: '/app/reviews',
  REVIEW_DETAIL: (id) => `/app/reviews/${id}`,
  PDF_AGENT: '/app/pdf-agent',
  COMMUNITY: '/community',

  // Content pages
  ABOUT: '/about',
  FAQ: '/faq',
  PRIVACY: '/privacy',
  TERMS: '/terms',

  // ADMIN
  ADMIN: '/admin',
  ADMIN_DASHBOARD: '/admin/dashboard',
  ADMIN_USERS: '/admin/user-management',
  ADMIN_COMMUNITY: '/admin/community',
  ADMIN_REVENUE: '/admin/revenue',
  ADMIN_TESTING_LITERATURE_REVIEW: '/admin/testing/literature-review',
  ADMIN_TESTING_RESEARCH_GAP: '/admin/testing/research-gap',
};
