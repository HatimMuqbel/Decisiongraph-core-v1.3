import { useState } from 'react';
import { clsx } from 'clsx';
import type { SimulationReport } from '../../types';
import CascadeImpactPanel from './CascadeImpactPanel';

const magnitudeStyle: Record<string, string> = {
  FUNDAMENTAL: 'bg-red-500/20 text-red-400 border-red-500/30',
  SIGNIFICANT: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  MODERATE: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  MINOR: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

function MetricCard({
  label,
  value,
  sub,
  variant = 'neutral',
}: {
  label: string;
  value: string | number;
  sub: string;
  variant?: 'danger' | 'warning' | 'success' | 'neutral';
}) {
  const border =
    variant === 'danger'
      ? 'border-red-500/30'
      : variant === 'warning'
        ? 'border-amber-500/30'
        : variant === 'success'
          ? 'border-emerald-500/30'
          : 'border-slate-700/60';
  return (
    <div className={clsx('rounded-lg border bg-slate-800/80 p-4', border)}>
      <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-bold text-slate-100">{value}</p>
      <p className="text-[11px] text-slate-500">{sub}</p>
    </div>
  );
}

function RiskBar({ counts, label }: { counts: Record<string, number>; label: string }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) return null;
  const segments = [
    { key: 'ALLOW', color: 'bg-emerald-500' },
    { key: 'EDD', color: 'bg-amber-500' },
    { key: 'BLOCK', color: 'bg-red-500' },
  ];
  return (
    <div className="flex items-center gap-3">
      <span className="w-14 text-right text-xs text-slate-500">{label}</span>
      <div className="flex flex-1 h-5 overflow-hidden rounded-md">
        {segments.map(({ key, color }) => {
          const n = counts[key] ?? 0;
          if (n === 0) return null;
          const pct = (n / total) * 100;
          return (
            <div
              key={key}
              className={clsx(color, 'flex items-center justify-center text-[9px] font-bold text-white')}
              style={{ width: `${pct}%`, minWidth: n > 0 ? '20px' : 0 }}
              title={`${key}: ${n} (${pct.toFixed(0)}%)`}
            >
              {pct >= 12 ? `${key} ${pct.toFixed(0)}%` : ''}
            </div>
          );
        })}
      </div>
      <span className="w-12 text-xs text-slate-500">{total}</span>
    </div>
  );
}

