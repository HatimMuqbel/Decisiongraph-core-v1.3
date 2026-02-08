import { clsx } from 'clsx';

interface LoadingProps {
  className?: string;
  text?: string;
}

export default function Loading({ className, text = 'Loading…' }: LoadingProps) {
  return (
    <div className={clsx('flex items-center justify-center gap-3 py-12', className)}>
      <svg
        className="h-5 w-5 animate-spin text-emerald-400"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      <span className="text-sm text-slate-400">{text}</span>
    </div>
  );
}
