import { clsx } from 'clsx';

interface Props {
  count: number;
  total: number;
  alignmentContext?: string[];
  opAligned?: number;
  opTotal?: number;
  regAligned?: number;
  regTotal?: number;
  combinedAligned?: number;
  regAllUndetermined?: boolean;
}

export default function GovernedAlignmentCard({
  count, total, alignmentContext,
  opAligned, opTotal, regAligned, regTotal, combinedAligned,
  regAllUndetermined,
}: Props) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  const color = pct >= 80 ? 'emerald' : pct >= 50 ? 'amber' : 'red';

  // Two-axis split
  const hasTA = opTotal != null && opTotal > 0;
  const opPct = hasTA && opTotal! > 0 ? Math.round(((opAligned ?? 0) / opTotal!) * 100) : 0;
  const regPct = hasTA && (regTotal ?? 0) > 0 ? Math.round(((regAligned ?? 0) / (regTotal ?? 1)) * 100) : 0;
  const combPct = hasTA && opTotal! > 0 ? Math.round(((combinedAligned ?? 0) / opTotal!) * 100) : 0;

  return (
    <div className={clsx(
      'rounded-xl border bg-slate-800 p-5',
      color === 'emerald' && 'border-emerald-500/30',
      color === 'amber' && 'border-amber-500/30',
      color === 'red' && 'border-red-500/30',
    )}>
      <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white">
        Governed Disposition Alignment
      </h4>

      {/* Two-axis split when available */}
      {hasTA ? (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="text-[10px] text-white uppercase">Operational</p>
              <p className={clsx('text-xl font-bold', opPct >= 70 ? 'text-emerald-400' : opPct >= 40 ? 'text-amber-400' : 'text-red-400')}>
                {opPct}%
              </p>
              <p className="text-[10px] text-white">{opAligned}/{opTotal}</p>
            </div>
            <div>
              <p className="text-[10px] text-white uppercase">Regulatory</p>
              <p className={clsx('text-xl font-bold', regAllUndetermined ? 'text-white' : regPct >= 70 ? 'text-emerald-400' : regPct >= 40 ? 'text-amber-400' : 'text-red-400')}>
                {regPct}%
              </p>
              <p className="text-[10px] text-white">{regAligned}/{regTotal}</p>
            </div>
            <div>
              <p className="text-[10px] text-white uppercase">Combined</p>
              <p className={clsx('text-xl font-bold', combPct >= 70 ? 'text-emerald-400' : combPct >= 40 ? 'text-amber-400' : 'text-red-400')}>
                {combPct}%
              </p>
              <p className="text-[10px] text-white">{combinedAligned}/{opTotal}</p>
            </div>
          </div>

          {/* Detailed explanations for each axis */}
          <div className="grid grid-cols-3 gap-3 border-t border-slate-700 pt-3">
            <div>
              <p className="text-[11px] text-white leading-relaxed">
                Percentage of comparable historical cases where the bank reached the same
                operational decision (ALLOW, EDD, or BLOCK) as the current governed disposition.
                Measures whether the institution has historically acted the same way on similar facts.
              </p>
            </div>
            <div>
              <p className="text-[11px] text-white leading-relaxed">
                Percentage of comparable cases where the suspicion finding matched — either both
                filed an STR or both determined no STR was required. Measures whether the institution
                has historically reached the same regulatory conclusion on similar risk profiles.
              </p>
            </div>
            <div>
              <p className="text-[11px] text-white leading-relaxed">
                Percentage of comparable cases that match on both axes simultaneously — same
                operational decision AND same suspicion finding. This is the strictest measure:
                only precedents that fully align on both dimensions count toward this number.
              </p>
            </div>
          </div>

          {opPct >= 70 && regPct < 30 && (
            <p className="text-[11px] text-amber-300/80 leading-relaxed">
              High operational alignment indicates institutional consensus on adverse action.
              Low regulatory alignment reflects absence of STR precedent for this profile.
            </p>
          )}
          {regPct >= 70 && opPct < 30 && (
            <p className="text-[11px] text-amber-300/80 leading-relaxed">
              High regulatory alignment indicates consistent suspicion findings.
              Low operational alignment reflects divergence in operational response.
            </p>
          )}
          {regAllUndetermined && (
            <p className="text-[11px] text-white italic leading-relaxed">
              Regulatory alignment is 0% — all comparable cases are pending reporting
              determination. This reflects incomplete data, not regulatory divergence.
            </p>
          )}
        </div>
      ) : (
        <>
          <div className={clsx(
            'text-3xl font-bold',
            color === 'emerald' && 'text-emerald-400',
            color === 'amber' && 'text-amber-400',
            color === 'red' && 'text-red-400',
          )}>
            {count}/{total}
            <span className="ml-2 text-base font-normal text-white">({pct}%)</span>
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
          <p className="mt-2 text-xs text-white">
            {pct === 100
              ? 'All comparable precedents match the governed disposition.'
              : pct >= 80
              ? 'Strong institutional alignment with governed disposition.'
              : pct >= 50
              ? 'Mixed alignment — review divergent precedents.'
              : 'Majority of precedents diverge from governed disposition.'}
          </p>
        </>
      )}
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
