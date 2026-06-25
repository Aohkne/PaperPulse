import { Navigate } from 'react-router-dom';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { ROUTES } from '@/shared/constant/routes';

const AdminRoute = ({ children }) => {
  const { isAuthenticated, user } = useAuthStore();
  if (!isAuthenticated) return <Navigate to={ROUTES.LOGIN} replace />;
  if (user?.role !== 'admin') return <Navigate to={ROUTES.APP} replace />;
  return children;
};

export default AdminRoute;
