import React from 'react';
import { clsx } from 'clsx';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  padded?: boolean;
  interactive?: boolean;
}

export function Card({
  children,
  className,
  padded = true,
  interactive = false,
  ...rest
}: CardProps) {
  return (
    <div
      className={clsx(
        'bg-white rounded-3xl border border-slate-200/90 shadow-xs transition-all',
        padded && 'p-6 sm:p-8',
        interactive &&
          'hover:border-blue-300 hover:shadow-md active:scale-[0.995] cursor-pointer',
        className
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
