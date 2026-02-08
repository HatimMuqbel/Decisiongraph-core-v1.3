import type { ReportViewModel } from '../../types';

interface VerbatimCitationsProps {
  report: ReportViewModel;
}

/**
 * Side-by-side: exact policy text | case data that triggered it.
 * Maps rules_fired to evidence_used for full provenance.
 */
export default function VerbatimCitations({ report }: VerbatimCitationsProps) {
  const triggeredRules = report.rules_fired?.filter((r) => r.result === 'TRIGGERED') ?? [];

  if (triggeredRules.length === 0) {
    return (
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Verbatim Citations
        </h3>
        <p className="text-sm text-slate-500">No triggered policy citations to display.</p>
      </div>
    );
  }

  // Build evidence lookup
  const evidenceMap = new Map<string, string>();
  report.evidence_used?.forEach((e) => {
    evidenceMap.set(e.field, String(e.value));
  });

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Verbatim Citations
      </h3>
      <p className="mb-4 text-[10px] text-slate-600">
        Policy provisions mapped to triggering case data — regulatory evidence chain
      </p>

      <div className="space-y-3">
        {triggeredRules.map((rule, i) => (
          <div
            key={i}
            className="grid grid-cols-1 gap-0.5 rounded-lg border border-slate-700/40 overflow-hidden md:grid-cols-2"
          >
            {/* Left: Policy citation */}
            <div className="bg-slate-900 p-4">
              <div className="mb-2 flex items-center gap-2">
                <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] font-medium text-red-400 border border-red-500/20">
                  POLICY
                </span>
                <span className="font-mono text-xs text-slate-300">{rule.code}</span>
              </div>
              <p className="text-xs leading-relaxed text-slate-400">{rule.reason}</p>
            </div>

            {/* Right: Case data */}
            <div className="bg-slate-900/50 p-4">
              <div className="mb-2">
                <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-medium text-blue-400 border border-blue-500/20">
                  CASE DATA
                </span>
              </div>
              <div className="space-y-1">
                {/* Match rule code to likely evidence fields */}
                {report.evidence_used
                  ?.filter((e) => {
                    const code = rule.code.toLowerCase();
                    const field = e.field.toLowerCase();
                    // Heuristic: match field to rule code
                    return (
                      code.includes(field.split('.').pop() ?? '') ||
                      field.includes(code.split('_').slice(-1)[0] ?? '') ||
                      (e.value === true && code.includes('esc'))
                    );
                  })
                  .slice(0, 5)
                  .map((e, j) => (
                    <div key={j} className="flex items-center gap-2 text-xs">
                      <span className="font-mono text-slate-500">{e.field}</span>
                      <span className="text-slate-600">=</span>
                      <span className="text-slate-300">{String(e.value)}</span>
                    </div>
                  ))}
                {/* Fallback: show rule result */}
                <div className="mt-1 border-t border-slate-700/30 pt-1">
                  <span className="text-[10px] text-slate-500">
                    Result: <span className="text-red-400">{rule.result}</span>
                  </span>
                </div>
              </div>
            </div>

            {/* Connector line (visual) */}
            <div className="col-span-full flex items-center justify-center md:hidden">
              <div className="h-px w-full bg-gradient-to-r from-red-500/20 via-slate-600 to-blue-500/20" />
            </div>
          </div>
        ))}
      </div>

      {/* Hash provenance */}
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-600">
        <span>Policy Hash: <span className="font-mono">{report.policy_hash?.slice(0, 16) ?? 'N/A'}</span></span>
        <span>Input Hash: <span className="font-mono">{report.input_hash?.slice(0, 16) ?? 'N/A'}</span></span>
        <span>Engine: v{report.engine_version}</span>
      </div>
    </div>
  );
}
