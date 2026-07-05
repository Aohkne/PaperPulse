import { StrictMode, Suspense } from 'react';
import { MathJaxContext } from 'better-react-mathjax';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'sonner';
import ChatPage from '@/pages/ChatPage';
import CommunityPage from '@/pages/CommunityPage';
import LandingPage from '@/pages/LandingPage';
import LoginPage from '@/pages/LoginPage';
import SignupPage from '@/pages/SignupPage';
import AdminRoute from '@/shared/components/AdminRoute';
import ProtectedRoute from '@/shared/components/ProtectedRoute';
import ScrollToTop from '@/shared/components/ScrollToTop';
import ChatLayout from '@/shared/components/layout/ChatLayout';
import PageSkeleton from '@/shared/components/ui/PageSkeleton';
import { ROUTES } from '@/shared/constant/routes';
import {
  AboutPage,
  AdminLayout,
  CommunityModerationPage,
  DashboardPage,
  FaqPage,
  LiteratureReviewTestingPage,
  MyReviewsPage,
  PDFAgentPage,
  PrivacyPage,
  ResearchGapTestingPage,
  ResearchPage,
  ReviewDetailPage,
  RevenuePage,
  TermsPage,
  UsageManagementPage,
  UserManagementPage,
} from '@/shared/constant/lazyRoutes';
import { ThemeProvider } from '@/shared/providers/ThemeProvider';
import './index.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <MathJaxContext>
        <Toaster position="top-center" closeButton />
        <BrowserRouter>
          <ScrollToTop />
          <Suspense fallback={<PageSkeleton />}>
            <Routes>
              <Route path={ROUTES.HOME} element={<LandingPage />} />
              <Route path={ROUTES.COMMUNITY} element={<CommunityPage />} />
              <Route path={ROUTES.ABOUT} element={<AboutPage />} />
              <Route path={ROUTES.FAQ} element={<FaqPage />} />
              <Route path={ROUTES.PRIVACY} element={<PrivacyPage />} />
              <Route path={ROUTES.TERMS} element={<TermsPage />} />
              <Route path={ROUTES.LOGIN} element={<LoginPage />} />
              <Route path={ROUTES.SIGNUP} element={<SignupPage />} />

              <Route
                path={ROUTES.APP}
                element={
                  <ProtectedRoute>
                    <ChatLayout>
                      <ChatPage />
                    </ChatLayout>
                  </ProtectedRoute>
                }
              />
              <Route
                path={ROUTES.RESEARCH}
                element={
                  <ProtectedRoute>
                    <ChatLayout>
                      <ResearchPage />
                    </ChatLayout>
                  </ProtectedRoute>
                }
              />
              <Route
                path={ROUTES.MY_REVIEWS}
                element={
                  <ProtectedRoute>
                    <ChatLayout>
                      <MyReviewsPage />
                    </ChatLayout>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/app/reviews/:id"
                element={
                  <ProtectedRoute>
                    <ChatLayout>
                      <ReviewDetailPage />
                    </ChatLayout>
                  </ProtectedRoute>
                }
              />
              <Route
                path={ROUTES.PDF_AGENT}
                element={
                  <ProtectedRoute>
                    <ChatLayout>
                      <PDFAgentPage />
                    </ChatLayout>
                  </ProtectedRoute>
                }
              />

              <Route
                path={ROUTES.ADMIN}
                element={
                  <AdminRoute>
                    <AdminLayout />
                  </AdminRoute>
                }
              >
                <Route index element={<Navigate to={ROUTES.ADMIN_DASHBOARD} replace />} />
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="user-management" element={<UserManagementPage />} />
                <Route path="usage-management" element={<UsageManagementPage />} />
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
