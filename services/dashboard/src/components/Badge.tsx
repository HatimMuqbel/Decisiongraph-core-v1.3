import type { ReactNode } from 'react';
import { clsx } from 'clsx';

type Variant = 'success' | 'danger' | 'warning' | 'info' | 'neutral';

const variantClasses: Record<Variant, string> = {
  success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  danger: 'bg-red-500/20 text-red-400 border-red-500/30',
  warning: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  info: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  neutral: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

interface BadgeProps {
  variant?: Variant;
  children: ReactNode;
  className?: string;
  size?: 'sm' | 'md';
}

export default function Badge({ variant = 'neutral', children, className, size = 'sm' }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center font-medium border rounded-full',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
        variantClasses[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

// Convenience mappers
export function dispositionVariant(d: string): Variant {
  switch (d) {
    case 'ALLOW':
    case 'PASS':
    case 'pay':
    case 'approve':
      return 'success';
    case 'EDD':
    case 'ESCALATE':
    case 'escalate':
    case 'PASS_WITH_EDD':
      return 'warning';
    case 'BLOCK':
    case 'HARD_STOP':
    case 'deny':
    case 'STR':
      return 'danger';
    default:
      return 'neutral';
  }
}

export function confidenceVariant(score: number): Variant {
  if (score >= 0.8) return 'success';
  if (score >= 0.5) return 'warning';
  return 'danger';
}

export function changeTypeVariant(ct: string): Variant {
  switch (ct) {
    case 'escalation':
      return 'danger';
    case 'de_escalation':
      return 'success';
    case 'reporting_change':
      return 'warning';
    default:
      return 'info';
  }
}
