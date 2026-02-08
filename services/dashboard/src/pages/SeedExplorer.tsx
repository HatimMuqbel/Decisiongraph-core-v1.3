import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge, Loading, ErrorMessage, Modal, dispositionVariant } from '../components';
import type { SeedScenario } from '../types';
import { useDecide } from '../hooks/useApi';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

// Static scenario data from aml_seed_generator.py (20 scenarios)
const SCENARIOS: (SeedScenario & { seedCount: number })[] = [
  { name: 'clean_known_customer', description: 'Known customer, normal pattern, under $10K', base_facts: { 'customer.type': 'individual', 'customer.relationship_length': 'established', 'txn.amount_band': '3k_10k', 'txn.cross_border': false, 'flag.structuring': false, 'screening.sanctions_match': false }, outcome: { disposition: 'ALLOW', disposition_basis: 'DISCRETIONARY', reporting: 'NO_REPORT' }, decision_level: 'analyst', weight: 0.25, seedCount: 375 },
  { name: 'new_customer_large_clear', description: 'New customer, >$10K, source clear, LCTR required', base_facts: { 'customer.type': 'individual', 'customer.relationship_length': 'new', 'txn.amount_band': '10k_25k', 'txn.source_of_funds_clear': true }, outcome: { disposition: 'ALLOW', disposition_basis: 'DISCRETIONARY', reporting: 'FILE_LCTR' }, decision_level: 'analyst', weight: 0.08, seedCount: 120 },
  { name: 'structuring_suspected', description: 'Just below $10K, multiple same day', base_facts: { 'txn.amount_band': '3k_10k', 'flag.structuring': true, 'txn.round_amount': true }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'analyst', weight: 0.06, seedCount: 90 },
  { name: 'round_amount_reporting', description: 'Round amount in reporting range', base_facts: { 'txn.amount_band': '10k_25k', 'txn.round_amount': true }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'analyst', weight: 0.04, seedCount: 60 },
  { name: 'source_of_funds_unclear', description: 'Source of funds unclear', base_facts: { 'txn.source_of_funds_clear': false, 'txn.stated_purpose': 'unclear' }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'analyst', weight: 0.05, seedCount: 75 },
  { name: 'stated_purpose_unclear', description: 'Stated purpose unclear', base_facts: { 'txn.stated_purpose': 'unclear' }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'analyst', weight: 0.04, seedCount: 60 },
  { name: 'adverse_media', description: 'Adverse media match', base_facts: { 'screening.adverse_media': true }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'analyst', weight: 0.04, seedCount: 60 },
  { name: 'rapid_movement', description: 'Rapid in/out movement', base_facts: { 'flag.rapid_movement': true }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'analyst', weight: 0.04, seedCount: 60 },
  { name: 'profile_deviation', description: 'Activity unusual for customer profile', base_facts: { 'flag.unusual_for_profile': true }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'analyst', weight: 0.04, seedCount: 60 },
  { name: 'third_party', description: 'Third-party payment', base_facts: { 'flag.third_party': true }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'analyst', weight: 0.03, seedCount: 45 },
  { name: 'layering_shell', description: 'Layering / shell company indicators', base_facts: { 'flag.layering': true, 'flag.shell_company': true }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'analyst', weight: 0.04, seedCount: 60 },
  { name: 'high_risk_country', description: 'High-risk country destination', base_facts: { 'txn.cross_border': true, 'txn.destination_country_risk': 'high' }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'senior_analyst', weight: 0.04, seedCount: 60 },
  { name: 'cash_intensive_large', description: 'Cash-intensive business, large amount', base_facts: { 'customer.cash_intensive': true, 'txn.amount_band': '25k_100k', 'txn.type': 'cash' }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'senior_analyst', weight: 0.04, seedCount: 60 },
  { name: 'pep_large_amount', description: 'PEP, large amount', base_facts: { 'customer.pep': true, 'screening.pep_match': true, 'txn.amount_band': '25k_100k' }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'senior_analyst', weight: 0.04, seedCount: 60 },
  { name: 'pep_screening_match', description: 'PEP screening match', base_facts: { 'screening.pep_match': true, 'customer.pep': true }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'senior_analyst', weight: 0.03, seedCount: 45 },
  { name: 'sanctions_match', description: 'Sanctions match - mandatory block', base_facts: { 'screening.sanctions_match': true }, outcome: { disposition: 'BLOCK', disposition_basis: 'MANDATORY', reporting: 'FILE_STR' }, decision_level: 'manager', weight: 0.03, seedCount: 45 },
  { name: 'one_prior_sar', description: '1 prior SAR - normal processing', base_facts: { 'prior.sars_filed': 1 }, outcome: { disposition: 'ALLOW', disposition_basis: 'DISCRETIONARY', reporting: 'NO_REPORT' }, decision_level: 'analyst', weight: 0.03, seedCount: 45 },
  { name: 'multiple_prior_sars', description: '2-3 prior SARs - escalate', base_facts: { 'prior.sars_filed': 3 }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'senior_analyst', weight: 0.03, seedCount: 45 },
  { name: 'heavy_sar_history', description: '4+ prior SARs - block for exit review', base_facts: { 'prior.sars_filed': 4 }, outcome: { disposition: 'BLOCK', disposition_basis: 'DISCRETIONARY', reporting: 'FILE_STR' }, decision_level: 'manager', weight: 0.02, seedCount: 30 },
  { name: 'previous_closure', description: 'Previous account closure - escalate', base_facts: { 'prior.account_closures': true }, outcome: { disposition: 'EDD', disposition_basis: 'DISCRETIONARY', reporting: 'PENDING_EDD' }, decision_level: 'senior_analyst', weight: 0.03, seedCount: 45 },
];

