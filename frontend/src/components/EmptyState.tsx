import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = '',
}: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center py-12 px-4 text-center rounded-2xl border border-dashed border-slate-200 bg-white/60 my-4 ${className}`}>
      <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mb-3.5 text-slate-400">
        {icon || <Inbox className="w-7 h-7" />}
      </div>
      <h3 className="text-base font-bold text-slate-800">{title}</h3>
      {description && (
        <p className="mt-1.5 text-sm text-slate-500 max-w-sm leading-relaxed">
          {description}
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
