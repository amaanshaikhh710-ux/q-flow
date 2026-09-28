import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { X, AlertTriangle, Info } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  consequence?: string;
  isDestructive?: boolean;
  children: ReactNode;
  footer?: ReactNode;
}

export function Modal({
  isOpen,
  onClose,
  title,
  subtitle,
  consequence,
  isDestructive = false,
  children,
  footer,
}: ModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto bg-slate-900/60 backdrop-blur-xs animate-fade-up"
      role="dialog"
      aria-modal="true"
    >
      <div
        className="fixed inset-0"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden z-10">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-slate-100 bg-slate-50/50">
          <div>
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              {isDestructive && (
                <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
              )}
              {title}
            </h3>
            {subtitle && (
              <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors"
            aria-label="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Operational Consequence Banner if applicable */}
        {consequence && (
          <div className="mx-5 mt-4 p-3.5 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-2.5 text-xs text-amber-900">
            <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div className="leading-relaxed">
              <span className="font-semibold block mb-0.5">Queue Impact Notice:</span>
              {consequence}
            </div>
          </div>
        )}

        {/* Content Body */}
        <div className="p-5">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="p-4 border-t border-slate-100 bg-slate-50/70 flex items-center justify-end gap-2.5">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
