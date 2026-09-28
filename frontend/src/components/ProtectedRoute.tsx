import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../store/AuthContext';
import { PageSpinner } from './Spinner';
import { authApi } from '../api/auth';
import type { UserRole } from '../types/api';
import { ShieldAlert, LogIn, ArrowRight, UserCheck, Sparkles } from 'lucide-react';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: UserRole | UserRole[];
  redirectTo?: string;
}

/**
 * Route guard — frontend UX only.
 * Backend RBAC remains authoritative for all data access.
 */
export function ProtectedRoute({
  children,
  requiredRole,
  redirectTo,
}: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user, logout, login } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [isSwitching, setIsSwitching] = useState(false);

  if (isLoading) return <PageSpinner />;

  // Default redirect path: if accessing staff route, send to staff portal login
  const defaultRedirect = location.pathname.startsWith('/staff')
    ? '/login?portal=staff'
    : '/login';
  const targetRedirect = redirectTo || defaultRedirect;

  if (!isAuthenticated) {
    return <Navigate to={targetRedirect} state={{ from: location }} replace />;
  }

  if (requiredRole && user) {
    const roles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
    if (!roles.includes(user.role)) {
      // Patient trying to access staff/admin portal
      if (roles.includes('staff') || roles.includes('admin')) {
        const handleDemoStaffLogin = async () => {
          setIsSwitching(true);
          try {
            const resp = await authApi.login({
              identifier: 'staff@qflow.com',
              password: 'password123',
            });
            login(resp.access_token, resp.user);
            navigate(location.pathname);
          } catch {
            await logout();
            navigate('/login?portal=staff');
          } finally {
            setIsSwitching(false);
          }
        };

        const handleSwitchAccount = async () => {
          await logout();
          navigate('/login?portal=staff');
        };

        return (
          <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4 font-sans">
            <div className="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl space-y-6 text-center">
              <div className="w-16 h-16 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mx-auto">
                <ShieldAlert className="w-8 h-8" />
              </div>

              <div>
                <span className="text-[11px] font-bold tracking-wider uppercase text-amber-700 bg-amber-100/80 px-3 py-1 rounded-full">
                  Access Restricted
                </span>
                <h2 className="text-xl font-bold text-slate-900 mt-3">
                  Hospital Staff Access Required
                </h2>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  You are currently signed in as a Patient (<strong className="text-slate-800">{user.name}</strong>).
                  The Staff Control Center is restricted to hospital receptionists and clinic administrators.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-left space-y-2">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-700">
                  <UserCheck className="w-4 h-4 text-blue-600" />
                  <span>Current Account:</span>
                </div>
                <div className="text-xs text-slate-600 pl-6 space-y-0.5">
                  <p><strong>Name:</strong> {user.name}</p>
                  <p><strong>Role:</strong> <span className="uppercase text-amber-600 font-bold">{user.role}</span></p>
                  <p><strong>Email/Phone:</strong> {user.email || user.phone || 'N/A'}</p>
                </div>
              </div>

              <div className="space-y-2.5">
                <button
                  type="button"
                  onClick={handleDemoStaffLogin}
                  disabled={isSwitching}
                  className="w-full inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-semibold text-sm shadow-xs transition-all disabled:opacity-50"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{isSwitching ? 'Logging in as Staff...' : '1-Click Demo Staff Login (staff@qflow.com)'}</span>
                </button>

                <button
                  type="button"
                  onClick={handleSwitchAccount}
                  className="w-full inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs transition-all"
                >
                  <LogIn className="w-4 h-4" />
                  <span>Sign In with Different Staff Account</span>
                </button>

                <button
                  type="button"
                  onClick={() => navigate('/hospitals')}
                  className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs text-slate-500 hover:text-slate-700"
                >
                  <span>Return to Patient Portal</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        );
      }

      // Staff/admin trying to access patient routes → redirect to staff dashboard
      if (user.role === 'staff' || user.role === 'admin') {
        return <Navigate to="/staff" replace />;
      }
      return <Navigate to="/" replace />;
    }
  }

  return <>{children}</>;
}
