import type { ReactNode } from 'react';
import { ArrowLeft, Activity } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../store/AuthContext';

interface PageHeaderProps {
  title?: string;
  subtitle?: string;
  backTo?: string;
  showBack?: boolean;
  rightAction?: ReactNode;
}

export function PageHeader({
  title,
  subtitle,
  backTo,
  showBack = true,
  rightAction,
}: PageHeaderProps) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleBack = () => {
    if (backTo) {
      navigate(backTo);
    } else {
      navigate(-1);
    }
  };

  return (
    <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-slate-200/80">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {showBack && (
            <button
              type="button"
              onClick={handleBack}
              className="p-2 -ml-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              aria-label="Go back"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          )}

          <Link to="/" className="flex items-center gap-2 font-black text-slate-900 tracking-tight">
            <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-xs">
              <Activity className="w-4 h-4" />
            </div>
            <span className="text-lg">Q-FLOW</span>
          </Link>
        </div>

        <div className="flex items-center gap-3">
          {rightAction}

          {user ? (
            <div className="flex items-center gap-2 text-xs">
              <span className="hidden sm:inline-block font-medium text-slate-600 bg-slate-100 px-2.5 py-1 rounded-full">
                {user.name} ({user.role})
              </span>
              <button
                type="button"
                onClick={() => logout()}
                className="text-slate-500 hover:text-red-600 px-2 py-1 rounded-lg hover:bg-slate-100 transition-colors"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                to="/login"
                className="text-xs font-semibold text-slate-700 hover:text-blue-600 px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors"
              >
                Log In
              </Link>
              <Link
                to="/register"
                className="text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg shadow-2xs transition-colors"
              >
                Register
              </Link>
            </div>
          )}
        </div>
      </div>

      {(title || subtitle) && (
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
          <div>
            {title && <h1 className="text-base sm:text-lg font-bold text-slate-900">{title}</h1>}
            {subtitle && <p className="text-xs sm:text-sm text-slate-500">{subtitle}</p>}
          </div>
        </div>
      )}
    </header>
  );
}
