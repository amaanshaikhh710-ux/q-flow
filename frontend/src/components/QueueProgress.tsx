import { Stethoscope, User } from 'lucide-react';
import type { QueueEntryStatus } from '../types/api';

interface QueueProgressProps {
  position: number | null;
  totalWaiting: number;
  status: QueueEntryStatus;
  className?: string;
}

export function QueueProgress({
  position,
  totalWaiting,
  status,
  className = '',
}: QueueProgressProps) {
  const isCalled = status === 'CALLED';
  const isInConsultation = status === 'IN_CONSULTATION';
  const isDone = status === 'COMPLETED';

  // Compute a clean progress percentage based strictly on actual position
  // If position is 1, they are next (75% progress). If called, 90%. If in consultation, 100%.
  let progressPercent = 10;
  if (isDone) {
    progressPercent = 100;
  } else if (isInConsultation) {
    progressPercent = 95;
  } else if (isCalled) {
    progressPercent = 80;
  } else if (position != null && position > 0) {
    const total = Math.max(totalWaiting, position);
    // Inverse ratio: position 1 of 10 is near the end of waiting
    progressPercent = Math.max(15, Math.min(75, Math.round(((total - position + 1) / total) * 75)));
  }

  return (
    <div className={`space-y-2 select-none ${className}`}>
      <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
        <span className="flex items-center gap-1.5 text-slate-700 font-semibold">
          <User className="w-3.5 h-3.5 text-blue-600" />
          <span>You {position != null ? `(#${position})` : ''}</span>
        </span>
        <span className="text-[11px] text-slate-400">
          {isInConsultation
            ? 'In Consultation Room'
            : isCalled
            ? 'Proceed to Door'
            : position === 1
            ? 'You are next in line'
            : position != null
            ? `${position - 1} ahead of you`
            : 'In line'}
        </span>
        <span className="flex items-center gap-1.5 text-slate-700 font-semibold">
          <Stethoscope className="w-3.5 h-3.5 text-emerald-600" />
          <span>Consultation</span>
        </span>
      </div>

      {/* Track rail */}
      <div className="relative h-2 w-full bg-slate-100 rounded-full overflow-hidden border border-slate-200/80">
        <div
          className="h-full bg-gradient-to-r from-blue-600 via-blue-500 to-emerald-500 rounded-full transition-all duration-700 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-[10px] text-slate-400 font-medium">
        <span>Joined Queue</span>
        <span className="text-slate-500">Your place is moving forward</span>
        <span>Doctor's Room</span>
      </div>
    </div>
  );
}
