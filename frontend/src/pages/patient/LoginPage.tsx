import React, { useState, useEffect } from 'react';
import { useNavigate, Link, useLocation, useSearchParams } from 'react-router-dom';
import {
  ArrowRight,
  Lock,
  Mail,
  AlertCircle,
  Building2,
  User,
  Sparkles,
  Eye,
  EyeOff,
  ShieldCheck,
} from 'lucide-react';
import { BrandLogo } from '../../components/BrandLogo';
import { authApi } from '../../api/auth';
import { useAuth } from '../../store/AuthContext';
import { extractErrorMessage } from '../../api/client';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { login } = useAuth();

  const from =
    (location.state as { from?: { pathname: string } } | null)?.from?.pathname ??
    '/dashboard';

  const initialPortal =
    searchParams.get('portal') === 'staff' || from.startsWith('/staff')
      ? 'staff'
      : 'patient';

  const [portalTab, setPortalTab] = useState<'patient' | 'staff'>(initialPortal);
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get('portal') === 'staff' || from.startsWith('/staff')) {
      setPortalTab('staff');
    }
  }, [searchParams, from]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      const resp = await authApi.login({ identifier: identifier.trim(), password });
      login(resp.access_token, resp.user);
      if (resp.user.role === 'staff' || resp.user.role === 'admin') {
        navigate('/staff');
      } else {
        navigate(from.startsWith('/staff') || from === '/hospitals' ? '/dashboard' : from);
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickLogin = async (ident: string, pass: string) => {
    setError(null);
    setIsLoading(true);
    setIdentifier(ident);
    setPassword(pass);
    try {
      const resp = await authApi.login({ identifier: ident, password: pass });
      login(resp.access_token, resp.user);
      if (resp.user.role === 'staff' || resp.user.role === 'admin') {
        navigate('/staff');
      } else {
        navigate(from.startsWith('/staff') ? '/hospitals' : from);
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center font-sans py-8 sm:py-12 px-4 sm:px-6 selection:bg-blue-100 selection:text-blue-900">
      <div className="max-w-5xl w-full grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
        {/* Left Column: Product Identity & Flow Visual (Desktop) */}
        <div className="lg:col-span-6 space-y-6 text-left">
          <BrandLogo size="md" showTagline={true} linkTo="/" />

          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200/80 text-blue-800 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              <span>Real-Time Clinical Flow</span>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 tracking-tight leading-[1.15]">
              Know when you'll be seen.
            </h1>

            <p className="text-sm sm:text-base text-slate-600 leading-relaxed max-w-lg">
              Continuous AI queue forecasting that dynamically recalculates consultation windows
              so patients arrive right on time without crowded clinic waits.
            </p>
          </div>

          {/* Calm Intelligence Flow Indicator */}
          <div className="p-5 rounded-3xl bg-white border border-slate-200/90 shadow-2xs space-y-3 hidden sm:block">
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 block">
              The Live Flow Pipeline
            </span>
            <div className="grid grid-cols-3 gap-2 text-left">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80">
                <span className="text-[10px] font-bold text-blue-600 block">01 / QUEUE</span>
                <p className="text-xs font-bold text-slate-900 mt-0.5">Digital Token</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Instant queue spot</p>
              </div>
              <div className="p-3 rounded-xl bg-blue-50/70 border border-blue-200/80">
                <span className="text-[10px] font-bold text-blue-700 block">02 / FORECAST</span>
                <p className="text-xs font-bold text-slate-900 mt-0.5">Pacing Model</p>
                <p className="text-[11px] text-slate-600 mt-0.5">±5 min uncertainty</p>
              </div>
              <div className="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200/80">
                <span className="text-[10px] font-bold text-emerald-700 block">03 / ARRIVAL</span>
                <p className="text-xs font-bold text-slate-900 mt-0.5">Smart Plan</p>
                <p className="text-[11px] text-slate-600 mt-0.5">Travel-aware departure</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500 pt-1">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Authoritative server-side reforecasting with WebSockets</span>
            </div>
          </div>
        </div>

        {/* Right Column: Premium Authentication Card */}
        <div className="lg:col-span-6 w-full max-w-md mx-auto">
          <div className="bg-white p-7 sm:p-9 border border-slate-200/90 rounded-3xl shadow-sm space-y-6">
            {/* Header & Portal Switcher */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-black text-slate-900 tracking-tight">
                    Welcome back
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {portalTab === 'staff'
                      ? 'Sign in to hospital reception & triage operations'
                      : 'Sign in to access your digital OPD queue ticket'}
                  </p>
                </div>
              </div>

              {/* Portal Selector Tabs */}
              <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 rounded-xl border border-slate-200 text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => {
                    setPortalTab('patient');
                    setError(null);
                  }}
                  className={`flex items-center justify-center gap-2 py-2 rounded-lg transition-all cursor-pointer ${
                    portalTab === 'patient'
                      ? 'bg-white text-slate-900 shadow-2xs font-bold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <User className="w-3.5 h-3.5 text-blue-600" />
                  <span>Patient Portal</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPortalTab('staff');
                    setError(null);
                  }}
                  className={`flex items-center justify-center gap-2 py-2 rounded-lg transition-all cursor-pointer ${
                    portalTab === 'staff'
                      ? 'bg-slate-900 text-white shadow-2xs font-bold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Building2 className="w-3.5 h-3.5 text-blue-400" />
                  <span>Hospital Staff</span>
                </button>
              </div>
            </div>

            {/* 1-Click Demo Shortcut */}
            <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/90 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                  {portalTab === 'staff' ? 'Staff Demo Accounts (5 Hospitals)' : 'Patient Demo Accounts (10)'}
                </span>
                <span className="text-[10px] text-blue-600 font-semibold">Click to sign in</span>
              </div>

              {portalTab === 'staff' ? (
                // 5 distinct staff accounts — one per hospital
                <div className="space-y-1.5">
                  {([
                    { hospital: 'KEM Hospital', email: 'staff.kem@qflow.com' },
                    { hospital: 'BYL Nair Hospital', email: 'staff.nair@qflow.com' },
                    { hospital: 'Sion Hospital', email: 'staff.sion@qflow.com' },
                    { hospital: 'Sir J.J. Hospital', email: 'staff.jj@qflow.com' },
                    { hospital: 'Rajawadi Hospital', email: 'staff.rajawadi@qflow.com' },
                  ] as const).map(({ hospital, email }) => (
                    <button
                      key={email}
                      type="button"
                      onClick={() => handleQuickLogin(email, 'password123')}
                      className="w-full text-left px-3.5 py-2 rounded-xl bg-white border border-slate-200 hover:border-slate-400 hover:bg-slate-50 transition-all text-xs flex items-center justify-between text-slate-800 font-medium shadow-2xs cursor-pointer"
                    >
                      <div>
                        <span className="font-bold text-slate-900">{hospital}:</span>{' '}
                        <span className="text-slate-500 font-mono">{email}</span>
                      </div>
                      <span className="text-[10px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded-md font-bold border border-slate-200/60 shrink-0 ml-2">
                        1-Click
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                // 10 distinct patient demo accounts
                <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                  {([
                    { num: '01', name: 'Aarav Sharma', email: 'patient01@qflow.com', desc: 'KEM Token #1 (Waiting)' },
                    { num: '02', name: 'Priya Patel', email: 'patient02@qflow.com', desc: 'KEM Token #2 (Waiting)' },
                    { num: '03', name: 'Rohan Verma', email: 'patient03@qflow.com', desc: 'KEM Token #3 (Waiting)' },
                    { num: '04', name: 'Ananya Iyer', email: 'patient04@qflow.com', desc: 'KEM Token #4 (Phone)' },
                    { num: '05', name: 'Vikram Singh', email: 'patient05@qflow.com', desc: 'KEM Token #5 (Booked)' },
                    { num: '06', name: 'Sneha Nair', email: 'patient06@qflow.com', desc: 'BYL Nair Gen Med' },
                    { num: '07', name: 'Aditya Joshi', email: 'patient07@qflow.com', desc: 'BYL Nair Derma' },
                    { num: '08', name: 'Meera Rao', email: 'patient08@qflow.com', desc: 'Sion Hospital' },
                    { num: '09', name: 'Karan Malhotra', email: 'patient09@qflow.com', desc: 'Sir JJ Hospital' },
                    { num: '10', name: 'Riya Sen', email: 'patient10@qflow.com', desc: 'Rajawadi Hospital' },
                  ] as const).map(({ num, name, email, desc }) => (
                    <button
                      key={email}
                      type="button"
                      onClick={() => handleQuickLogin(email, 'password123')}
                      className="w-full text-left px-3 py-1.5 rounded-xl bg-white border border-slate-200 hover:border-blue-400 hover:bg-blue-50/40 transition-all text-xs flex items-center justify-between text-slate-800 font-medium shadow-2xs cursor-pointer"
                    >
                      <div className="truncate mr-2">
                        <span className="font-bold text-slate-900">Patient {num}</span>{' '}
                        <span className="text-slate-600 font-medium">({name})</span>
                        <div className="text-[11px] text-slate-400 font-mono truncate">{email} • {desc}</div>
                      </div>
                      <span className="text-[10px] bg-blue-50 text-blue-700 px-2 py-0.5 rounded-md font-bold border border-blue-200/60 shrink-0">
                        1-Click
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Login Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
                  {portalTab === 'staff' ? 'Staff Email or ID *' : 'Email or Phone Number *'}
                </label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="text"
                    name="identifier"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    required
                    placeholder={
                      portalTab === 'staff' ? 'staff@qflow.com' : 'patient@example.com or +91...'
                    }
                    autoComplete="username"
                    className="w-full pl-10 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
                  Password *
                </label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    className="w-full pl-10 pr-10 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 focus:outline-hidden"
                    title={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-600" />
                  <span>{error}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading || !identifier.trim() || !password}
                className={`w-full inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm shadow-xs transition-all disabled:opacity-50 text-white cursor-pointer ${
                  portalTab === 'staff'
                    ? 'bg-slate-900 hover:bg-slate-800 active:bg-slate-950'
                    : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'
                }`}
              >
                <span>
                  {isLoading
                    ? 'Signing In...'
                    : portalTab === 'staff'
                    ? 'Sign In to Operations'
                    : 'Sign In to Patient Portal'}
                </span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>

            <div className="pt-4 border-t border-slate-100 text-center text-xs text-slate-500 space-y-2">
              {portalTab === 'patient' ? (
                <p>
                  New patient to Q-FLOW?{' '}
                  <Link to="/register" className="font-bold text-blue-600 hover:underline">
                    Create an account
                  </Link>
                </p>
              ) : (
                <p className="text-slate-400">
                  Staff credentials are provisioned by hospital administration.
                </p>
              )}
              <p>
                <Link to="/" className="text-slate-400 hover:text-slate-600 inline-flex items-center gap-1">
                  <span>← Back to landing</span>
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
