import { useState } from 'react';
import { ArrowRight, Clock, AlertTriangle, Zap, ChevronDown, ChevronUp, X } from 'lucide-react';
import { formatTime } from '../utils/format';

export interface EtaChangeData {
  previousStart: string;
  newStart: string;
  shiftMinutes: number;
  reason: string;
  isEmergency?: boolean;
}

interface EtaChangeBannerProps {
  data: EtaChangeData;
  onDismiss?: () => void;
  className?: string;
}

export function EtaChangeBanner({
  data,
  onDismiss,
  className = '',
}: EtaChangeBannerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const isEmergency = Boolean(data.isEmergency || (data.reason && data.reason.toLowerCase().includes('emergency')));
  const isShiftPositive = data.shiftMinutes > 0;

  return (
    <div
      role="region"
      aria-label="ETA Update Announcement"
      className={`rounded-2xl p-5 sm:p-6 transition-all duration-300 ease-out animate-fade-up ${
        isEmergency
          ? 'bg-rose-950/95 text-rose-50 border border-rose-800 shadow-md'
          : 'bg-slate-900 text-slate-100 border border-slate-800 shadow-md'
      } ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span
            className={`inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-md ${
              isEmergency
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                : 'bg-amber-400/20 text-amber-300 border border-amber-400/30'
            }`}
          >
            {isEmergency ? <Zap className="w-3 h-3 text-rose-400" /> : <Clock className="w-3 h-3 text-amber-400" />}
            <span>ETA Updated</span>
          </span>
          <span className="text-[11px] text-slate-400 font-medium">Real-time queue recalculation</span>
        </div>

        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
            title="Dismiss notification"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Time comparison rail */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 py-3 px-4 rounded-xl bg-black/20 border border-white/5">
        <div className="flex items-center gap-3">
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
              Previous
            </span>
            <span className="text-sm font-semibold text-slate-400 line-through">
              {formatTime(data.previousStart)}
            </span>
          </div>

          <ArrowRight className="w-4 h-4 text-blue-400 shrink-0" />

          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-300 block">
              New Estimate
            </span>
            <span className="text-base sm:text-lg font-bold text-white tracking-tight">
              {formatTime(data.newStart)}
            </span>
          </div>
        </div>

        <div className="text-right">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
            Adjustment
          </span>
          <span
            className={`text-sm font-extrabold ${
              isEmergency
                ? 'text-rose-300'
                : isShiftPositive
                ? 'text-amber-300'
                : 'text-emerald-300'
            }`}
          >
            {isShiftPositive ? `+${data.shiftMinutes} min` : `${data.shiftMinutes} min`}
          </span>
        </div>
      </div>

      {/* Why did this happen section */}
      <div className="mt-3.5 space-y-1">
        <p className="text-xs font-semibold text-slate-200">
          Why did this happen?
        </p>
        <p className="text-xs text-slate-300 leading-relaxed">
          {data.reason || 'Clinical triage priority adjustment or clinician pacing change in OPD rounds.'}
        </p>
      </div>

      {/* Expandable See what changed */}
      <div className="mt-3 pt-3 border-t border-white/10 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors cursor-pointer"
        >
          <span>See what changed</span>
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
        <span className="text-[11px] text-slate-400">Departure recommendations updated</span>
      </div>

      {isExpanded && (
        <div className="mt-3 p-3.5 rounded-xl bg-black/30 border border-white/5 text-xs text-slate-300 space-y-2 animate-fade-up">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-white">Continuous OPD Pacing Engine</p>
              <p className="text-[11px] text-slate-300 leading-relaxed">
                Q-FLOW's engine observed a shift in active consultations. Rather than letting you wait in clinic corridors, your arrival and departure times have been recalibrated so you arrive right on time.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
