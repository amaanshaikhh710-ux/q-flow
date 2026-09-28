export function SkeletonLine({ className = 'h-4 w-full' }: { className?: string }) {
  return <div className={`animate-pulse bg-slate-200 rounded-lg ${className}`} />;
}

export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-white rounded-2xl p-5 border border-slate-200/80 shadow-xs space-y-4 ${className}`}>
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-slate-200 animate-pulse shrink-0" />
        <div className="space-y-2 flex-1">
          <SkeletonLine className="h-5 w-3/4" />
          <SkeletonLine className="h-3 w-1/2" />
        </div>
      </div>
      <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
        <SkeletonLine className="h-4 w-28" />
        <SkeletonLine className="h-4 w-16" />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 3, className = '' }: { count?: number; className?: string }) {
  return (
    <div className={`space-y-3.5 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export function LoadingScreen({ message = 'Loading queue details...' }: { message?: string }) {
  return (
    <div className="min-h-[50vh] flex flex-col items-center justify-center p-6 text-center animate-fade-up">
      <div className="relative mb-5">
        <div className="w-14 h-14 rounded-2xl border-3 border-blue-100 border-t-blue-600 animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center font-bold text-blue-600 text-xs tracking-wider">
          Q
        </div>
      </div>
      <p className="text-sm font-semibold text-slate-800">{message}</p>
      <p className="text-xs text-slate-400 mt-1 max-w-xs">
        Syncing with real-time OPD forecasting engine...
      </p>
    </div>
  );
}
