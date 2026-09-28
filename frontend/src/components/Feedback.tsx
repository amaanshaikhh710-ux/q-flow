interface ErrorBannerProps {
  message: string | null | undefined;
}

export function ErrorBanner({ message }: ErrorBannerProps) {
  if (!message) return null;
  return (
    <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
      {message}
    </div>
  );
}

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && <div className="mb-3 text-slate-400">{icon}</div>}
      <p className="text-base font-medium text-slate-700">{title}</p>
      {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
