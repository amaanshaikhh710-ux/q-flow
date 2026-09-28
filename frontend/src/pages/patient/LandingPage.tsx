import { Link, useNavigate } from 'react-router-dom';
import {
  Clock,
  Navigation,
  ShieldCheck,
  Zap,
  Users,
  ChevronRight,
  TrendingUp,
  Sparkles,
  AlertTriangle,
  Bell,
} from 'lucide-react';
import { HeaderNav } from '../../components/HeaderNav';
import { useEffect } from 'react';
import { useAuth } from '../../store/AuthContext';
import { Button } from '../../components/Button';

export default function LandingPage() {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();

  useEffect(() => {
    if (isAuthenticated && (user?.role === 'staff' || user?.role === 'admin')) {
      navigate('/staff', { replace: true });
    }
  }, [isAuthenticated, user, navigate]);

  const handleTrackQueue = () => {
    const token = localStorage.getItem('qflow_token');
    if (token) {
      navigate('/dashboard');
    } else {
      navigate('/login');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col text-slate-900 font-sans selection:bg-blue-100 selection:text-blue-900">
      <HeaderNav />

      <main className="flex-1">
        {/* Hero Section */}
        <section className="py-16 sm:py-24 px-4 sm:px-6 max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-50 border border-blue-200/80 text-blue-800 text-xs font-semibold mb-6 animate-fade-up shadow-2xs">
            <Sparkles className="w-3.5 h-3.5 text-blue-600" />
            <span>AI-Powered OPD Queue Intelligence</span>
          </div>

          <h1 className="text-4xl sm:text-6xl font-black text-slate-900 tracking-tight leading-[1.12] mb-6 animate-fade-up">
            Know when you'll be seen.
          </h1>

          <p className="text-base sm:text-xl text-slate-600 max-w-2xl mx-auto mb-10 leading-relaxed font-normal animate-fade-up">
            AI-powered OPD queue forecasting that helps patients arrive at the right time
            instead of waiting at the hospital.
          </p>

          {/* Primary & Secondary CTAs */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3.5 mb-16 animate-fade-up">
            <Link to="/book" className="w-full sm:w-auto">
              <Button size="lg" className="w-full sm:w-auto gap-2 text-base px-8 bg-slate-900 hover:bg-slate-800 shadow-sm">
                <span>Book an Appointment</span>
                <ChevronRight className="w-4 h-4 text-blue-400" />
              </Button>
            </Link>

            <Button
              type="button"
              variant="secondary"
              size="lg"
              onClick={handleTrackQueue}
              className="w-full sm:w-auto text-base px-7"
            >
              <span>Track My Queue</span>
            </Button>
          </div>

          {/* 5-Stage Live Product Visualization Pipeline */}
          <div className="max-w-4xl mx-auto bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/90 shadow-xs animate-fade-up">
            <div className="flex items-center justify-between mb-6">
              <div className="text-left">
                <span className="text-[11px] font-bold text-blue-600 uppercase tracking-wider">
                  The Q-FLOW Pipeline
                </span>
                <h2 className="text-base font-bold text-slate-900 mt-0.5">
                  How Patient Flow Works in Real Time
                </h2>
              </div>
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live Engine
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
              {/* Stage 1 */}
              <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 text-left flex flex-col justify-between">
                <div className="w-8 h-8 rounded-xl bg-slate-200 text-slate-700 font-bold text-xs flex items-center justify-center mb-2">
                  01
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">Patient</h3>
                  <p className="text-[11px] text-slate-500 mt-0.5">Selects doctor & session digitally</p>
                </div>
              </div>

              {/* Stage 2 */}
              <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 text-left flex flex-col justify-between">
                <div className="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 font-bold text-xs flex items-center justify-center mb-2">
                  02
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">Live Queue</h3>
                  <p className="text-[11px] text-slate-500 mt-0.5">Enters queue with verifiable token</p>
                </div>
              </div>

              {/* Stage 3 */}
              <div className="p-3.5 rounded-2xl bg-blue-50/70 border border-blue-200 text-left flex flex-col justify-between">
                <div className="w-8 h-8 rounded-xl bg-blue-600 text-white font-bold text-xs flex items-center justify-center mb-2">
                  03
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">AI Forecast</h3>
                  <p className="text-[11px] text-slate-600 mt-0.5">Uncertainty window: ±8 min</p>
                </div>
              </div>

              {/* Stage 4 */}
              <div className="p-3.5 rounded-2xl bg-indigo-50/60 border border-indigo-200 text-left flex flex-col justify-between">
                <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white font-bold text-xs flex items-center justify-center mb-2">
                  04
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">Arrival Window</h3>
                  <p className="text-[11px] text-slate-600 mt-0.5">Travel-aware departure time</p>
                </div>
              </div>

              {/* Stage 5 */}
              <div className="p-3.5 rounded-2xl bg-emerald-50/60 border border-emerald-200 text-left flex flex-col justify-between">
                <div className="w-8 h-8 rounded-xl bg-emerald-600 text-white font-bold text-xs flex items-center justify-center mb-2">
                  05
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">Consultation</h3>
                  <p className="text-[11px] text-slate-600 mt-0.5">Zero waiting room congestion</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 3 Core Feature Cards */}
        <section className="py-14 bg-white border-y border-slate-200/90 px-4 sm:px-6">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-10">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700 bg-blue-50 border border-blue-200/80 px-3 py-1 rounded-full">
                Core Innovation
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 mt-3">
                Built For Clinical Realities
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 max-w-xl mx-auto mt-1">
                Hospital queues are chaotic. Q-FLOW replaces blind waiting with continuous mathematical certainty.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="p-6 rounded-2xl bg-slate-50 border border-slate-200/70 hover:border-blue-300 transition-colors">
                <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center mb-4">
                  <TrendingUp className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">
                  Probabilistic Service Modeling
                </h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Doctor consult times are not fixed averages. Q-FLOW fits lognormal service distributions with honest confidence bounds.
                </p>
              </div>

              <div className="p-6 rounded-2xl bg-slate-50 border border-slate-200/70 hover:border-blue-300 transition-colors">
                <div className="w-12 h-12 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center mb-4">
                  <Clock className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">
                  Dynamic Reforecast
                </h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  When emergency patients are inserted, doctor breaks happen, or consultations run long, downstream patients are immediately reforecasted in real-time.
                </p>
              </div>

              <div className="p-6 rounded-2xl bg-slate-50 border border-slate-200/70 hover:border-blue-300 transition-colors">
                <div className="w-12 h-12 rounded-xl bg-indigo-100 text-indigo-600 flex items-center justify-center mb-4">
                  <Navigation className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">
                  Smart Arrival Planning
                </h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Combines estimated consultation time with traffic-aware transit duration to suggest the exact moment patients should leave home.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Signature Innovation Section: Dynamic Recalculation */}
        <section className="py-16 px-4 sm:px-6 max-w-5xl mx-auto">
          <div className="bg-slate-900 rounded-3xl p-8 sm:p-12 text-white border border-slate-800 shadow-xl">
            <div className="max-w-2xl mb-8">
              <span className="text-[11px] font-bold uppercase tracking-wider text-blue-400 bg-blue-950/80 border border-blue-800/80 px-3 py-1 rounded-full">
                The Innovation
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold mt-3 text-white">
                "Your queue is always changing.
                <br />
                Q-FLOW keeps recalculating."
              </h2>
              <p className="text-xs sm:text-sm text-slate-300 mt-2 leading-relaxed">
                Hospital OPDs face constant disruptions. When an emergency case arrives, static queues break down. Q-FLOW dynamically recalculates the exact downstream impact in real time.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3.5">
              <div className="p-4 rounded-2xl bg-slate-800/80 border border-slate-700/80 space-y-1.5">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">01 Baseline</span>
                <h4 className="text-sm font-bold text-white">Normal Queue</h4>
                <p className="text-xs text-slate-300">Initial estimate: 10:40 AM window</p>
              </div>

              <div className="p-4 rounded-2xl bg-red-950/40 border border-red-800/80 space-y-1.5">
                <span className="text-[10px] font-bold text-red-400 uppercase tracking-wider flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  02 Disruption
                </span>
                <h4 className="text-sm font-bold text-white">Emergency Insert</h4>
                <p className="text-xs text-slate-300">Urgent case triage called ahead</p>
              </div>

              <div className="p-4 rounded-2xl bg-amber-950/40 border border-amber-700/80 space-y-1.5">
                <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">03 Recalculation</span>
                <h4 className="text-sm font-bold text-white">ETA Updated</h4>
                <p className="text-xs text-slate-300">New estimate: 11:05 AM (+25m)</p>
              </div>

              <div className="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-700/80 space-y-1.5">
                <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1">
                  <Bell className="w-3 h-3 text-emerald-400" />
                  04 Real-Time
                </span>
                <h4 className="text-sm font-bold text-white">Patient Notified</h4>
                <p className="text-xs text-slate-300">WebSocket alert & updated departure</p>
              </div>
            </div>
          </div>
        </section>

        {/* Trust Section */}
        <section className="py-12 px-4 sm:px-6 max-w-5xl mx-auto">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 text-center">
            <div className="flex flex-col items-center">
              <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center mb-3">
                <Zap className="w-5 h-5" />
              </div>
              <h4 className="text-sm font-bold text-slate-900">Real-Time WebSocket</h4>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                Authoritative instant synchronization with automatic REST snapshot recovery
              </p>
            </div>

            <div className="flex flex-col items-center">
              <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center mb-3">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h4 className="text-sm font-bold text-slate-900">Privacy-Aware Design</h4>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                Strict zero-PII leak policy across all public snapshots and WebSocket feeds
              </p>
            </div>

            <div className="flex flex-col items-center">
              <div className="w-10 h-10 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center mb-3">
                <Users className="w-5 h-5" />
              </div>
              <h4 className="text-sm font-bold text-slate-900">Uncertainty-Aware</h4>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                Honest probabilistic margins prevent patient frustration and missed visits
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 px-4 sm:px-6 text-center text-xs text-slate-500">
        <p>© 2026 Q-FLOW Healthcare Intelligence. Problem Statement CX0308.</p>
      </footer>
    </div>
  );
}
