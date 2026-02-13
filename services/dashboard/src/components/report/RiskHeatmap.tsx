import { clsx } from 'clsx';
import type { ReportViewModel } from '../../types';

interface RiskHeatmapProps {
  report: ReportViewModel;
}

/**
 * Probability × Severity grid showing where this case sits.
 * Derives probability from confidence score and severity from
 * signal counts + verdict.
 */
export default function RiskHeatmap({ report }: RiskHeatmapProps) {
  // Determine probability level (from confidence / precedent alignment)
  const confScore = report.decision_confidence_score ?? 0;
  const prob: 'low' | 'medium' | 'high' =
    confScore >= 70 ? 'high' : confScore >= 40 ? 'medium' : 'low';

  // Determine severity level (from signals + verdict)
  const suspCount = report.suspicion_count ?? report.tier1_signals?.length ?? 0;
  const severity: 'low' | 'medium' | 'high' =
    report.verdict === 'HARD_STOP' || report.verdict === 'BLOCK' || suspCount >= 2
      ? 'high'
      : suspCount >= 1 || report.verdict === 'ESCALATE' || report.verdict === 'STR'
      ? 'medium'
      : 'low';

  const severityLabels = ['low', 'medium', 'high'] as const;
  const probLabels = ['low', 'medium', 'high'] as const;

  function cellColor(s: string, p: string) {
    const si = severityLabels.indexOf(s as typeof severityLabels[number]);
    const pi = probLabels.indexOf(p as typeof probLabels[number]);
    const risk = si + pi; // 0-4
    if (risk >= 3) return 'bg-red-500/30 border-red-500/30';
    if (risk >= 2) return 'bg-amber-500/25 border-amber-500/25';
    return 'bg-emerald-500/20 border-emerald-500/20';
  }

  function isActive(s: string, p: string) {
    return s === severity && p === prob;
  }

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white">
        Risk Heatmap
      </h3>
      <div className="flex gap-4">
        {/* Y axis label */}
        <div className="flex flex-col justify-between py-1 text-[10px] text-white">
          <span>High</span>
          <span>Med</span>
          <span>Low</span>
        </div>

        {/* Grid */}
        <div className="flex-1">
          <div className="grid grid-cols-3 gap-1">
            {/* Row: severity high → low, cols: prob low → high */}
            {[...severityLabels].reverse().map((s) =>
              probLabels.map((p) => (
                <div
                  key={`${s}-${p}`}
                  className={clsx(
                    'flex h-10 items-center justify-center rounded border text-[10px] font-medium transition-all',
                    cellColor(s, p),
                    isActive(s, p)
                      ? 'ring-2 ring-white/40 text-white scale-105'
                      : 'text-white',
                  )}
                >
                  {isActive(s, p) && '●'}
                </div>
              )),
            )}
          </div>
          {/* X axis labels */}
          <div className="mt-1 flex justify-between text-[10px] text-white px-1">
            <span>Low</span>
            <span>Med</span>
            <span>High</span>
          </div>
          <p className="mt-0.5 text-center text-[10px] text-white">Probability</p>
        </div>
      </div>
      <p className="mt-1 text-[10px] text-white text-right">
        Severity: <span className="text-white capitalize">{severity}</span> | Probability:{' '}
        <span className="text-white capitalize">{prob}</span>
      </p>
    </div>
  );
}
