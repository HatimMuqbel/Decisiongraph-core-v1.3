import type { ReportViewModel } from '../../types';
import Badge from '../Badge';

interface NegativePathSearchProps {
  report: ReportViewModel;
}

/**
 * Shows policies that were checked but NOT triggered.
 * Critical for compliance — proves the system verified what doesn't apply.
 */
export default function NegativePathSearch({ report }: NegativePathSearchProps) {
  const allSections = [
    ...(report.gate1_sections ?? []).map((s) => ({ ...s, gate: 'Gate 1' })),
    ...(report.gate2_sections ?? []).map((s) => ({ ...s, gate: 'Gate 2' })),
  ];

  const cleared = allSections.filter((s) => s.passed);
  const triggered = allSections.filter((s) => !s.passed);

  // Also check rules that were evaluated but NOT triggered
  const clearedRules = report.rules_fired?.filter((r) => r.result !== 'TRIGGERED') ?? [];

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-white">
        Negative Path Search
      </h3>
      <p className="mb-4 text-[10px] text-white">
        Policies verified as NOT applicable — audit evidence of comprehensive review
      </p>

      {/* Cleared checks */}
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-emerald-400">
          ✓ Checked &amp; CLEAR ({cleared.length + clearedRules.length})
        </h4>
        <div className="space-y-1">
          {cleared.map((s, i) => (
            <div
              key={i}
              className="flex items-start gap-2 rounded-lg bg-emerald-500/5 px-3 py-2 text-xs"
            >
              <Badge variant="success">CLEAR</Badge>
              <div>
                <span className="font-medium text-slate-300">{s.name}</span>
                <span className="ml-2 text-white">({s.gate})</span>
                <p className="mt-0.5 text-white">{s.reason}</p>
              </div>
            </div>
          ))}
          {clearedRules.slice(0, 10).map((r, i) => (
            <div
              key={`rule-${i}`}
              className="flex items-start gap-2 rounded-lg bg-emerald-500/5 px-3 py-2 text-xs"
            >
              <Badge variant="success">CLEAR</Badge>
              <div>
                <span className="font-mono font-medium text-slate-300">{r.code}</span>
                <p className="mt-0.5 text-white">{r.reason}</p>
              </div>
            </div>
          ))}
          {clearedRules.length > 10 && (
            <p className="pl-3 text-[10px] text-white">
              +{clearedRules.length - 10} more cleared rules
            </p>
          )}
        </div>
      </div>

      {/* Triggered checks */}
      {triggered.length > 0 && (
        <div className="mt-4 space-y-2">
          <h4 className="text-xs font-medium text-red-400">
            ✗ TRIGGERED ({triggered.length})
          </h4>
          <div className="space-y-1">
            {triggered.map((s, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-lg bg-red-500/5 px-3 py-2 text-xs"
              >
                <Badge variant="danger">TRIGGERED</Badge>
                <div>
                  <span className="font-medium text-slate-300">{s.name}</span>
                  <span className="ml-2 text-white">({s.gate})</span>
                  <p className="mt-0.5 text-white">{s.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
