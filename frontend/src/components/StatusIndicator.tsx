import { WifiOff, RefreshCw } from 'lucide-react';

interface LiveIndicatorProps {
  connected: boolean;
  isConnecting?: boolean;
  className?: string;
}

export function LiveIndicator({
  connected,
  isConnecting = false,
  className = '',
}: LiveIndicatorProps) {
  if (connected) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-2xs ${className}`}
      >
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
        <span className="font-bold tracking-wider uppercase text-[11px]">LIVE</span>
      </span>
    );
  }

  if (isConnecting) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200/80 ${className}`}
      >
        <RefreshCw className="w-3 h-3 animate-spin" />
        <span>Reconnecting...</span>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200 ${className}`}
    >
      <WifiOff className="w-3 h-3 text-slate-400" />
      <span>Offline — showing latest estimate</span>
    </span>
  );
}

interface TravelStatusBadgeProps {
  status: string;
}

export function TravelStatusBadge({ status }: TravelStatusBadgeProps) {
  switch (status.toUpperCase()) {
    case 'OPTIMIZED':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
          ● Google Routes Optimized
        </span>
      );
    case 'DEGRADED':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          ▲ Degraded Estimate
        </span>
      );
    case 'UNAVAILABLE':
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
          ○ Route Unavailable
        </span>
      );
  }
}
