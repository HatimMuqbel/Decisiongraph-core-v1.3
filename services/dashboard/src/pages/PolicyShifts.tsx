import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Badge,
  Loading,
  ErrorMessage,
  PolicyShiftCard,
  StatsCard,
} from '../components';
import { usePolicyShifts, usePolicyShiftCases } from '../hooks/useApi';
import { changeTypeVariant, dispositionVariant } from '../components/Badge';

export default function PolicyShifts() {
  const { data: shifts, isLoading, error } = usePolicyShifts();
  const [selectedShift, setSelectedShift] = useState<string | null>(null);
  const {
    data: cases,
    isLoading: casesLoading,
  } = usePolicyShiftCases(selectedShift ?? '');

  if (isLoading) return <Loading text="Loading policy shifts…" />;
  if (error) return <ErrorMessage error={error as Error} />;

  const shiftList = shifts ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Policy Shifts</h1>
          <p className="mt-1 text-sm text-white">
            Track how regulatory and internal policy changes affect decision outcomes
          </p>
        </div>
        <Link
          to="/sandbox"
          className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
        >
          Simulate new policies {'\u2192'}
        </Link>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatsCard
          label="Active Shifts"
          value={shiftList.length}
          sub="Tracked policy changes"
        />
        <StatsCard
          label="Total Cases Affected"
          value={shiftList.reduce((a, s) => a + (s.cases_affected ?? 0), 0)}
          sub="Across all shifts"
        />
        <StatsCard
          label="Avg Impact"
          value={
            shiftList.length
              ? `${(shiftList.reduce((a, s) => a + (s.pct_affected ?? 0), 0) / shiftList.length).toFixed(1)}%`
              : '–'
          }
          sub="Mean impact percentage"
        />
      </div>

      {/* Shift Cards */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {shiftList.map((shift) => (
          <div
            key={shift.id}
            onClick={() =>
              setSelectedShift(
                selectedShift === shift.id ? null : shift.id,
              )
            }
            className="cursor-pointer"
          >
            <PolicyShiftCard shift={shift} />
          </div>
        ))}
      </div>

      {shiftList.length === 0 && (
        <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-8 text-center">
          <p className="text-sm text-white">
            No policy shifts detected. Shifts are created when decision pack rules
            or thresholds change between policy versions.
          </p>
        </div>
      )}

      {/* Cases Panel */}
      {selectedShift && (
        <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
          <h2 className="mb-4 text-lg font-semibold text-slate-100">
            Affected Cases –{' '}
            <span className="text-emerald-400">
              {shiftList.find((s) => s.id === selectedShift)?.name ?? selectedShift}
            </span>
          </h2>

          {casesLoading ? (
            <Loading text="Loading cases…" />
          ) : cases && cases.cases.length > 0 ? (
            <div className="overflow-x-auto">
              <p className="mb-3 text-xs text-white">
                {cases.total_cases} total cases analyzed
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="px-3 py-2 text-left text-xs text-white">Precedent ID</th>
                    <th className="px-3 py-2 text-left text-xs text-white">Summary</th>
                    <th className="px-3 py-2 text-left text-xs text-white">Before</th>
                    <th className="px-3 py-2 text-left text-xs text-white">After</th>
                    <th className="px-3 py-2 text-left text-xs text-white">Change Type</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.cases.map((c, idx) => (
                    <tr key={idx} className="border-b border-slate-800 hover:bg-slate-700/30">
                      <td className="px-3 py-2 font-mono text-xs text-slate-300">
                        {c.precedent_id}
                      </td>
                      <td className="max-w-xs truncate px-3 py-2 text-xs text-white">
                        {c.case_summary}
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={dispositionVariant(c.outcome_before?.disposition || '')}>
                          {c.outcome_before?.disposition || '–'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={dispositionVariant(c.outcome_after?.disposition || '')}>
                          {c.outcome_after?.disposition || '–'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={changeTypeVariant(c.change_type || '')}>
                          {c.change_type || '–'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-white">No cases found for this shift.</p>
          )}
        </div>
      )}
    </div>
  );
}
