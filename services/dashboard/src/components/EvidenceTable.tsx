import Badge, { dispositionVariant } from './Badge';
import type { EvidenceUsed } from '../types';

// --- Banking Field Registry (mirrors backend banking_field_registry.py) ---
const FIELD_LABELS: Record<string, string> = {
  'customer.type': 'Customer entity type',
  'customer.relationship_length': 'Customer relationship duration',
  'customer.pep': 'Politically Exposed Person status',
  'customer.high_risk_jurisdiction': 'High-risk jurisdiction indicator',
  'customer.high_risk_industry': 'High-risk industry indicator',
  'customer.cash_intensive': 'Cash-intensive business indicator',
  'txn.type': 'Transaction type',
  'txn.amount_band': 'Transaction amount range',
  'txn.cross_border': 'Cross-border transaction indicator',
  'txn.destination_country_risk': 'Destination country risk level',
  'txn.round_amount': 'Round amount indicator',
  'txn.just_below_threshold': 'Transaction just below reporting threshold',
  'txn.multiple_same_day': 'Multiple same-day transactions',
  'txn.pattern_matches_profile': 'Transaction pattern consistent with customer profile',
  'txn.source_of_funds_clear': 'Source of funds clarity',
  'txn.stated_purpose': 'Stated transaction purpose',
  'flag.structuring': 'Structuring indicators present',
  'flag.rapid_movement': 'Rapid fund movement indicator',
  'flag.layering': 'Layering indicators present',
  'flag.unusual_for_profile': 'Activity unusual for customer profile',
  'flag.third_party': 'Third-party payment indicator',
  'flag.shell_company': 'Shell company indicators present',
  'screening.sanctions_match': 'Sanctions screening match',
  'screening.pep_match': 'PEP screening match',
  'screening.adverse_media': 'Adverse media indicator',
  'prior.sars_filed': 'Prior Suspicious Activity Reports filed',
  'prior.account_closures': 'Previous account closures on record',
  // Website-name aliases
  'risk.pep': 'Politically Exposed Person status',
  'risk.high_risk_jurisdiction': 'Customer domicile jurisdiction risk',
  'risk.high_risk_industry': 'High-risk industry indicator',
  'risk.cash_intensive_business': 'Cash-intensive business indicator',
  'screen.sanctions_match': 'Sanctions screening match',
  'screen.pep_match': 'PEP screening match',
  'screen.adverse_media': 'Adverse media indicator',
  'screen.prior_sars_filed': 'Prior Suspicious Activity Reports filed',
  'screen.previous_account_closures': 'Previous account closures on record',
  'flag.structuring_suspected': 'Structuring indicators present',
  'flag.layering_indicators': 'Layering indicators present',
  'flag.third_party_payment': 'Third-party payment indicator',
  'flag.shell_company_indicators': 'Shell company indicators present',
  'risk.risk_score': 'Overall risk score',
};

function getLabel(field: string): string {
  return FIELD_LABELS[field] || field.replace(/[._]/g, ' ');
}

function formatValue(v: unknown): string {
  if (v === true) return 'Yes';
  if (v === false) return 'No';
  if (v === null || v === undefined) return '—';
  return String(v);
}

interface EvidenceTableProps {
  evidence: EvidenceUsed[];
  compact?: boolean;
}

export default function EvidenceTable({ evidence, compact }: EvidenceTableProps) {
  if (!evidence.length) {
    return <p className="text-sm text-white">No evidence recorded.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-left">
            <th className="px-3 py-2 text-xs font-medium uppercase text-white">Field</th>
            {!compact && (
              <th className="px-3 py-2 text-xs font-medium uppercase text-white">Label</th>
            )}
            <th className="px-3 py-2 text-xs font-medium uppercase text-white">Value</th>
          </tr>
        </thead>
        <tbody>
          {evidence.map((ev, i) => {
            const v = formatValue(ev.value);
            const isFlag = ev.field.startsWith('flag.') || ev.field.startsWith('screen');
            const isTruthy = ev.value === true || ev.value === 'true';
            return (
              <tr key={i} className="border-b border-slate-800 hover:bg-slate-800/50">
                <td className="px-3 py-2 font-mono text-xs text-slate-300">{ev.field}</td>
                {!compact && (
                  <td className="px-3 py-2 text-white">{getLabel(ev.field)}</td>
                )}
                <td className="px-3 py-2">
                  {isFlag && isTruthy ? (
                    <Badge variant="danger">{v}</Badge>
                  ) : isFlag ? (
                    <Badge variant="success">{v}</Badge>
                  ) : (
                    <span className="text-slate-200">{v}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Export the label lookup for other components
export { FIELD_LABELS, getLabel };
