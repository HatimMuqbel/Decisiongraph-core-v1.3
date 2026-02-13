import type { ReportViewModel } from '../../types';
import { getLabel } from '../EvidenceTable';
import Badge from '../Badge';

interface ReportEvidenceTableProps {
  report: ReportViewModel;
}

/**
 * Full registry-driven evidence table for Tier 2+.
 * All 28 fields with labels, grouped by category.
 */

const FIELD_GROUPS: { label: string; prefix: string[] }[] = [
  { label: 'Customer', prefix: ['customer.'] },
  { label: 'Transaction', prefix: ['txn.'] },
  { label: 'Red Flags', prefix: ['flag.'] },
  { label: 'Screening', prefix: ['screening.'] },
  { label: 'Prior History', prefix: ['prior.'] },
];

export default function ReportEvidenceTable({ report }: ReportEvidenceTableProps) {
  const allEvidence = report.evidence_used ?? [];

  if (allEvidence.length === 0) {
    return (
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white">
          Full Evidence Table
        </h3>
        <p className="text-sm text-white">No evidence recorded.</p>
      </div>
    );
  }

  // Group evidence by category
  const grouped = FIELD_GROUPS.map((group) => ({
    ...group,
    items: allEvidence.filter((e) =>
      group.prefix.some((p) => e.field.startsWith(p)),
    ),
  })).filter((g) => g.items.length > 0);

  // Uncategorized
  const categorized = new Set(grouped.flatMap((g) => g.items.map((e) => e.field)));
  const uncategorized = allEvidence.filter((e) => !categorized.has(e.field));

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-white">
        Full Evidence Table — Registry Labels ({allEvidence.length} fields)
      </h3>

      <div className="space-y-4">
        {grouped.map((group) => (
          <div key={group.label}>
            <h4 className="mb-2 text-xs font-medium text-white border-b border-slate-700/40 pb-1">
              {group.label}
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left">
                    <th className="px-3 py-1.5 text-[10px] font-medium uppercase text-white w-40">Field</th>
                    <th className="px-3 py-1.5 text-[10px] font-medium uppercase text-white">Label</th>
                    <th className="px-3 py-1.5 text-[10px] font-medium uppercase text-white w-32">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {group.items.map((ev, i) => {
                    const isFlag = ev.field.startsWith('flag.') || ev.field.startsWith('screening');
                    const isTruthy = ev.value === true || ev.value === 'true';
                    return (
                      <tr key={i} className="border-t border-slate-800/50 hover:bg-slate-800/30">
                        <td className="px-3 py-1.5 font-mono text-[11px] text-white">{ev.field}</td>
                        <td className="px-3 py-1.5 text-xs text-slate-300">{getLabel(ev.field)}</td>
                        <td className="px-3 py-1.5">
                          {isFlag && isTruthy ? (
                            <Badge variant="danger">{formatVal(ev.value)}</Badge>
                          ) : isFlag ? (
                            <Badge variant="success">{formatVal(ev.value)}</Badge>
                          ) : (
                            <span className="text-xs text-slate-200">{formatVal(ev.value)}</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ))}

        {uncategorized.length > 0 && (
          <div>
            <h4 className="mb-2 text-xs font-medium text-white border-b border-slate-700/40 pb-1">
              Other
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <tbody>
                  {uncategorized.map((ev, i) => (
                    <tr key={i} className="border-t border-slate-800/50">
                      <td className="px-3 py-1.5 font-mono text-[11px] text-white w-40">{ev.field}</td>
                      <td className="px-3 py-1.5 text-xs text-slate-300">{getLabel(ev.field)}</td>
                      <td className="px-3 py-1.5 text-xs text-slate-200 w-32">{formatVal(ev.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Risk Factors callout */}
      {report.risk_factors && report.risk_factors.length > 0 && (
        <div className="mt-4 rounded-lg bg-amber-500/5 border border-amber-500/10 p-3">
          <h4 className="mb-2 text-xs font-medium text-amber-400">Risk Factors Identified</h4>
          <div className="flex flex-wrap gap-2">
            {report.risk_factors.map((rf, i) => (
              <span key={i} className="rounded-md bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-300">
                {rf.field}: {rf.value}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function formatVal(v: unknown): string {
  if (v === true) return 'Yes';
  if (v === false) return 'No';
  if (v == null) return '—';
  return String(v);
}
