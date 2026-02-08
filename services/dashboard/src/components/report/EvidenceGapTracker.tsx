import type { ReportViewModel } from '../../types';
import { getLabel } from '../EvidenceTable';

interface EvidenceGapTrackerProps {
  report: ReportViewModel;
}

// All 28 required registry fields
const ALL_REQUIRED_FIELDS = [
  'customer.type', 'customer.relationship_length',
  'customer.pep', 'customer.high_risk_jurisdiction',
  'customer.high_risk_industry', 'customer.cash_intensive',
  'txn.type', 'txn.amount_band', 'txn.cross_border',
  'txn.destination_country_risk', 'txn.round_amount',
  'txn.just_below_threshold', 'txn.multiple_same_day',
  'txn.pattern_matches_profile', 'txn.source_of_funds_clear',
  'txn.stated_purpose',
  'flag.structuring', 'flag.rapid_movement', 'flag.layering',
  'flag.unusual_for_profile', 'flag.third_party', 'flag.shell_company',
  'screening.sanctions_match', 'screening.pep_match', 'screening.adverse_media',
  'prior.sars_filed', 'prior.account_closures',
];

// Optional fields that strengthen assessment
const OPTIONAL_FIELDS = [
  'txn.frequency_30d', 'customer.source_of_wealth',
  'customer.occupation', 'txn.correspondent_bank',
  'customer.beneficial_owner_known',
];

export default function EvidenceGapTracker({ report }: EvidenceGapTrackerProps) {
  const evidenceFields = new Set(report.evidence_used?.map((e) => e.field) ?? []);
  const txnFields = new Set(report.transaction_facts?.map((e) => e.field) ?? []);
  const allPresent = new Set([...evidenceFields, ...txnFields]);

  const present = ALL_REQUIRED_FIELDS.filter((f) => allPresent.has(f));
  const missing = ALL_REQUIRED_FIELDS.filter((f) => !allPresent.has(f));
  const optPresent = OPTIONAL_FIELDS.filter((f) => allPresent.has(f));

  const completeness = ALL_REQUIRED_FIELDS.length > 0
    ? Math.round((present.length / ALL_REQUIRED_FIELDS.length) * 100)
    : 100;

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Evidence Gap Tracker
        </h3>
        <span className="text-xs text-slate-400">
          {completeness}% complete ({present.length}/{ALL_REQUIRED_FIELDS.length} required)
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-4 h-2 rounded-full bg-slate-700">
        <div
          className="h-2 rounded-full transition-all bg-emerald-500"
          style={{ width: `${completeness}%` }}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Present */}
        <div>
          <h4 className="mb-2 flex items-center gap-1 text-xs font-medium text-emerald-400">
            <span>✓</span> Present ({present.length})
          </h4>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {present.map((f) => (
              <div key={f} className="rounded bg-emerald-500/5 px-2 py-1 text-[11px]">
                <span className="text-slate-300">{getLabel(f)}</span>
                <span className="ml-1 font-mono text-[10px] text-slate-500">{f}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Required but missing */}
        <div>
          <h4 className="mb-2 flex items-center gap-1 text-xs font-medium text-amber-400">
            <span>⚠</span> Required — Missing ({missing.length})
          </h4>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {missing.length === 0 ? (
              <p className="text-[11px] text-slate-500">All required fields present.</p>
            ) : (
              missing.map((f) => (
                <div key={f} className="rounded bg-amber-500/5 px-2 py-1 text-[11px]">
                  <span className="text-slate-300">{getLabel(f)}</span>
                  <span className="ml-1 font-mono text-[10px] text-slate-500">{f}</span>
                </div>
              ))
            )}
          </div>
          {missing.length > 0 && (
            <p className="mt-2 text-[10px] text-amber-500/70">
              Missing required fields reduce decision confidence.
            </p>
          )}
        </div>

        {/* Optional */}
        <div>
          <h4 className="mb-2 flex items-center gap-1 text-xs font-medium text-blue-400">
            <span>ℹ</span> Optional ({optPresent.length}/{OPTIONAL_FIELDS.length})
          </h4>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {OPTIONAL_FIELDS.map((f) => (
              <div
                key={f}
                className={`rounded px-2 py-1 text-[11px] ${
                  optPresent.includes(f) ? 'bg-blue-500/5' : 'bg-slate-700/30'
                }`}
              >
                <span className={optPresent.includes(f) ? 'text-slate-300' : 'text-slate-500'}>
                  {getLabel(f)}
                </span>
                <span className="ml-1 font-mono text-[10px] text-slate-600">{f}</span>
                {optPresent.includes(f) && (
                  <span className="ml-1 text-blue-400">✓</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
