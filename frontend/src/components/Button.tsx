import React from 'react';
import { clsx } from 'clsx';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-slate-900 hover:bg-slate-800 active:bg-slate-950 text-white border border-slate-900 shadow-xs focus:ring-slate-400 disabled:bg-slate-300 disabled:border-slate-300',
  secondary:
    'bg-white hover:bg-slate-50 active:bg-slate-100 text-slate-700 border border-slate-200/90 shadow-2xs focus:ring-blue-200 disabled:opacity-50 disabled:border-slate-200',
  danger:
    'bg-red-600 hover:bg-red-700 active:bg-red-800 text-white border border-red-600 shadow-xs focus:ring-red-200 disabled:opacity-50',
  ghost:
    'bg-transparent hover:bg-slate-100 active:bg-slate-200 text-slate-700 focus:ring-slate-200 disabled:opacity-40',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'min-h-[36px] px-3.5 py-1.5 text-xs font-semibold rounded-xl',
  md: 'min-h-[44px] px-4 py-2.5 text-sm font-semibold rounded-xl',
  lg: 'min-h-[50px] px-6 py-3 text-base font-semibold rounded-2xl',
};

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  fullWidth = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center gap-2 font-medium transition-all select-none',
        'focus:outline-hidden focus:ring-2 focus:ring-offset-1',
        'active:scale-[0.99]',
        variantClasses[variant],
        sizeClasses[size],
        fullWidth && 'w-full',
        (disabled || loading) && 'cursor-not-allowed opacity-60 active:scale-100',
        className
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && (
        <svg
          className="h-4 w-4 animate-spin text-current shrink-0"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )}
      {children}
    </button>
  );
}
