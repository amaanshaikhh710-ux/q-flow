import { AlertCircle, RotateCcw, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface RetryButtonProps {
  onClick: () => void;
  isLoading?: boolean;
  className?: string;
  label?: string;
}

export function RetryButton({
  onClick,
  isLoading = false,
  className = '',
  label = 'Try Again',
}: RetryButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isLoading}
      className={`inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-medium text-sm transition-all shadow-xs disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
      <RotateCcw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
      <span>{label}</span>
    </button>
  );
}

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  backTo?: string;
  backLabel?: string;
  className?: string;
}

export function ErrorState({
  title = 'Unable to Load Data',
  message,
  onRetry,
  backTo,
  backLabel = 'Go Back',
  className = '',
}: ErrorStateProps) {
  const navigate = useNavigate();

  return (
    <div className={`rounded-2xl border border-red-200/90 bg-red-50/50 p-6 md:p-8 text-center max-w-lg mx-auto my-6 shadow-xs ${className}`}>
      <div className="w-12 h-12 rounded-2xl bg-red-100 flex items-center justify-center mx-auto mb-3 text-red-600 shadow-inner">
        <AlertCircle className="w-6 h-6" />
      </div>
      <h3 className="text-base font-bold text-slate-900 mb-1">{title}</h3>
      <p className="text-sm text-slate-600 mb-6 leading-relaxed max-w-sm mx-auto">
        {message}
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        {onRetry && (
          <RetryButton onClick={onRetry} label="Retry Request" />
        )}
        {backTo ? (
          <button
            type="button"
            onClick={() => navigate(backTo)}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl bg-white hover:bg-slate-100 text-slate-700 font-medium text-sm border border-slate-200 shadow-xs transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>{backLabel}</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl bg-white hover:bg-slate-100 text-slate-700 font-medium text-sm border border-slate-200 shadow-xs transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>{backLabel}</span>
          </button>
        )}
      </div>
    </div>
  );
}
