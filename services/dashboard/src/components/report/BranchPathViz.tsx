import type { ReportViewModel } from '../../types';
import { clsx } from 'clsx';

interface BranchPathVizProps {
  report: ReportViewModel;
}

/**
 * Visual breadcrumb showing the ltree navigation path through the policy tree.
 * Shows Route → Narrow → Cite stages.
 */
export default function BranchPathViz({ report }: BranchPathVizProps) {
  const path = report.decision_path_trace || '';
  const segments = path.split('.').filter(Boolean);

  if (!path || segments.length === 0) {
    return (
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Decision Path
        </h3>
        <p className="text-sm text-slate-500">No decision path trace available.</p>
      </div>
    );
  }

  // Map segments to pipeline stages
  const stages = [
    { label: 'Route', desc: 'Branch selection', icon: '⤵' },
    { label: 'Narrow', desc: 'Node refinement', icon: '⊳' },
    { label: 'Cite', desc: 'Citation match', icon: '§' },
  ];

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Decision Path Navigation
      </h3>

      {/* Full path */}
      <div className="mb-4 rounded-lg bg-slate-900 px-4 py-2">
        <p className="font-mono text-xs text-slate-300 break-all">{path}</p>
      </div>

      {/* Breadcrumb visualization */}
      <div className="flex items-center gap-0 overflow-x-auto pb-2">
        {segments.map((seg, i) => {
          const stageIdx = Math.min(i, stages.length - 1);
          const stage = stages[stageIdx];
          const isLast = i === segments.length - 1;

          return (
            <div key={i} className="flex items-center">
              <div
                className={clsx(
                  'flex flex-col items-center rounded-lg border px-3 py-2 min-w-[80px]',
                  isLast
                    ? 'border-emerald-500/30 bg-emerald-500/10'
                    : 'border-slate-700 bg-slate-900',
                )}
              >
                <span className="text-base">{stage.icon}</span>
                <span className={clsx(
                  'mt-1 font-mono text-[11px] font-medium',
                  isLast ? 'text-emerald-400' : 'text-slate-300',
                )}>
                  {seg}
                </span>
                <span className="mt-0.5 text-[9px] text-slate-500">{stage.label}</span>
              </div>
              {!isLast && (
                <div className="mx-1 text-slate-600">→</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Gate summary */}
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg bg-slate-900 p-3">
          <p className="text-slate-500">Gate 1 (Escalation)</p>
          <p className={clsx(
            'mt-1 font-semibold',
            report.gate1_passed ? 'text-emerald-400' : 'text-red-400',
          )}>
            {report.gate1_decision || 'N/A'}
          </p>
        </div>
        <div className="rounded-lg bg-slate-900 p-3">
          <p className="text-slate-500">Gate 2 (STR)</p>
          <p className={clsx(
            'mt-1 font-semibold',
            report.gate2_status === 'CLEAR' ? 'text-emerald-400' : 'text-amber-400',
          )}>
            {report.gate2_decision || 'N/A'}
          </p>
        </div>
      </div>
    </div>
  );
}
