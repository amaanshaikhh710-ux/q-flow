import { useState } from 'react';
import { ChevronDown, ChevronUp, Layers, Users, Clock, Activity, AlertCircle } from 'lucide-react';

interface WhyEstimateProps {
  position: number | null;
  patientsAhead: number;
  recentPaceMinutes?: number | null;
  doctorName?: string | null;
  explanation?: string | null;
  className?: string;
}

export function WhyEstimate({
  position,
  patientsAhead,
  recentPaceMinutes,
  doctorName,
  explanation,
  className = '',
}: WhyEstimateProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className={`border border-slate-200/90 rounded-2xl bg-white overflow-hidden shadow-2xs transition-all ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-slate-50/70 transition-colors cursor-pointer"
        aria-expanded={isOpen}
      >
        <span className="flex items-center gap-2 text-xs font-bold text-slate-700">
          <Layers className="w-3.5 h-3.5 text-blue-600" />
          <span>Why this estimate?</span>
        </span>
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700">
          <span>{isOpen ? 'Hide breakdown' : 'View factors'}</span>
          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </span>
      </button>

      {isOpen && (
        <div className="px-5 pb-5 pt-2 border-t border-slate-100 space-y-3.5 text-xs text-slate-600 animate-fade-up">
          <p className="font-semibold text-slate-900 text-xs">
            Q-FLOW continuously evaluates 4 real-time factors:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {/* Factor 1: Queue Position */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
              <div className="flex items-center gap-1.5 text-slate-800 font-bold text-[11px] uppercase tracking-wider">
                <Users className="w-3.5 h-3.5 text-blue-600" />
                <span>Queue Position</span>
              </div>
              <p className="text-slate-600 text-xs">
                {position != null ? `Token placed at position #${position} with ${patientsAhead} patients ahead.` : `${patientsAhead} patients currently ahead in consultation line.`}
              </p>
            </div>

            {/* Factor 2: Clinician Pacing */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
              <div className="flex items-center gap-1.5 text-slate-800 font-bold text-[11px] uppercase tracking-wider">
                <Clock className="w-3.5 h-3.5 text-indigo-600" />
                <span>Consultation Pace</span>
              </div>
              <p className="text-slate-600 text-xs">
                {recentPaceMinutes != null
                  ? `~${recentPaceMinutes} min observed average per patient visit.`
                  : 'Derived from live session consultation velocities.'}
              </p>
            </div>

            {/* Factor 3: Current OPD Flow */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
              <div className="flex items-center gap-1.5 text-slate-800 font-bold text-[11px] uppercase tracking-wider">
                <Activity className="w-3.5 h-3.5 text-emerald-600" />
                <span>Current OPD Flow</span>
              </div>
              <p className="text-slate-600 text-xs">
                {doctorName ? `Synchronized with Dr. ${doctorName}'s active room.` : 'Active clinic queue telemetry synchronized.'}
              </p>
            </div>

            {/* Factor 4: Active Disruptions */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
              <div className="flex items-center gap-1.5 text-slate-800 font-bold text-[11px] uppercase tracking-wider">
                <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                <span>Active Disruptions</span>
              </div>
              <p className="text-slate-600 text-xs">
                {explanation || 'No active clinical delays or triage emergencies recorded.'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
