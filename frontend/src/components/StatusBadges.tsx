import type { QueueEntryStatus, PriorityClass, QueueStatus, DoctorStatus } from '../types/api';
import {
  Clock,
  Bell,
  Stethoscope,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  PauseCircle,
  AlertOctagon,
  ArrowLeftCircle,
  ArrowRightCircle,
  Slash,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Queue Entry Status Badge
// ---------------------------------------------------------------------------

const entryStatusConfig: Record<
  QueueEntryStatus,
  { label: string; bg: string; text: string; border: string; icon: React.ComponentType<{ className?: string }> }
> = {
  BOOKED: {
    label: 'Booked',
    bg: 'bg-purple-50',
    text: 'text-purple-700',
    border: 'border-purple-200',
    icon: Clock,
  },
  ARRIVED: {
    label: 'Arrived',
    bg: 'bg-teal-50',
    text: 'text-teal-700',
    border: 'border-teal-200',
    icon: CheckCircle2,
  },
  WAITING: {
    label: 'Waiting',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    border: 'border-blue-200',
    icon: Clock,
  },
  CALLED: {
    label: 'Called',
    bg: 'bg-amber-50',
    text: 'text-amber-800',
    border: 'border-amber-200',
    icon: Bell,
  },
  IN_CONSULTATION: {
    label: 'In Consultation',
    bg: 'bg-indigo-50',
    text: 'text-indigo-700',
    border: 'border-indigo-200',
    icon: Stethoscope,
  },
  COMPLETED: {
    label: 'Completed',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
    icon: CheckCircle2,
  },
  TEMPORARILY_LEFT: {
    label: 'Temporarily Left',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
    icon: ArrowLeftCircle,
  },
  RETURNED: {
    label: 'Returned',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    border: 'border-blue-200',
    icon: ArrowRightCircle,
  },
  NO_SHOW: {
    label: 'No Show',
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
    icon: XCircle,
  },
};

export function EntryStatusBadge({ status }: { status: QueueEntryStatus | string }) {
  const upper = (status ?? '').toUpperCase() as QueueEntryStatus;
  const cfg = entryStatusConfig[upper] ?? {
    label: status,
    bg: 'bg-slate-50',
    text: 'text-slate-700',
    border: 'border-slate-200',
    icon: Clock,
  };
  const Icon = cfg.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cfg.bg} ${cfg.text} ${cfg.border} shadow-2xs`}
    >
      <Icon className="w-3 h-3 shrink-0" />
      <span>{cfg.label}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Priority Class Badge
// ---------------------------------------------------------------------------

const priorityConfig: Record<
  PriorityClass,
  { label: string; bg: string; text: string; border: string; icon: React.ComponentType<{ className?: string }> }
> = {
  NORMAL: {
    label: 'Normal',
    bg: 'bg-slate-50',
    text: 'text-slate-700',
    border: 'border-slate-200',
    icon: Clock,
  },
  PRIORITY: {
    label: 'Priority',
    bg: 'bg-amber-50',
    text: 'text-amber-800',
    border: 'border-amber-200',
    icon: AlertTriangle,
  },
  EMERGENCY: {
    label: 'Emergency',
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
    icon: AlertOctagon,
  },
};

export function PriorityBadge({ priority }: { priority: PriorityClass | string }) {
  const upper = (priority ?? '').toUpperCase() as PriorityClass;
  const cfg = priorityConfig[upper] ?? {
    label: priority,
    bg: 'bg-slate-50',
    text: 'text-slate-700',
    border: 'border-slate-200',
    icon: Clock,
  };
  const Icon = cfg.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cfg.bg} ${cfg.text} ${cfg.border} shadow-2xs`}
    >
      <Icon className="w-3 h-3 shrink-0" />
      <span>{cfg.label}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Queue Status Badge
// ---------------------------------------------------------------------------

export function QueueStatusBadge({ status }: { status: QueueStatus | string }) {
  const upper = (status ?? '').toUpperCase();
  if (upper === 'ACTIVE') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-2xs">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        <span>Active</span>
      </span>
    );
  }
  if (upper === 'PAUSED') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 shadow-2xs">
        <PauseCircle className="w-3 h-3" />
        <span>Paused</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200 shadow-2xs">
      <Slash className="w-3 h-3" />
      <span>Closed</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Doctor Status Badge
// ---------------------------------------------------------------------------

export function DoctorStatusBadge({ status }: { status: DoctorStatus | string }) {
  const lower = (status ?? '').toLowerCase();
  if (lower === 'available') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-2xs">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        <span>OPD Live</span>
      </span>
    );
  }
  if (lower === 'break') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 shadow-2xs">
        <PauseCircle className="w-3 h-3" />
        <span>On Short Break</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200 shadow-2xs">
      <Clock className="w-3 h-3" />
      <span>Unavailable</span>
    </span>
  );
}