const DISP_COLORS: Record<string, string> = {
  ALLOW: '#10b981',
  EDD: '#f59e0b',
  BLOCK: '#ef4444',
};

export default function SeedExplorer() {
  const [filter, setFilter] = useState('');
  const [dispositionFilter, setDispositionFilter] = useState<string>('');
  const [selected, setSelected] = useState<(typeof SCENARIOS)[0] | null>(null);
  const navigate = useNavigate();
  const decideMut = useDecide();

  const filtered = SCENARIOS.filter((s) => {
    const matchText =
      !filter ||
      s.name.toLowerCase().includes(filter.toLowerCase()) ||
      s.description.toLowerCase().includes(filter.toLowerCase());
    const matchDisp = !dispositionFilter || s.outcome.disposition === dispositionFilter;
    return matchText && matchDisp;
  });

  const chartData = filtered.map((s) => ({
    name: s.name.replace(/_/g, ' ').slice(0, 18),
    seeds: s.seedCount,
    disposition: s.outcome.disposition,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Seed Explorer</h1>
        <p className="mt-1 text-sm text-slate-400">
          Browse 20 AML scenarios and 1,500 generated seed precedents
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search scenarios…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
        />
        <select
          value={dispositionFilter}
          onChange={(e) => setDispositionFilter(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:border-emerald-500 focus:outline-none"
        >
          <option value="">All Dispositions</option>
          <option value="ALLOW">ALLOW</option>
          <option value="EDD">EDD</option>
          <option value="BLOCK">BLOCK</option>
        </select>
      </div>

      {/* Chart */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Seed Count by Scenario
        </h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} margin={{ left: 10 }}>
            <XAxis
              dataKey="name"
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              angle={-45}
              textAnchor="end"
              height={80}
            />
            <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
              itemStyle={{ color: '#e2e8f0' }}
            />
            <Bar dataKey="seeds" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, idx) => (
                <Cell key={idx} fill={DISP_COLORS[entry.disposition] || '#64748b'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Scenario Grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filtered.map((s) => (
          <div
            key={s.name}
            onClick={() => setSelected(s)}
            className="cursor-pointer rounded-xl border border-slate-700/60 bg-slate-800 p-5 transition-all hover:border-slate-600 hover:shadow-lg"
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-slate-100">{s.name.replace(/_/g, ' ')}</h3>
                <p className="mt-1 text-xs text-slate-400">{s.description}</p>
              </div>
              <Badge variant={dispositionVariant(s.outcome.disposition)}>
                {s.outcome.disposition}
              </Badge>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
              <div>
                <p className="text-slate-500">Seeds</p>
                <p className="font-bold text-slate-200">{s.seedCount}</p>
              </div>
              <div>
                <p className="text-slate-500">Weight</p>
                <p className="font-bold text-slate-200">{(s.weight * 100).toFixed(0)}%</p>
              </div>
              <div>
                <p className="text-slate-500">Level</p>
                <p className="font-bold text-slate-200">{s.decision_level}</p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-1">
              {Object.keys(s.base_facts).slice(0, 4).map((k) => (
                <span key={k} className="rounded-md bg-slate-700 px-1.5 py-0.5 text-[10px] text-slate-400">
                  {k}
                </span>
              ))}
              {Object.keys(s.base_facts).length > 4 && (
                <span className="text-[10px] text-slate-500">
                  +{Object.keys(s.base_facts).length - 4} more
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Detail Modal */}
      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.name?.replace(/_/g, ' ') ?? 'Scenario Detail'}
        wide
      >
        {selected && (
          <div className="space-y-5">
            <p className="text-sm text-slate-400">{selected.description}</p>

            {/* Outcome */}
            <div className="rounded-lg bg-slate-900 p-4">
              <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500">Outcome</h3>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-xs text-slate-500">Disposition</p>
                  <Badge variant={dispositionVariant(selected.outcome.disposition)} size="md">
                    {selected.outcome.disposition}
                  </Badge>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Basis</p>
                  <p className="text-sm text-slate-200">{selected.outcome.disposition_basis}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Reporting</p>
                  <p className="text-sm text-slate-200">{selected.outcome.reporting}</p>
                </div>
              </div>
            </div>

            {/* Base Facts */}
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500">
                Base Facts (Pinned)
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="px-3 py-2 text-left text-xs text-slate-400">Field</th>
                      <th className="px-3 py-2 text-left text-xs text-slate-400">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(selected.base_facts).map(([k, v]) => (
                      <tr key={k} className="border-b border-slate-800">
                        <td className="px-3 py-2 font-mono text-xs text-slate-300">{k}</td>
                        <td className="px-3 py-2 text-xs text-slate-200">
                          {typeof v === 'boolean' ? (
                            <Badge variant={v ? 'danger' : 'success'}>{String(v)}</Badge>
                          ) : (
                            String(v)
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-lg bg-slate-900 p-3 text-center">
                <p className="text-xs text-slate-500">Total Seeds</p>
                <p className="text-xl font-bold text-slate-100">{selected.seedCount}</p>
              </div>
              <div className="rounded-lg bg-slate-900 p-3 text-center">
                <p className="text-xs text-slate-500">Weight</p>
                <p className="text-xl font-bold text-slate-100">
                  {(selected.weight * 100).toFixed(0)}%
                </p>
              </div>
              <div className="rounded-lg bg-slate-900 p-3 text-center">
                <p className="text-xs text-slate-500">Decision Level</p>
                <p className="text-xl font-bold text-slate-100">{selected.decision_level}</p>
              </div>
            </div>

            <p className="text-xs text-slate-500">
              Remaining fields (not listed in base_facts) are filled with realistic random values
              using weighted distributions appropriate for the scenario disposition.
              ~10% noise variants apply minority-outcome overrides for training diversity.
            </p>

            {/* Run Through Pipeline */}
            <button
              onClick={async () => {
                if (!selected) return;
                try {
                  const pack = await decideMut.mutateAsync({
                    case_id: `seed_${selected.name}`,
                    ...selected.base_facts,
                    customer: selected.base_facts,
                    transaction: selected.base_facts,
                  });
                  setSelected(null);
                  navigate(`/reports/${pack.meta.decision_id}`);
                } catch {
                  // error handled by mutation state
                }
              }}
              disabled={decideMut.isPending}
              className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 transition"
            >
              {decideMut.isPending ? 'Running Pipeline…' : 'Run Through Pipeline → View Report'}
            </button>
            {decideMut.error && (
              <p className="text-xs text-red-400">
                Error: {(decideMut.error as Error).message}
              </p>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
