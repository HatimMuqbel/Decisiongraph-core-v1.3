interface Props {
  sharedDrivers: string[];
  divergentDrivers: string[];
}

const DRIVER_LABELS: Record<string, string> = {
  'customer.type': 'Customer type',
  'customer.relationship_length': 'Relationship length',
  'customer.pep': 'Politically Exposed Person status',
  'customer.high_risk_jurisdiction': 'High-risk jurisdiction',
  'customer.high_risk_industry': 'High-risk industry',
  'customer.cash_intensive': 'Cash-intensive business',
  'txn.type': 'Transaction type',
  'txn.amount_band': 'Transaction amount range',
  'txn.cross_border': 'Cross-border transaction',
  'txn.destination_country_risk': 'Destination country risk',
  'txn.round_amount': 'Round amount indicator',
  'txn.just_below_threshold': 'Below threshold indicator',
  'txn.multiple_same_day': 'Same-day multiples',
  'txn.pattern_matches_profile': 'Profile consistency',
  'txn.source_of_funds_clear': 'Source of funds clarity',
  'txn.stated_purpose': 'Stated purpose',
  'flag.structuring': 'Structuring indicators',
  'flag.rapid_movement': 'Rapid fund movement',
  'flag.layering': 'Layering indicators',
  'flag.unusual_for_profile': 'Activity unusual for profile',
  'flag.third_party': 'Third-party payment',
  'flag.shell_company': 'Shell company indicators',
  'screening.sanctions_match': 'Sanctions screening match',
  'screening.pep_match': 'PEP screening match',
  'screening.adverse_media': 'Adverse media indicator',
  'prior.sars_filed': 'Prior SARs filed',
  'prior.account_closures': 'Account closures',
};

function formatLabel(d: string): string {
  return DRIVER_LABELS[d] ?? d.replace(/^(flag|txn|customer|screening)[\s.]/, '').replace(/[._]/g, ' ');
}

export default function DriverCausalityPanel({ sharedDrivers, divergentDrivers }: Props) {
  if (sharedDrivers.length === 0 && divergentDrivers.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Decision Driver Analysis
      </h4>

      {sharedDrivers.length > 0 && (
        <div className="mb-3">
          <span className="text-[11px] font-medium text-emerald-400">Shared Drivers:</span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {sharedDrivers.map((d, i) => (
              <span
                key={i}
                className="inline-block rounded-md bg-emerald-500/15 px-2.5 py-1 text-[11px] font-medium text-emerald-400 border border-emerald-500/20"
              >
                {formatLabel(d)}
              </span>
            ))}
          </div>
        </div>
      )}

      {divergentDrivers.length > 0 && (
        <div>
          <span className="text-[11px] font-medium text-red-400">Divergent Drivers:</span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {divergentDrivers.map((d, i) => (
              <span
                key={i}
                className="inline-block rounded-md bg-red-500/15 px-2.5 py-1 text-[11px] font-medium text-red-400 border border-red-500/20"
              >
                {formatLabel(d)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
