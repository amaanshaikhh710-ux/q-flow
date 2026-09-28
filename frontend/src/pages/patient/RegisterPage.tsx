import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  ArrowRight,
  User,
  Mail,
  Phone,
  Lock,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  Eye,
  EyeOff,
} from 'lucide-react';
import { BrandLogo } from '../../components/BrandLogo';
import { authApi } from '../../api/auth';
import { useAuth } from '../../store/AuthContext';
import { extractErrorMessage } from '../../api/client';

export default function RegisterPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [form, setForm] = useState({
    name: '',
    email: '',
    phone: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) {
      setError('Please enter your full name.');
      return;
    }

    if (!form.email && !form.phone) {
      setError('Please provide at least an email address or phone number.');
      return;
    }

    if (form.password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    setIsLoading(true);
    try {
      await authApi.register({
        name: form.name.trim(),
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
        password: form.password,
      });

      const tokenResp = await authApi.login({
        identifier: form.email.trim() || form.phone.trim(),
        password: form.password,
      });

      login(tokenResp.access_token, tokenResp.user);
      navigate('/hospitals');
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center font-sans py-8 sm:py-12 px-4 sm:px-6 selection:bg-blue-100 selection:text-blue-900">
      <div className="max-w-5xl w-full grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
        {/* Left Column: Product Value Proposition */}
        <div className="lg:col-span-6 space-y-6 text-left">
          <BrandLogo size="md" showTagline={true} linkTo="/" />

          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200/80 text-blue-800 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              <span>Instant Digital Access</span>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 tracking-tight leading-[1.15]">
              Wait where you want, arrive when you're seen.
            </h1>

            <p className="text-sm sm:text-base text-slate-600 leading-relaxed max-w-lg">
              Create your patient account to queue for doctor sessions remotely, receive live
              reforecasted ETAs, and plan your journey based on real-time OPD pace.
            </p>
          </div>

          <div className="space-y-3 pt-2 hidden sm:block">
            <div className="flex items-center gap-3 text-sm text-slate-700">
              <div className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <span>Digital queue token issued instantly to your phone</span>
            </div>

            <div className="flex items-center gap-3 text-sm text-slate-700">
              <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <span>Continuous AI recalculation with uncertainty intervals</span>
            </div>

            <div className="flex items-center gap-3 text-sm text-slate-700">
              <div className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <span>Traffic-aware departure notifications so you arrive right on time</span>
            </div>
          </div>
        </div>

        {/* Right Column: Registration Card */}
        <div className="lg:col-span-6 w-full max-w-md mx-auto">
          <div className="bg-white p-7 sm:p-9 border border-slate-200/90 rounded-3xl shadow-sm space-y-6">
            <div>
              <h2 className="text-2xl font-black text-slate-900 tracking-tight">
                Create Patient Account
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Register in 30 seconds to join any hospital OPD queue
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3.5">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
                  Full Legal Name *
                </label>
                <div className="relative">
                  <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="text"
                    name="name"
                    value={form.name}
                    onChange={handleChange}
                    required
                    placeholder="e.g. Rahul Verma"
                    autoComplete="name"
                    className="w-full pl-10 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="email"
                    name="email"
                    value={form.email}
                    onChange={handleChange}
                    placeholder="patient@example.com"
                    autoComplete="email"
                    className="w-full pl-10 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
                  Phone Number
                </label>
                <div className="relative">
                  <Phone className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="tel"
                    name="phone"
                    value={form.phone}
                    onChange={handleChange}
                    placeholder="+91 98765 43210"
                    autoComplete="tel"
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
                    value={form.password}
                    onChange={handleChange}
                    required
                    minLength={6}
                    placeholder="At least 6 characters"
                    autoComplete="new-password"
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

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1.5">
                  Confirm Password *
                </label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="confirmPassword"
                    value={form.confirmPassword}
                    onChange={handleChange}
                    required
                    minLength={6}
                    placeholder="Re-enter password"
                    autoComplete="new-password"
                    className="w-full pl-10 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-900 bg-slate-50 focus:bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
                  />
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
                disabled={isLoading}
                className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-semibold text-sm shadow-xs transition-all disabled:opacity-50 cursor-pointer"
              >
                <span>{isLoading ? 'Creating Account...' : 'Register & Enter Directory'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>

            <div className="pt-4 border-t border-slate-100 text-center text-xs text-slate-500 space-y-2">
              <p>
                Already have an account?{' '}
                <Link to="/login" className="font-bold text-blue-600 hover:underline">
                  Sign in here
                </Link>
              </p>
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
