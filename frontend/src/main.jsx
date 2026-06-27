import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MathJaxContext } from 'better-react-mathjax';
import { Toaster } from 'sonner';
import ChatLayout from '@/shared/components/layout/ChatLayout';
import ChatPage from '@/pages/ChatPage';
import LandingPage from '@/pages/LandingPage';
import CommunityPage from '@/pages/CommunityPage';
import LoginPage from '@/pages/LoginPage';
import SignupPage from '@/pages/SignupPage';
import ProtectedRoute from '@/shared/components/ProtectedRoute';
import AdminRoute from '@/shared/components/AdminRoute';
import PageSkeleton from '@/shared/components/ui/PageSkeleton';
import ScrollToTop from '@/shared/components/ScrollToTop';
import { ThemeProvider } from '@/shared/providers/ThemeProvider';
import { ROUTES } from '@/shared/constant/routes';
import './index.css';

// Lazy-loaded routes (optimize_Plan.html §1.1) — these pull in the heaviest
// deps (Monaco Editor, react-sigma/graphology, recharts) and shouldn't be in
// the initial bundle landing-page visitors download. Kept eager: LandingPage,
// CommunityPage, LoginPage, SignupPage, ChatPage — most-visited entry points.
const AboutPage = lazy(() => import('@/pages/content-landing/AboutPage'));
const FaqPage = lazy(() => import('@/pages/content-landing/FaqPage'));
const PrivacyPage = lazy(() => import('@/pages/content-landing/PrivacyPage'));
const TermsPage = lazy(() => import('@/pages/content-landing/TermsPage'));
const ResearchPage = lazy(() => import('@/pages/ResearchPage'));
const MyReviewsPage = lazy(() => import('@/pages/MyReviewsPage'));
const ReviewDetailPage = lazy(() => import('@/pages/ReviewDetailPage'));
const PDFAgentPage = lazy(() => import('@/pages/PDFAgentPage'));
const AdminLayout = lazy(() => import('@/pages/admin/AdminLayout'));
const DashboardPage = lazy(() => import('@/pages/admin/DashboardPage'));
const UserManagementPage = lazy(() => import('@/pages/admin/UserManagementPage'));
const CommunityModerationPage = lazy(() => import('@/pages/admin/CommunityModerationPage'));
const RevenuePage = lazy(() => import('@/pages/admin/RevenuePage'));
const LiteratureReviewTestingPage = lazy(() => import('@/pages/admin/LiteratureReviewTestingPage'));
const ResearchGapTestingPage = lazy(() => import('@/pages/admin/ResearchGapTestingPage'));

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <MathJaxContext>
        <Toaster position="top-center" closeButton />
        <BrowserRouter>
          <ScrollToTop />
          <Suspense fallback={<PageSkeleton />}>
            <Routes>
              {/* Public */}
              <Route path={ROUTES.HOME} element={<LandingPage />} />
              <Route path={ROUTES.COMMUNITY} element={<CommunityPage />} />
              <Route path={ROUTES.ABOUT}   element={<AboutPage />} />
              <Route path={ROUTES.FAQ}     element={<FaqPage />} />
              <Route path={ROUTES.PRIVACY} element={<PrivacyPage />} />
              <Route path={ROUTES.TERMS}   element={<TermsPage />} />
              <Route path={ROUTES.LOGIN} element={<LoginPage />} />
              <Route path={ROUTES.SIGNUP} element={<SignupPage />} />

              {/* User app */}
              <Route path={ROUTES.APP} element={
                <ProtectedRoute>
                  <ChatLayout><ChatPage /></ChatLayout>
                </ProtectedRoute>
              } />
              <Route path={ROUTES.RESEARCH} element={
                <ProtectedRoute>
                  <ChatLayout><ResearchPage /></ChatLayout>
                </ProtectedRoute>
              } />
              <Route path={ROUTES.MY_REVIEWS} element={
                <ProtectedRoute>
                  <ChatLayout><MyReviewsPage /></ChatLayout>
                </ProtectedRoute>
              } />
              <Route path="/app/reviews/:id" element={
                <ProtectedRoute>
                  <ChatLayout><ReviewDetailPage /></ChatLayout>
                </ProtectedRoute>
              } />
              <Route path={ROUTES.PDF_AGENT} element={
                <ProtectedRoute>
                  <ChatLayout><PDFAgentPage /></ChatLayout>
                </ProtectedRoute>
              } />

              {/* Admin */}
              <Route path={ROUTES.ADMIN} element={
                <AdminRoute>
                  <AdminLayout />
                </AdminRoute>
              }>
                <Route index element={<Navigate to={ROUTES.ADMIN_DASHBOARD} replace />} />
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="user-management" element={<UserManagementPage />} />
                <Route path="community" element={<CommunityModerationPage />} />
                <Route path="revenue" element={<RevenuePage />} />
                <Route path="testing/literature-review" element={<LiteratureReviewTestingPage />} />
                <Route path="testing/research-gap" element={<ResearchGapTestingPage />} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </MathJaxContext>
    </ThemeProvider>
  </StrictMode>
);
