import type { RegimeAnalysis } from '../../types';

interface Props {
  regimeAnalysis: RegimeAnalysis;
}

const MAGNITUDE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  high: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'HIGH' },
  moderate: { bg: 'bg-amber-500/20', text: 'text-amber-400', label: 'MODERATE' },
  low: { bg: 'bg-slate-500/20', text: 'text-slate-400', label: 'LOW' },
};

const DISPOSITION_COLORS: Record<string, string> = {
  ALLOW: 'bg-emerald-500',
  EDD: 'bg-amber-500',
  BLOCK: 'bg-red-500',
};

function DistributionBars({ distribution, total }: { distribution: Record<string, number>; total: number }) {
  if (!total || Object.keys(distribution).length === 0) {
    return <p className="text-[11px] text-slate-500 italic">No cases</p>;
  }
  return (
    <div className="space-y-1">
      {Object.entries(distribution)
        .sort(([, a], [, b]) => b - a)
        .map(([disp, count]) => {
          const pct = Math.round((count / total) * 100);
          const color = DISPOSITION_COLORS[disp] ?? 'bg-slate-500';
          return (
            <div key={disp}>
              <div className="flex justify-between text-[11px]">
                <span className="text-slate-400">{disp}</span>
                <span className="text-slate-400">{count} ({pct}%)</span>
              </div>
              <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-700">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.max(pct, 3)}%` }} />
              </div>
            </div>
          );
        })}
    </div>
  );
}

export default function PolicyRegimeContext({ regimeAnalysis }: Props) {
  const ra = regimeAnalysis;
  if (!ra.shifts_detected || ra.shifts_detected.length === 0) return null;

  const magStyle = MAGNITUDE_STYLES[ra.magnitude] ?? MAGNITUDE_STYLES.low;

  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-900/10 p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-amber-400">&#9888;</span>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-400">
          Policy Regime Context
        </h4>
        <span className={`ml-auto inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${magStyle.bg} ${magStyle.text} border-current/30`}>
          {magStyle.label} IMPACT
        </span>
      </div>

      {ra.shifts_detected.map((shift) => (
        <div key={shift.id} className="mb-4">
          <p className="text-sm font-medium text-slate-200">
            Active shift: {shift.name}
          </p>
          <p className="text-[11px] text-slate-400">
            Effective: {shift.effective_date} &middot; {shift.description}
          </p>

          <div className="mt-3 grid grid-cols-2 gap-3">
            {/* Pre-shift card */}
            <div className="rounded-lg bg-slate-700/50 p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Pre-Shift
                </span>
                <span className="text-[10px] text-slate-500">Superseded policy</span>
              </div>
              <p className="mb-2 text-lg font-bold text-slate-300">{ra.pre_shift_count} <span className="text-xs font-normal text-slate-500">cases</span></p>
              <DistributionBars distribution={ra.pre_shift_distribution} total={ra.pre_shift_count} />
            </div>

            {/* Post-shift card */}
            <div className="rounded-lg bg-emerald-900/20 border border-emerald-500/10 p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
                  Post-Shift
                </span>
                <span className="text-[10px] text-emerald-500">Current policy &#10003;</span>
              </div>
              <p className="mb-2 text-lg font-bold text-slate-200">{ra.post_shift_count} <span className="text-xs font-normal text-slate-500">cases</span></p>
              <DistributionBars distribution={ra.post_shift_distribution} total={ra.post_shift_count} />
            </div>
          </div>
        </div>
      ))}

      <div className="mt-3 space-y-1 border-t border-amber-500/20 pt-3">
        <p className="text-xs text-slate-300">
          <span className="font-medium text-amber-400">{ra.pct_regime_limited}%</span> of comparable pool decided under superseded policy.
          Post-shift pool: <span className="font-medium">{ra.post_shift_count}</span> cases (effective pool for confidence).
        </p>
        {ra.guidance && (
          <p className="text-[11px] text-slate-400 italic">{ra.guidance}</p>
        )}
      </div>
    </div>
  );
}
