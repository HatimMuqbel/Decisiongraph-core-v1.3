import { useState } from 'react';
import { clsx } from 'clsx';
import type { SimulationReport } from '../../types';
import SimulationResultPanel from './SimulationResultPanel';

const magnitudeStyle: Record<string, string> = {
  FUNDAMENTAL: 'bg-red-500/20 text-red-400 border-red-500/30',
  SIGNIFICANT: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  MODERATE: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  MINOR: 'bg-slate-500/20 text-white border-slate-500/30',
};

interface Props {
  reports: SimulationReport[];
  onDiscard?: () => void;
}

export default function ComparisonView({ reports, onDiscard }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (reports.length === 0) return null;

  // Find best values for highlighting
  const minWorkload = Math.min(...reports.map((r) => r.estimated_analyst_hours_month));
  const minWarnings = Math.min(...reports.map((r) => r.warnings.length));
  const minAffected = Math.min(...reports.map((r) => r.affected_cases));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-slate-100">Side-by-Side Comparison</h2>
        {onDiscard && (
          <button
            onClick={onDiscard}
            className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-600 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Comparison Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-700/60">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700/60 bg-slate-800">
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-white">
                Metric
              </th>
              {reports.map((r) => (
                <th
                  key={r.draft.id}
                  className="px-4 py-3 text-center text-xs font-semibold text-slate-200"
                >
                  {r.draft.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/30 bg-slate-800/50">
            {/* Magnitude */}
            <tr>
              <td className="px-4 py-2.5 text-xs text-white">Magnitude</td>
              {reports.map((r) => (
                <td key={r.draft.id} className="px-4 py-2.5 text-center">
                  <span
                    className={clsx(
                      'inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold',
                      magnitudeStyle[r.magnitude] ?? magnitudeStyle.MINOR,
                    )}
                  >
                    {r.magnitude}
                  </span>
                </td>
              ))}
            </tr>
            {/* Affected */}
            <tr>
              <td className="px-4 py-2.5 text-xs text-white">Affected Cases</td>
              {reports.map((r) => (
                <td
                  key={r.draft.id}
                  className={clsx(
                    'px-4 py-2.5 text-center text-sm font-bold',
                    r.affected_cases === minAffected ? 'text-emerald-400' : 'text-slate-200',
                  )}
                >
                  {r.affected_cases}
                </td>
              ))}
            </tr>
            {/* Escalated */}
            <tr>
              <td className="px-4 py-2.5 text-xs text-white">Escalated</td>
              {reports.map((r) => (
                <td key={r.draft.id} className="px-4 py-2.5 text-center text-sm text-slate-200">
                  {r.escalation_count}
                </td>
              ))}
            </tr>
            {/* New STRs */}
            <tr>
              <td className="px-4 py-2.5 text-xs text-white">New STR Filings</td>
              {reports.map((r) => (
                <td key={r.draft.id} className="px-4 py-2.5 text-center text-sm text-slate-200">
                  {r.new_str_filings}
                </td>
              ))}
            </tr>
            {/* Workload */}
            <tr>
              <td className="px-4 py-2.5 text-xs text-white">Analyst Hours/Mo</td>
              {reports.map((r) => (
                <td
                  key={r.draft.id}
                  className={clsx(
                    'px-4 py-2.5 text-center text-sm font-bold',
                    r.estimated_analyst_hours_month === minWorkload
                      ? 'text-emerald-400'
                      : r.estimated_analyst_hours_month > 100
                        ? 'text-red-400'
                        : 'text-slate-200',
                  )}
                >
                  {r.estimated_analyst_hours_month.toFixed(0)} hrs
                </td>
              ))}
            </tr>
            {/* Filing Cost */}
            <tr>
              <td className="px-4 py-2.5 text-xs text-white">Filing Cost/Mo</td>
              {reports.map((r) => (
                <td key={r.draft.id} className="px-4 py-2.5 text-center text-sm text-slate-200">
                  ${r.estimated_filing_cost_month.toLocaleString()}
                </td>
              ))}
            </tr>
            {/* Warnings */}
            <tr>
              <td className="px-4 py-2.5 text-xs text-white">Warnings</td>
              {reports.map((r) => (
                <td
                  key={r.draft.id}
                  className={clsx(
                    'px-4 py-2.5 text-center text-sm font-bold',
                    r.warnings.length === minWarnings && r.warnings.length === 0
                      ? 'text-emerald-400'
                      : r.warnings.length === minWarnings
                        ? 'text-emerald-400'
                        : r.warnings.length > 3
                          ? 'text-red-400'
                          : 'text-amber-400',
                  )}
                >
                  {r.warnings.length}
                </td>
              ))}
            </tr>
            {/* Cascade Reversals */}
            <tr>
              <td className="px-4 py-2.5 text-xs text-white">Posture Reversals</td>
              {reports.map((r) => {
                const reversals = r.cascade_impacts.filter((c) => c.posture_reversal).length;
                return (
                  <td
                    key={r.draft.id}
                    className={clsx(
                      'px-4 py-2.5 text-center text-sm font-bold',
                      reversals > 0 ? 'text-red-400' : 'text-emerald-400',
                    )}
                  >
                    {reversals}
                  </td>
                );
              })}
            </tr>
            {/* Actions */}
            <tr>
              <td className="px-4 py-2.5 text-xs text-white">Actions</td>
              {reports.map((r, idx) => (
                <td key={r.draft.id} className="px-4 py-2.5 text-center">
                  <button
                    onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                    className="rounded-lg bg-slate-700 px-3 py-1 text-xs font-medium text-slate-300 hover:bg-slate-600 transition-colors"
                  >
                    {expandedIdx === idx ? 'Collapse' : 'Full Report'}
                  </button>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      {/* Expanded full report */}
      {expandedIdx !== null && reports[expandedIdx] && (
        <SimulationResultPanel
          report={reports[expandedIdx]}
          onDiscard={() => setExpandedIdx(null)}
        />
      )}
    </div>
  );
}
