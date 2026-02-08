import { clsx } from 'clsx';

interface StatsCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'flat';
  className?: string;
}

export default function StatsCard({ label, value, sub, icon, trend, className }: StatsCardProps) {
  return (
    <div
      className={clsx(
        'rounded-xl border border-slate-700/60 bg-slate-800 p-5 transition-shadow hover:shadow-lg',
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">{label}</p>
          <p className="mt-1 text-2xl font-bold text-slate-100">{value}</p>
          {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
        </div>
        {icon && <div className="text-slate-500">{icon}</div>}
      </div>
      {trend && (
        <div className="mt-2">
          <span
            className={clsx(
              'text-xs font-medium',
              trend === 'up' && 'text-emerald-400',
              trend === 'down' && 'text-red-400',
              trend === 'flat' && 'text-slate-400'
            )}
          >
            {trend === 'up' ? '▲' : trend === 'down' ? '▼' : '—'}
          </span>
        </div>
      )}
    </div>
  );
}
