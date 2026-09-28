import { Link, useNavigate } from 'react-router-dom';
import { BrandLogo } from './BrandLogo';
import { useAuth } from '../store/AuthContext';
import { Building2, LogOut, User, LayoutDashboard, Stethoscope } from 'lucide-react';

export function HeaderNav() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="border-b border-slate-200/90 bg-white/90 backdrop-blur-md sticky top-0 z-30 transition-all">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <BrandLogo
          showTagline={false}
          size="sm"
          linkTo={user?.role === 'staff' || user?.role === 'admin' ? '/staff' : '/'}
        />

        <div className="flex items-center gap-3">
          {isAuthenticated && user ? (
            <div className="flex items-center gap-2.5">
              <span className="hidden sm:inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 bg-slate-100/90 border border-slate-200/80 px-3 py-1 rounded-full">
                <User className="w-3.5 h-3.5 text-blue-600" />
                <span className="max-w-[140px] truncate">{user.name}</span>
                <span className="text-[10px] text-slate-400 font-bold uppercase">({user.role})</span>
              </span>

              {user.role === 'staff' || user.role === 'admin' ? (
                <Link
                  to="/staff"
                  className="text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white px-3.5 py-2 rounded-xl transition-all shadow-xs inline-flex items-center gap-1.5"
                >
                  <LayoutDashboard className="w-3.5 h-3.5 text-blue-400" />
                  <span>Control Center</span>
                </Link>
              ) : (
                <div className="flex items-center gap-2">
                  <Link
                    to="/dashboard"
                    className="text-xs font-semibold text-slate-700 hover:text-slate-900 px-3 py-2 rounded-xl hover:bg-slate-100 transition-colors inline-flex items-center gap-1.5"
                  >
                    <LayoutDashboard className="w-3.5 h-3.5 text-blue-600" />
                    <span>My Appointments</span>
                  </Link>
                  <Link
                    to="/book"
                    className="text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white px-3.5 py-2 rounded-xl transition-all shadow-xs inline-flex items-center gap-1.5"
                  >
                    <Stethoscope className="w-3.5 h-3.5 text-white" />
                    <span>Book Appointment</span>
                  </Link>
                </div>
              )}

              <button
                type="button"
                onClick={() => void logout().then(() => navigate('/login'))}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                to="/staff"
                className="text-xs font-semibold text-slate-700 hover:text-slate-900 border border-slate-200/90 bg-white hover:bg-slate-50 px-3 py-2 rounded-xl transition-all shadow-2xs inline-flex items-center gap-1.5"
              >
                <Building2 className="w-3.5 h-3.5 text-blue-600" />
                <span>Staff Portal</span>
              </Link>
              <Link
                to="/login"
                className="text-xs font-medium text-slate-600 hover:text-slate-900 px-3 py-2 rounded-xl hover:bg-slate-100 transition-colors"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                className="text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white px-3.5 py-2 rounded-xl transition-all shadow-xs"
              >
                Register
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
