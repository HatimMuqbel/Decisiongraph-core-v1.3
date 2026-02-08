import { useState, useMemo } from 'react';
import { Badge, Loading, ErrorMessage, dispositionVariant } from '../components';
import { useDemoCases } from '../hooks/useApi';
import type { DemoCase } from '../types';
import { format } from 'date-fns';

const OUTCOME_OPTIONS = ['', 'ALLOW', 'EDD', 'BLOCK'] as const;
const SCENARIO_TYPES = [
  '',
  'clean_known_customer',
  'structuring_suspected',
  'sanctions_match',
  'pep_large_amount',
  'adverse_media',
  'layering_shell',
  'high_risk_country',
  'source_of_funds_unclear',
  'rapid_movement',
  'profile_deviation',
] as const;

export default function AuditSearch() {
  const { data: allCases, isLoading, error } = useDemoCases();

  const [search, setSearch] = useState('');
  const [outcome, setOutcome] = useState('');
  const [scenario, setScenario] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const filtered = useMemo(() => {
    if (!allCases) return [];
    return allCases.filter((c: DemoCase) => {
      const matchText =
        !search ||
        c.id?.toLowerCase().includes(search.toLowerCase()) ||
        c.name?.toLowerCase().includes(search.toLowerCase()) ||
        c.description?.toLowerCase().includes(search.toLowerCase());

      const matchOutcome = !outcome || c.expected_verdict === outcome;
      const matchScenario = !scenario || c.category === scenario;

      // Date filtering (if the case has a date field)
      const caseDate = (c as Record<string, unknown>).date as string | undefined;
      const matchDateFrom = !dateFrom || (caseDate && caseDate >= dateFrom);
      const matchDateTo = !dateTo || (caseDate && caseDate <= dateTo);

      return matchText && matchOutcome && matchScenario && matchDateFrom && matchDateTo;
    });
  }, [allCases, search, outcome, scenario, dateFrom, dateTo]);

  const exportCsv = () => {
    if (!filtered.length) return;
    const headers = ['ID', 'Name', 'Category', 'Expected Verdict', 'Description'];
    const rows = filtered.map((c) => [
      c.id ?? '',
      c.name ?? '',
      c.category ?? '',
      c.expected_verdict ?? '',
      (c.description ?? '').replace(/"/g, '""'),
    ]);
    const csv = [headers.join(','), ...rows.map((r) => r.map((v) => `"${v}"`).join(','))].join(
      '\n',
    );
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit_export_${format(new Date(), 'yyyyMMdd_HHmmss')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Audit Search</h1>
          <p className="mt-1 text-sm text-slate-400">
            Search and filter case decisions for PCMLTFA/FINTRAC compliance audit trails
          </p>
        </div>
        <button
          onClick={exportCsv}
          disabled={!filtered.length}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-40"
        >
          Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Search</label>
            <input
              type="text"
              placeholder="Case ID, name…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Outcome</label>
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              {OUTCOME_OPTIONS.map((o) => (
                <option key={o} value={o}>
                  {o || 'All Outcomes'}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Scenario Type</label>
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              {SCENARIO_TYPES.map((s) => (
                <option key={s} value={s}>
                  {s ? s.replace(/_/g, ' ') : 'All Scenarios'}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Date From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Date To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-emerald-500 focus:outline-none"
            />
          </div>
        </div>
        <div className="mt-3 flex items-center gap-3 text-xs text-slate-400">
          <span>
            Showing <span className="font-bold text-slate-200">{filtered.length}</span>{' '}
            of <span className="font-bold text-slate-200">{allCases?.length ?? 0}</span> cases
          </span>
          {(search || outcome || scenario || dateFrom || dateTo) && (
            <button
              onClick={() => {
                setSearch('');
                setOutcome('');
                setScenario('');
                setDateFrom('');
                setDateTo('');
              }}
              className="text-emerald-400 hover:text-emerald-300"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <Loading text="Loading cases…" />
      ) : error ? (
        <ErrorMessage error={error as Error} />
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-8 text-center">
          <p className="text-sm text-slate-400">No cases match the current filters.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-800/80">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                  Case ID
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                  Category
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                  Expected Verdict
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                  Description
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c, idx) => (
                <tr
                  key={c.id ?? idx}
                  className="border-b border-slate-800 transition-colors hover:bg-slate-700/30"
                >
                  <td className="px-4 py-3 font-mono text-xs text-emerald-400">
                    {c.id ?? `#${idx + 1}`}
                  </td>
                  <td className="px-4 py-3 text-slate-200">{c.name}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-md bg-slate-700 px-2 py-0.5 text-xs text-slate-300">
                      {c.category?.replace(/_/g, ' ') ?? '–'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={dispositionVariant(c.expected_verdict ?? '')}>
                      {c.expected_verdict ?? '–'}
                    </Badge>
                  </td>
                  <td className="max-w-xs truncate px-4 py-3 text-xs text-slate-400">
                    {c.description ?? '–'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
