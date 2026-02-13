import { clsx } from 'clsx';
import type { CascadeImpact } from '../../types';

function PoolBar({ counts, label }: { counts: Record<string, number>; label: string }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) return <div className="text-xs text-white">{label}: empty</div>;

  const segments = [
    { key: 'ALLOW', color: 'bg-emerald-500', text: 'text-emerald-100' },
    { key: 'EDD', color: 'bg-amber-500', text: 'text-amber-100' },
    { key: 'BLOCK', color: 'bg-red-500', text: 'text-red-100' },
  ];

  return (
    <div className="space-y-1">
      <p className="text-[10px] font-medium uppercase tracking-wider text-white">{label}</p>
      <div className="flex h-7 overflow-hidden rounded-md">
        {segments.map(({ key, color, text }) => {
          const n = counts[key] ?? 0;
          if (n === 0) return null;
          const pct = (n / total) * 100;
          return (
            <div
              key={key}
              className={clsx(color, text, 'flex items-center justify-center text-[10px] font-bold')}
              style={{ width: `${pct}%`, minWidth: pct > 0 ? '24px' : 0 }}
              title={`${key}: ${n}`}
            >
              {pct >= 15 ? `${key}(${n})` : n}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const adequacyColor: Record<string, string> = {
  LOW: 'text-red-400',
  MODERATE: 'text-amber-400',
  HIGH: 'text-emerald-400',
  VERY_HIGH: 'text-emerald-300',
};

interface Props {
  cascade: CascadeImpact;
}

export default function CascadeImpactPanel({ cascade }: Props) {
  const ci = cascade;

  const confIcon =
    ci.confidence_direction === 'IMPROVED'
      ? { sym: '\u25B2', cls: 'text-emerald-400' }
      : ci.confidence_direction === 'DEGRADED'
        ? { sym: '\u25BC', cls: 'text-red-400' }
        : { sym: '\u2014', cls: 'text-white' };

  return (
    <div
      className={clsx(
        'rounded-xl border p-4 space-y-3',
        ci.posture_reversal
          ? 'border-red-500/40 bg-red-500/5'
          : 'border-slate-700/60 bg-slate-800/60',
      )}
    >
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-slate-200">
          {ci.typology.replace(/_/g, ' ')}
        </h4>
        {ci.posture_reversal && (
          <span className="inline-flex items-center gap-1 rounded-full bg-red-500/20 px-2 py-0.5 text-[10px] font-bold text-red-400 border border-red-500/30">
            REVERSAL
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <PoolBar counts={ci.pool_before} label="Before" />
        <PoolBar counts={ci.pool_after} label="After" />
      </div>

      <div className="grid grid-cols-3 gap-4 text-xs">
        <div>
          <p className="text-white">Confidence</p>
          <p className="text-slate-200">
            {ci.confidence_before} <span className="text-white">{'\u2192'}</span> {ci.confidence_after}{' '}
            <span className={confIcon.cls}>{confIcon.sym} {ci.confidence_direction}</span>
          </p>
        </div>
        <div>
          <p className="text-white">Posture</p>
          <p className="text-slate-200 leading-tight">{ci.posture_before}</p>
          <p className="text-white leading-tight">{'\u2192'} {ci.posture_after}</p>
        </div>
        <div>
          <p className="text-white">Pool Size</p>
          <p className={clsx('font-medium', adequacyColor[ci.pool_adequacy] ?? 'text-slate-300')}>
            {ci.post_shift_pool_size} cases ({ci.pool_adequacy})
          </p>
        </div>
      </div>

      {ci.posture_reversal && (
        <p className="text-xs text-red-400/80 italic">
          A future {ci.typology.replace(/_/g, ' ')} case would see a fundamentally different
          institutional posture under this policy.
        </p>
      )}
    </div>
  );
}
