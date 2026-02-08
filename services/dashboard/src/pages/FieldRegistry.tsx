import { useState, useMemo } from 'react';
import { Badge } from '../components';

// Full 28-field banking field registry (mirrors banking_field_registry.py)
const REGISTRY: {
  canonical: string;
  label: string;
  type: string;
  group: string;
  description: string;
  example: string;
}[] = [
  // Customer fields
  { canonical: 'customer.type', label: 'Customer Type', type: 'enum', group: 'Customer', description: 'Type of customer entity', example: 'individual | corporate' },
  { canonical: 'customer.relationship_length', label: 'Relationship Length', type: 'enum', group: 'Customer', description: 'How long the customer relationship has existed', example: 'new | established' },
  { canonical: 'customer.pep', label: 'Politically Exposed Person', type: 'boolean', group: 'Customer', description: 'Whether customer is a PEP', example: 'true / false' },
  { canonical: 'customer.cash_intensive', label: 'Cash-Intensive Business', type: 'boolean', group: 'Customer', description: 'Whether the customer operates a cash-intensive business', example: 'true / false' },

  // Transaction fields
  { canonical: 'txn.amount_band', label: 'Amount Band', type: 'enum', group: 'Transaction', description: 'Monetary amount range of the transaction', example: '0_3k | 3k_10k | 10k_25k | 25k_100k | 100k_plus' },
  { canonical: 'txn.type', label: 'Transaction Type', type: 'enum', group: 'Transaction', description: 'Type of transaction', example: 'wire | cash | eft | internal' },
  { canonical: 'txn.cross_border', label: 'Cross-Border', type: 'boolean', group: 'Transaction', description: 'Whether the transaction crosses national borders', example: 'true / false' },
  { canonical: 'txn.destination_country_risk', label: 'Destination Country Risk', type: 'enum', group: 'Transaction', description: 'Risk rating of destination country', example: 'low | medium | high' },
  { canonical: 'txn.source_of_funds_clear', label: 'Source of Funds Clear', type: 'boolean', group: 'Transaction', description: 'Whether the source of funds is clearly documented', example: 'true / false' },
  { canonical: 'txn.stated_purpose', label: 'Stated Purpose', type: 'enum', group: 'Transaction', description: 'Purpose of the transaction as stated by customer', example: 'business | personal | investment | unclear' },
  { canonical: 'txn.round_amount', label: 'Round Amount', type: 'boolean', group: 'Transaction', description: 'Whether the transaction is a suspiciously round amount', example: 'true / false' },
  { canonical: 'txn.frequency_vs_norm', label: 'Frequency vs Norm', type: 'enum', group: 'Transaction', description: 'Transaction frequency relative to customer norm', example: 'normal | elevated | high' },

  // Flag fields
  { canonical: 'flag.structuring', label: 'Structuring Suspected', type: 'boolean', group: 'Flags', description: 'Whether structuring pattern is detected (multiple sub-$10K)', example: 'true / false' },
  { canonical: 'flag.rapid_movement', label: 'Rapid In/Out Movement', type: 'boolean', group: 'Flags', description: 'Whether funds are rapidly moved in and out', example: 'true / false' },
  { canonical: 'flag.unusual_for_profile', label: 'Unusual for Profile', type: 'boolean', group: 'Flags', description: 'Whether the activity is unusual for the customer profile', example: 'true / false' },
  { canonical: 'flag.third_party', label: 'Third-Party Payment', type: 'boolean', group: 'Flags', description: 'Whether a third party is involved in the payment', example: 'true / false' },
  { canonical: 'flag.layering', label: 'Layering Indicators', type: 'boolean', group: 'Flags', description: 'Whether layering patterns are detected', example: 'true / false' },
  { canonical: 'flag.shell_company', label: 'Shell Company Indicators', type: 'boolean', group: 'Flags', description: 'Whether shell company involvement is suspected', example: 'true / false' },

  // Screening fields
  { canonical: 'screening.sanctions_match', label: 'Sanctions Match', type: 'boolean', group: 'Screening', description: 'Whether the customer or counterparty matches sanctions lists', example: 'true / false' },
  { canonical: 'screening.pep_match', label: 'PEP Match', type: 'boolean', group: 'Screening', description: 'Whether PEP screening returned a match', example: 'true / false' },
  { canonical: 'screening.adverse_media', label: 'Adverse Media', type: 'boolean', group: 'Screening', description: 'Whether adverse media coverage was found', example: 'true / false' },

  // Prior history
  { canonical: 'prior.sars_filed', label: 'Prior SARs Filed', type: 'integer', group: 'Prior History', description: 'Number of previous SARs/STRs filed for this customer', example: '0 | 1 | 2 | 3 | 4+' },
  { canonical: 'prior.account_closures', label: 'Previous Account Closures', type: 'boolean', group: 'Prior History', description: 'Whether the customer has had accounts previously closed', example: 'true / false' },

  // Website-name aliases (alternative field names used in some adapters)
  { canonical: 'website-name', label: 'Website/Domain Name', type: 'string', group: 'Aliases', description: 'Counterparty website or domain name', example: 'example.com' },
  { canonical: 'account-name', label: 'Account Name', type: 'string', group: 'Aliases', description: 'Name on the account', example: 'Acme Corp' },
  { canonical: 'txn-amount', label: 'Transaction Amount', type: 'number', group: 'Aliases', description: 'Raw transaction amount (before banding)', example: '9999.50' },
  { canonical: 'country-code', label: 'Country Code', type: 'string', group: 'Aliases', description: 'ISO country code', example: 'CA | US | IR' },
  { canonical: 'alert-score', label: 'Alert Score', type: 'number', group: 'Aliases', description: 'Numeric alert score from detection system', example: '0-100' },
];