function ChangeRows({ changes, type }: { changes: Record<string, number>; type: 'escalation' | 'reporting' }) {
  const entries = Object.entries(changes).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    return <p className="text-xs text-slate-500 italic">No {type === 'escalation' ? 'disposition' : 'reporting'} changes</p>;
  }
  const max = Math.max(...entries.map(([, v]) => v));
  return (
    <div className="space-y-1.5">
      {entries.map(([label, count]) => (
        <div key={label} className="flex items-center gap-2">
          <span className="w-36 text-xs text-slate-300 font-mono">{label}</span>
          <span className="w-14 text-right text-xs text-slate-400">{count} cases</span>
          <div className="flex-1 h-3 rounded-sm bg-slate-700/50 overflow-hidden">
            <div
              className={clsx(
                'h-full rounded-sm',
                type === 'escalation' ? 'bg-red-500/60' : 'bg-amber-500/60',
              )}
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

interface Props {
  report: SimulationReport;
  onDiscard?: () => void;
}

export default function SimulationResultPanel({ report, onDiscard }: Props) {
  const [showCases, setShowCases] = useState(false);
  const [showEnact, setShowEnact] = useState(false);
  const r = report;

  const affectedVariant =
    r.affected_cases > 50 ? 'danger' : r.affected_cases > 10 ? 'warning' : 'success';
  const workloadHrs = r.estimated_analyst_hours_month;

  return (
    <div className="space-y-5 rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-bold text-slate-100">{r.draft.name}</h2>
        <span
          className={clsx(
            'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold',
            magnitudeStyle[r.magnitude] ?? magnitudeStyle.MINOR,
          )}
        >
          {r.magnitude}
        </span>
        <span className="ml-auto text-[11px] text-slate-500">
          {new Date(r.timestamp).toLocaleString()}
        </span>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard
          label="Affected"
          value={r.affected_cases}
          sub={`of ${r.total_cases_evaluated} evaluated`}
          variant={affectedVariant}
        />
        <MetricCard
          label="Escalated"
          value={r.escalation_count}
          sub="cases escalated"
          variant={r.escalation_count > 20 ? 'danger' : r.escalation_count > 0 ? 'warning' : 'success'}
        />
        <MetricCard
          label="New STRs"
          value={r.new_str_filings}
          sub="filings"
          variant={r.new_str_filings > 20 ? 'danger' : r.new_str_filings > 0 ? 'warning' : 'success'}
        />
        <MetricCard
          label="Workload"
          value={`${workloadHrs.toFixed(0)} hrs`}
          sub="/month"
          variant={workloadHrs > 100 ? 'danger' : workloadHrs > 30 ? 'warning' : 'success'}
        />
      </div>

      {/* Risk Distribution */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Risk Distribution
        </h3>
        <RiskBar counts={r.risk_before} label="Before" />
        <RiskBar counts={r.risk_after} label="After" />
      </div>

      {/* Disposition + Reporting Changes */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Disposition Changes
          </h3>
          <ChangeRows changes={r.disposition_changes} type="escalation" />
        </div>
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Reporting Changes
          </h3>
          <ChangeRows changes={r.reporting_changes} type="reporting" />
        </div>
      </div>

      {/* Workload Impact */}
      <div className="rounded-lg border border-slate-700/40 bg-slate-800/50 p-4 space-y-1.5">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
          Workload Impact
        </h3>
        <p className="text-xs text-slate-300">
          Additional EDD reviews: <span className="font-mono">{r.additional_edd_cases}</span>{' '}
          {'\u00D7'} 2.5 hrs ={' '}
          <span className="font-bold">{(r.additional_edd_cases * 2.5).toFixed(1)} hrs/month</span>
        </p>
        <p className="text-xs text-slate-300">
          Additional STR filings: <span className="font-mono">{r.additional_str_filings}</span>{' '}
          {'\u00D7'} 1.5 hrs ={' '}
          <span className="font-bold">{(r.additional_str_filings * 1.5).toFixed(1)} hrs/month</span>
        </p>
        <p className="text-xs text-slate-300">
          Filing costs: <span className="font-mono">{r.additional_str_filings}</span>{' '}
          {'\u00D7'} $150 ={' '}
          <span className="font-bold">${r.estimated_filing_cost_month.toLocaleString()}/month</span>
        </p>
        <p className={clsx('mt-2 text-sm font-bold', workloadHrs > 100 ? 'text-red-400' : 'text-slate-100')}>
          Total: {workloadHrs.toFixed(0)} analyst hrs + ${r.estimated_filing_cost_month.toLocaleString()} filing costs per month
        </p>
      </div>

      {/* Warnings */}
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Warnings ({r.warnings.length})
        </h3>
        {r.warnings.length === 0 ? (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
            <p className="text-xs text-emerald-400">No unintended consequences detected</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {r.warnings.map((w, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2"
              >
                <span className="mt-0.5 text-amber-400 text-xs">{'\u26A0'}</span>
                <p className="text-xs text-amber-300/90">{w}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Cascade Impact */}
      {r.cascade_impacts.length > 0 && (
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Cascade Impact on Precedent Pool ({r.cascade_impacts.length} typologies)
          </h3>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {r.cascade_impacts.map((ci) => (
              <CascadeImpactPanel key={ci.typology} cascade={ci} />
            ))}
          </div>
        </div>
      )}

      {/* Affected Cases (expandable) */}
      <div>
        <button
          onClick={() => setShowCases(!showCases)}
          className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-200 transition-colors"
        >
          <span>{showCases ? '\u25BC' : '\u25B6'}</span>
          Affected Cases ({r.case_results.filter((c) => c.disposition_changed || c.reporting_changed).length})
        </button>
        {showCases && (
          <div className="mt-2 max-h-64 overflow-y-auto rounded-lg border border-slate-700/40 bg-slate-900/50">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-900">
                <tr className="text-left text-slate-500">
                  <th className="px-3 py-2">Case</th>
                  <th className="px-3 py-2">Disposition</th>
                  <th className="px-3 py-2">Reporting</th>
                  <th className="px-3 py-2">Direction</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/30">
                {r.case_results
                  .filter((c) => c.disposition_changed || c.reporting_changed)
                  .slice(0, 100)
                  .map((c) => (
                    <tr key={c.case_id} className="text-slate-300">
                      <td className="px-3 py-1.5 font-mono">{c.case_id.slice(0, 12)}...</td>
                      <td className="px-3 py-1.5">
                        {c.original_disposition} {'\u2192'} {c.simulated_disposition}
                      </td>
                      <td className="px-3 py-1.5">
                        {c.original_reporting} {'\u2192'} {c.simulated_reporting}
                      </td>
                      <td className="px-3 py-1.5">
                        <span
                          className={clsx(
                            'font-bold',
                            c.escalation_direction === 'UP' && 'text-red-400',
                            c.escalation_direction === 'DOWN' && 'text-emerald-400',
                            c.escalation_direction === 'UNCHANGED' && 'text-slate-500',
                          )}
                        >
                          {c.escalation_direction === 'UP' ? '\u25B2 UP' : c.escalation_direction === 'DOWN' ? '\u25BC DOWN' : '\u2014'}
                        </span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3 border-t border-slate-700/40 pt-4">
        <button
          onClick={() => setShowEnact(true)}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 transition-colors"
        >
          Enact Policy
        </button>
        {onDiscard && (
          <button
            onClick={onDiscard}
            className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-600 transition-colors"
          >
            Discard
          </button>
        )}
      </div>

      {/* Enact Confirmation Dialog */}
      {showEnact && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 space-y-3">
          <p className="text-sm text-red-300">
            This will create a live policy shift affecting{' '}
            <span className="font-bold">{r.affected_cases} cases</span>.{' '}
            {r.warnings.length > 0 && (
              <span className="font-bold">{r.warnings.length} warnings</span>
            )}{' '}
            {r.warnings.length > 0 ? 'were detected.' : ''}
          </p>
          <p className="text-xs text-red-400/70">
            Enactment preview — the shift definition would be created with status READY_TO_ENACT.
          </p>
          <pre className="overflow-x-auto rounded-md bg-slate-900 p-3 text-[11px] text-slate-300">
            {JSON.stringify(
              {
                shift_id: r.draft.id.replace('draft_', ''),
                name: r.draft.name,
                trigger_signals: r.draft.trigger_signals,
                magnitude: r.magnitude,
                cases_affected: r.affected_cases,
                warnings_count: r.warnings.length,
                status: 'READY_TO_ENACT',
              },
              null,
              2,
            )}
          </pre>
          <div className="flex gap-2">
            <button
              onClick={() => setShowEnact(false)}
              className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-600"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
