import { Navigate, Route, Routes } from 'react-router-dom';
import type { ReactNode } from 'react';
import { lazy, Suspense } from 'react';
import { useAuth } from './auth/AuthContext';
import Layout from './components/Layout';
import { ErrorState, Spinner } from './components/ui';
import type { Role } from './api/types';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Requests from './pages/Requests';
import Approvals from './pages/Approvals';
import Academy from './pages/Academy';
import CourseView from './pages/CourseView';
import Assistant from './pages/Assistant';
import Notifications from './pages/Notifications';
import Administration from './pages/Administration';
const Branches = lazy(() => import('./pages/Branches'));
const Integrations = lazy(() => import('./pages/Integrations'));

function RoleGuard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) {
    return (
      <div className="state state-error">
        <strong>Нет доступа</strong>
        <span>{roles.includes('manager') ? 'Этот раздел доступен только руководителю и HR.' : 'Этот раздел доступен только HR.'}</span>
      </div>
    );
  }
  return <>{children}</>;
}

export default function App() {
  const { user, booting, bootError, retryBoot } = useAuth();

  if (booting) return <div className="boot"><Spinner label="Проверяем сессию…" /></div>;
  if (bootError) {
    return (
      <div className="boot">
        <ErrorState error={bootError} onRetry={retryBoot} />
      </div>
    );
  }
  if (!user) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="requests" element={<Requests />} />
        <Route
          path="approvals"
          element={
            <RoleGuard roles={['manager', 'hr']}>
              <Approvals />
            </RoleGuard>
          }
        />
        <Route path="academy" element={<Academy />} />
        <Route path="academy/:id" element={<CourseView />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="branches" element={<Suspense fallback={<Spinner />}><Branches /></Suspense>} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="admin" element={<RoleGuard roles={['hr']}><Administration /></RoleGuard>} />
        <Route path="integrations" element={<RoleGuard roles={['hr']}><Suspense fallback={<Spinner />}><Integrations /></Suspense></RoleGuard>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