const GROUPS = ['All', ...Array.from(new Set(REGISTRY.map((r) => r.group)))];
const TYPES = ['All', ...Array.from(new Set(REGISTRY.map((r) => r.type)))];

const TYPE_COLORS: Record<string, string> = {
  boolean: 'text-amber-400 bg-amber-900/30',
  enum: 'text-blue-400 bg-blue-900/30',
  integer: 'text-purple-400 bg-purple-900/30',
  number: 'text-purple-400 bg-purple-900/30',
  string: 'text-slate-300 bg-slate-700',
};

export default function FieldRegistry() {
  const [search, setSearch] = useState('');
  const [group, setGroup] = useState('All');
  const [type, setType] = useState('All');

  const filtered = useMemo(
    () =>
      REGISTRY.filter((f) => {
        const matchSearch =
          !search ||
          f.canonical.toLowerCase().includes(search.toLowerCase()) ||
          f.label.toLowerCase().includes(search.toLowerCase()) ||
          f.description.toLowerCase().includes(search.toLowerCase());
        const matchGroup = group === 'All' || f.group === group;
        const matchType = type === 'All' || f.type === type;
        return matchSearch && matchGroup && matchType;
      }),
    [search, group, type],
  );

  const groupedFields = useMemo(() => {
    const map: Record<string, typeof REGISTRY> = {};
    for (const f of filtered) {
      (map[f.group] ??= []).push(f);
    }
    return map;
  }, [filtered]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Field Registry</h1>
        <p className="mt-1 text-sm text-slate-400">
          28 canonical banking fields used across all AML decision packs and seed generation
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search fields…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
        />
        <select
          value={group}
          onChange={(e) => setGroup(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:border-emerald-500 focus:outline-none"
        >
          {GROUPS.map((g) => (
            <option key={g} value={g}>
              {g === 'All' ? 'All Groups' : g}
            </option>
          ))}
        </select>
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:border-emerald-500 focus:outline-none"
        >
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t === 'All' ? 'All Types' : t}
            </option>
          ))}
        </select>
      </div>

      <p className="text-xs text-slate-500">
        Showing {filtered.length} of {REGISTRY.length} fields
      </p>

      {/* Field Groups */}
      {Object.entries(groupedFields).map(([grp, fields]) => (
        <div key={grp}>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
            {grp}
            <span className="ml-2 text-xs font-normal text-slate-500">({fields.length})</span>
          </h2>
          <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                    Canonical Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                    Display Label
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                    Description
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                    Example
                  </th>
                </tr>
              </thead>
              <tbody>
                {fields.map((f) => (
                  <tr key={f.canonical} className="border-b border-slate-800 hover:bg-slate-700/30">
                    <td className="px-4 py-3 font-mono text-xs text-emerald-400">{f.canonical}</td>
                    <td className="px-4 py-3 text-slate-200">{f.label}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-md px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[f.type] ?? TYPE_COLORS.string}`}
                      >
                        {f.type}
                      </span>
                    </td>
                    <td className="max-w-xs px-4 py-3 text-xs text-slate-400">{f.description}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">{f.example}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {filtered.length === 0 && (
        <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-8 text-center">
          <p className="text-sm text-slate-400">No fields match the current filters.</p>
        </div>
      )}
    </div>
  );
}
