import { Link } from 'react-router-dom';

interface BrandLogoProps {
  size?: 'sm' | 'md' | 'lg';
  showTagline?: boolean;
  linkTo?: string;
  className?: string;
  theme?: 'light' | 'dark';
}

export function BrandLogo({
  size = 'md',
  showTagline = false,
  linkTo = '/',
  className = '',
  theme = 'light',
}: BrandLogoProps) {
  const iconSizes = {
    sm: 'w-7 h-7',
    md: 'w-9 h-9',
    lg: 'w-11 h-11',
  };

  const textSizes = {
    sm: 'text-lg',
    md: 'text-xl',
    lg: 'text-2xl',
  };

  const content = (
    <div className={`inline-flex items-center gap-2.5 select-none ${className}`}>
      {/* Q-FLOW Forward Momentum Mark (Queue -> Flow -> Forward Movement) */}
      <div
        className={`${iconSizes[size]} rounded-xl bg-slate-900 flex items-center justify-center text-white shadow-xs shrink-0 relative overflow-hidden border border-slate-800`}
      >
        <svg
          viewBox="0 0 32 32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-5 h-5 text-blue-400"
        >
          {/* Subtle Queue Node */}
          <circle cx="9" cy="16" r="3" fill="currentColor" fillOpacity="0.4" />
          {/* Progressive Momentum Flow Line */}
          <path
            d="M13 16C15 16 16 11 19 11C22 11 23 16 25 16"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Leading Consultation Arrow */}
          <path
            d="M22 13L25 16L22 19"
            stroke="#60a5fa"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      <div className="flex flex-col">
        <span
          className={`${textSizes[size]} font-black tracking-tight leading-none ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}
        >
          Q-FLOW
        </span>
        {showTagline && (
          <span className="text-[10px] font-semibold text-slate-500 tracking-normal mt-0.5">
            Know when you'll be seen.
          </span>
        )}
      </div>
    </div>
  );

  if (linkTo) {
    return (
      <Link to={linkTo} className="hover:opacity-95 transition-opacity inline-block">
        {content}
      </Link>
    );
  }

  return content;
}
