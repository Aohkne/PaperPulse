import { lazy } from 'react';

export const AboutPage = lazy(() => import('@/pages/content-landing/AboutPage'));
export const FaqPage = lazy(() => import('@/pages/content-landing/FaqPage'));
export const PrivacyPage = lazy(() => import('@/pages/content-landing/PrivacyPage'));
export const TermsPage = lazy(() => import('@/pages/content-landing/TermsPage'));
export const ResearchPage = lazy(() => import('@/pages/ResearchPage'));
export const MyReviewsPage = lazy(() => import('@/pages/MyReviewsPage'));
export const ReviewDetailPage = lazy(() => import('@/pages/ReviewDetailPage'));
export const PDFAgentPage = lazy(() => import('@/pages/PDFAgentPage'));
export const AdminLayout = lazy(() => import('@/pages/admin/AdminLayout'));
export const DashboardPage = lazy(() => import('@/pages/admin/DashboardPage'));
export const UserManagementPage = lazy(() => import('@/pages/admin/UserManagementPage'));
export const UsageManagementPage = lazy(() => import('@/pages/admin/UsageManagementPage'));
export const CommunityModerationPage = lazy(() => import('@/pages/admin/CommunityModerationPage'));
export const RevenuePage = lazy(() => import('@/pages/admin/RevenuePage'));
export const LiteratureReviewTestingPage = lazy(() => import('@/pages/admin/LiteratureReviewTestingPage'));
export const ResearchGapTestingPage = lazy(() => import('@/pages/admin/ResearchGapTestingPage'));
