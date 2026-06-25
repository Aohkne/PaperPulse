import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MathJaxContext } from 'better-react-mathjax';
import ChatLayout from '@/shared/components/layout/ChatLayout';
import ChatPage from '@/pages/ChatPage';
import LandingPage from '@/pages/LandingPage';
import CommunityPage from '@/pages/CommunityPage';
import AboutPage from '@/pages/content-landing/AboutPage';
import ContactPage from '@/pages/content-landing/ContactPage';
import FaqPage from '@/pages/content-landing/FaqPage';
import PrivacyPage from '@/pages/content-landing/PrivacyPage';
import TermsPage from '@/pages/content-landing/TermsPage';
import LoginPage from '@/pages/LoginPage';
import SignupPage from '@/pages/SignupPage';
import ResearchPage from '@/pages/ResearchPage';
import MyReviewsPage from '@/pages/MyReviewsPage';
import ReviewDetailPage from '@/pages/ReviewDetailPage';
import PDFAgentPage from '@/pages/PDFAgentPage';
import ProtectedRoute from '@/shared/components/ProtectedRoute';
import AdminRoute from '@/shared/components/AdminRoute';
import AdminLayout from '@/pages/admin/AdminLayout';
import DashboardPage from '@/pages/admin/DashboardPage';
import UserManagementPage from '@/pages/admin/UserManagementPage';
import CommunityModerationPage from '@/pages/admin/CommunityModerationPage';
import RevenuePage from '@/pages/admin/RevenuePage';
import LiteratureReviewTestingPage from '@/pages/admin/LiteratureReviewTestingPage';
import ResearchGapTestingPage from '@/pages/admin/ResearchGapTestingPage';
import { ThemeProvider } from '@/shared/providers/ThemeProvider';
import { ROUTES } from '@/shared/constant/routes';
import './index.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <MathJaxContext>
        <BrowserRouter>
          <Routes>
            {/* Public */}
            <Route path={ROUTES.HOME} element={<LandingPage />} />
            <Route path={ROUTES.COMMUNITY} element={<CommunityPage />} />
            <Route path={ROUTES.ABOUT}   element={<AboutPage />} />
            <Route path={ROUTES.CONTACT} element={<ContactPage />} />
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
        </BrowserRouter>
      </MathJaxContext>
    </ThemeProvider>
  </StrictMode>
);
