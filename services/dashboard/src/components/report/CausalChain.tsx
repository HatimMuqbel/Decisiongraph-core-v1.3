import type { ReportViewModel } from '../../types';
import Badge from '../Badge';
import { clsx } from 'clsx';

interface CausalChainProps {
  report: ReportViewModel;
}

/**
 * Signal → node → decision chain visualization.
 * Shows how input signals activated policy nodes and led to the final decision.
 */
export default function CausalChain({ report }: CausalChainProps) {
  const tier1 = report.tier1_signals ?? [];
  const tier2 = report.tier2_signals ?? [];
  const triggered = report.rules_fired?.filter((r) => r.result === 'TRIGGERED') ?? [];

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-white">
        Causal Chain
      </h3>
      <p className="mb-4 text-[10px] text-white">
        Signal → Rule → Decision chain — full inference provenance
      </p>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        {/* Stage 1: Input Signals */}
        <div>
          <h4 className="mb-2 text-xs font-medium text-blue-400">① Input Signals</h4>
          <div className="space-y-1">
            {tier1.map((s, i) => (
              <div key={i} className="rounded-lg bg-red-500/5 border border-red-500/10 px-2 py-1.5 text-[11px]">
                <span className="font-mono font-medium text-red-400">{s.code}</span>
                {s.field && <span className="ml-1 text-white">({s.field})</span>}
                <p className="mt-0.5 text-white line-clamp-2">{s.detail}</p>
              </div>
            ))}
            {tier2.map((s, i) => (
              <div key={`t2-${i}`} className="rounded-lg bg-amber-500/5 border border-amber-500/10 px-2 py-1.5 text-[11px]">
                <span className="font-mono font-medium text-amber-400">{s.code}</span>
                {s.field && <span className="ml-1 text-white">({s.field})</span>}
                <p className="mt-0.5 text-white line-clamp-2">{s.detail}</p>
              </div>
            ))}
            {tier1.length === 0 && tier2.length === 0 && (
              <p className="text-[11px] text-white">No signals detected</p>
            )}
          </div>
        </div>

        {/* Stage 2: Rules Activated */}
        <div>
          <h4 className="mb-2 text-xs font-medium text-amber-400">② Rules Activated</h4>
          <div className="space-y-1">
            {triggered.map((r, i) => (
              <div key={i} className="rounded-lg bg-amber-500/5 border border-amber-500/10 px-2 py-1.5 text-[11px]">
                <span className="font-mono font-medium text-amber-300">{r.code}</span>
                <p className="mt-0.5 text-white line-clamp-2">{r.reason}</p>
              </div>
            ))}
            {triggered.length === 0 && (
              <p className="text-[11px] text-white">No rules triggered</p>
            )}
          </div>
        </div>

        {/* Stage 3: Gate Decisions */}
        <div>
          <h4 className="mb-2 text-xs font-medium text-purple-400">③ Gate Decisions</h4>
          <div className="space-y-2">
            <div className="rounded-lg bg-slate-900 px-2 py-2 text-[11px]">
              <p className="text-white">Gate 1 (Escalation)</p>
              <p className={clsx(
                'mt-0.5 font-semibold',
                report.gate1_passed ? 'text-emerald-400' : 'text-red-400',
              )}>
                {report.gate1_decision || 'N/A'}
              </p>
            </div>
            <div className="rounded-lg bg-slate-900 px-2 py-2 text-[11px]">
              <p className="text-white">Gate 2 (STR)</p>
              <p className={clsx(
                'mt-0.5 font-semibold',
                report.gate2_status === 'CLEAR' ? 'text-emerald-400' : 'text-amber-400',
              )}>
                {report.gate2_decision || 'N/A'}
              </p>
            </div>
            {report.classifier_is_sovereign && !report.is_pep_edd_no_suspicion && (
              <div className={clsx(
                'rounded-lg px-2 py-1.5 text-[10px]',
                report.classification_outcome !== report.governed_disposition
                  ? 'bg-amber-500/5 border border-amber-500/10 text-amber-400'
                  : 'bg-purple-500/5 border border-purple-500/10 text-purple-400',
              )}>
                {report.classification_outcome !== report.governed_disposition
                  ? `OVERRIDDEN — Classifier recommends ${report.classification_outcome?.replace(/_/g, ' ')}, governed disposition is ${report.governed_disposition?.replace(/_/g, ' ')}`
                  : 'Classifier is sovereign — final authority'}
              </div>
            )}
            {report.is_pep_edd_no_suspicion && (
              <div className="rounded-lg px-2 py-1.5 text-[10px] bg-blue-500/5 border border-blue-500/10 text-blue-400">
                NO SUSPICION DETECTED — EDD required by PEP regulatory obligation, not suspicion indicators
              </div>
            )}
          </div>
        </div>

        {/* Stage 4: Final Decision */}
        <div>
          <h4 className="mb-2 text-xs font-medium text-emerald-400">④ Final Decision</h4>
          <div className="space-y-2">
            <div className="rounded-lg bg-slate-900 p-3 text-center">
              <Badge
                variant={
                  report.verdict === 'PASS' || report.verdict === 'ALLOW'
                    ? 'success'
                    : report.verdict === 'HARD_STOP' || report.verdict === 'BLOCK'
                    ? 'danger'
                    : 'warning'
                }
                size="md"
              >
                {report.verdict}
              </Badge>
              <p className="mt-2 text-xs text-white">{report.action || 'N/A'}</p>
            </div>
            <div className="rounded-lg bg-slate-900 px-2 py-2 text-[11px]">
              <p className="text-white">Canonical</p>
              <p className="mt-0.5 text-slate-300">
                {report.canonical_outcome?.disposition} / {report.canonical_outcome?.reporting}
              </p>
            </div>
            {report.str_required && (
              <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-2 py-1.5 text-center text-[11px] font-medium text-red-400">
                STR FILING REQUIRED
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Connecting arrows (mobile-hidden) */}
      <div className="mt-3 hidden lg:flex items-center justify-center gap-0">
        <div className="h-px flex-1 bg-gradient-to-r from-blue-500/30 via-amber-500/30 to-emerald-500/30" />
      </div>
    </div>
  );
}
