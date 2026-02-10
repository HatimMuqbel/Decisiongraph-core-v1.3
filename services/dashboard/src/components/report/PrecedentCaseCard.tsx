import type { SampleCase } from '../../types';
import Badge from '../Badge';
import { dispositionVariant } from '../Badge';
import { clsx } from 'clsx';

interface Props {
  sc: SampleCase;
  defaultOpen?: boolean;
}

const V3_FIELD_LABELS: Record<string, string> = {
  'customer.type': 'Customer type',
  'customer.relationship_length': 'Relationship',
  'customer.pep': 'PEP status',
  'customer.high_risk_jurisdiction': 'High-risk jurisdiction',
  'customer.high_risk_industry': 'High-risk industry',
  'customer.cash_intensive': 'Cash-intensive',
  'txn.type': 'Transaction type',
  'txn.amount_band': 'Amount band',
  'txn.cross_border': 'Cross-border',
  'txn.destination_country_risk': 'Destination risk',
  'flag.structuring': 'Structuring',
  'flag.rapid_movement': 'Rapid movement',
  'flag.layering': 'Layering',
  'flag.shell_company': 'Shell company',
  'flag.unusual_for_profile': 'Unusual activity',
  'screening.sanctions_match': 'Sanctions',
  'screening.adverse_media': 'Adverse media',
};

function formatDriverLabel(d: string): string {
  return V3_FIELD_LABELS[d] ?? d.replace(/^(flag|txn|customer|screening)\./, '').replace(/_/g, ' ');
}

export default function PrecedentCaseCard({ sc, defaultOpen }: Props) {
  const borderColor =
    sc.non_transferable
      ? 'border-l-amber-500'
      : sc.classification === 'supporting'
      ? 'border-l-emerald-500'
      : sc.classification === 'contrary'
      ? 'border-l-red-500'
      : 'border-l-slate-600';

  const classificationVariant =
    sc.non_transferable
      ? 'warning' as const
      : sc.classification === 'supporting'
      ? 'success' as const
      : sc.classification === 'contrary'
      ? 'danger' as const
      : 'neutral' as const;

  return (
    <details
      className={clsx(
        'rounded-lg border border-slate-700/60 border-l-4 bg-slate-800/50 overflow-hidden',
        borderColor,
      )}
      open={defaultOpen}
    >
      <summary className="flex cursor-pointer items-center gap-3 px-4 py-3 text-sm hover:bg-slate-700/30 transition-colors">
        <span className="font-mono text-xs text-slate-400 min-w-[80px]">
          {sc.precedent_id?.slice(0, 10)}…
        </span>
        <Badge variant={dispositionVariant(sc.outcome_normalized || sc.disposition)}>
          {sc.outcome_label || sc.disposition}
        </Badge>
        <span className="text-base font-bold text-slate-200">{sc.similarity_pct}%</span>
        <Badge variant={classificationVariant}>
          {sc.non_transferable ? '⚠ Non-Transferable' : sc.classification}
        </Badge>
        {sc.appealed && <Badge variant="warning">APPEALED</Badge>}
      </summary>

      <div className="space-y-3 px-4 pb-4 pt-1 text-xs">
        {/* Non-transferable warning */}
        {sc.non_transferable && sc.non_transferable_reasons && sc.non_transferable_reasons.length > 0 && (
          <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-2">
            <p className="font-medium text-amber-400">Non-Transferable — reasons:</p>
            <ul className="mt-1 space-y-0.5 text-amber-300/80">
              {sc.non_transferable_reasons.map((r, i) => (
                <li key={i}>• {r}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Driver comparison */}
        {(sc.matched_drivers?.length || sc.mismatched_drivers?.length) ? (
          <div className="space-y-2">
            {sc.matched_drivers && sc.matched_drivers.length > 0 && (
              <div>
                <span className="text-emerald-400 font-medium">Matched drivers: </span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {sc.matched_drivers.map((d, i) => (
                    <span key={i} className="inline-block rounded-md bg-emerald-500/15 px-2 py-0.5 text-[11px] text-emerald-400 border border-emerald-500/20">
                      {formatDriverLabel(d)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {sc.mismatched_drivers && sc.mismatched_drivers.length > 0 && (
              <div>
                <span className="text-red-400 font-medium">Mismatched drivers: </span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {sc.mismatched_drivers.map((d, i) => (
                    <span key={i} className="inline-block rounded-md bg-red-500/15 px-2 py-0.5 text-[11px] text-red-400 border border-red-500/20">
                      {formatDriverLabel(d)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : null}

        {/* Field scores summary (top matches + differences) */}
        {sc.field_scores && Object.keys(sc.field_scores).length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="font-medium text-emerald-400 mb-1">Key Matches</p>
              {Object.entries(sc.field_scores)
                .filter(([, v]) => v >= 70)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 4)
                .map(([k, v]) => (
                  <div key={k} className="flex justify-between text-[11px] py-0.5">
                    <span className="text-slate-400">{V3_FIELD_LABELS[k] ?? k}</span>
                    <span className="text-emerald-400">{v}%</span>
                  </div>
                ))}
            </div>
            <div>
              <p className="font-medium text-red-400 mb-1">Key Differences</p>
              {Object.entries(sc.field_scores)
                .filter(([, v]) => v > 0 && v < 50)
                .sort(([, a], [, b]) => a - b)
                .slice(0, 4)
                .map(([k, v]) => (
                  <div key={k} className="flex justify-between text-[11px] py-0.5">
                    <span className="text-slate-400">{V3_FIELD_LABELS[k] ?? k}</span>
                    <span className="text-red-400">{v}%</span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </details>
  );
}
