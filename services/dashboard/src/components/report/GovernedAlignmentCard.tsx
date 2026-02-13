import { clsx } from 'clsx';

interface Props {
  count: number;
  total: number;
  alignmentContext?: string[];
}

export default function GovernedAlignmentCard({ count, total, alignmentContext }: Props) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  const color = pct >= 80 ? 'emerald' : pct >= 50 ? 'amber' : 'red';

  return (
    <div className={clsx(
      'rounded-xl border bg-slate-800 p-5',
      color === 'emerald' && 'border-emerald-500/30',
      color === 'amber' && 'border-amber-500/30',
      color === 'red' && 'border-red-500/30',
    )}>
      <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Governed Disposition Alignment
      </h4>
      <div className={clsx(
        'text-3xl font-bold',
        color === 'emerald' && 'text-emerald-400',
        color === 'amber' && 'text-amber-400',
        color === 'red' && 'text-red-400',
      )}>
        {count}/{total}
        <span className="ml-2 text-base font-normal text-slate-400">({pct}%)</span>
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-700">
        <div
          className={clsx(
            'h-full rounded-full transition-all',
            color === 'emerald' && 'bg-emerald-500',
            color === 'amber' && 'bg-amber-500',
            color === 'red' && 'bg-red-500',
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-slate-400">
        {pct === 100
          ? 'All comparable precedents match the governed disposition.'
          : pct >= 80
          ? 'Strong institutional alignment with governed disposition.'
          : pct >= 50
          ? 'Mixed alignment — review divergent precedents.'
          : 'Majority of precedents diverge from governed disposition.'}
      </p>
      {alignmentContext && alignmentContext.length > 0 && pct < 60 && (
        <div className="mt-2 space-y-1">
          {alignmentContext.map((ctx, i) => (
            <p key={i} className="text-[11px] text-amber-300/80 leading-relaxed">{ctx}</p>
          ))}
        </div>
      )}
    </div>
  );
}
