import { Navigate } from 'react-router-dom';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
};

export default ProtectedRoute;
