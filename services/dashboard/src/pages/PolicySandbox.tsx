import { useState } from 'react';
import { Link } from 'react-router-dom';
import { clsx } from 'clsx';
import { Loading, ErrorMessage, Badge } from '../components';
import { useSimulationDrafts, useSimulate, useSimulateCompare } from '../hooks/useApi';
import type { DraftShift, SimulationReport } from '../types';
import SimulationResultPanel from '../components/sandbox/SimulationResultPanel';
import ComparisonView from '../components/sandbox/ComparisonView';

function DraftCard({
  draft,
  selected,
  onToggleSelect,
  onSimulate,
  isSimulating,
}: {
  draft: DraftShift;
  selected: boolean;
  onToggleSelect: () => void;
  onSimulate: () => void;
  isSimulating: boolean;
}) {
  return (
    <div
      className={clsx(
        'rounded-xl border p-5 transition-all',
        selected
          ? 'border-emerald-500/40 bg-emerald-500/5 ring-1 ring-emerald-500/20'
          : 'border-slate-700/60 bg-slate-800 hover:border-slate-600',
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-slate-100">{draft.name}</h3>
          <p className="mt-1 text-xs text-slate-400 leading-relaxed">{draft.description}</p>
        </div>
        <label className="ml-3 flex items-center">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="h-4 w-4 rounded border-slate-600 bg-slate-700 text-emerald-500 focus:ring-emerald-500/30"
          />
        </label>
      </div>

      {/* Trigger Signals */}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {draft.trigger_signals.map((sig) => (
          <Badge key={sig} variant="info" size="sm">
            {sig}
          </Badge>
        ))}
      </div>

      {/* Typologies + Citation */}
      <div className="mt-3 space-y-1">
        <div className="flex flex-wrap gap-1">
          {draft.affected_typologies.map((t) => (
            <span key={t} className="text-[10px] text-slate-500">
              {t.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
        {draft.citation && (
          <p className="text-[10px] text-slate-600 italic">{draft.citation}</p>
        )}
      </div>

      {/* Parameter Change */}
      <div className="mt-3 rounded-md bg-slate-900/50 px-3 py-2">
        <p className="text-[10px] text-slate-500">
          <span className="font-mono">{draft.parameter}</span>:{' '}
          <span className="text-slate-400">{draft.old_value === null ? 'none' : String(draft.old_value)}</span>
          {' \u2192 '}
          <span className="text-emerald-400 font-semibold">{String(draft.new_value)}</span>
        </p>
      </div>

      {/* Simulate Button */}
      <button
        onClick={onSimulate}
        disabled={isSimulating}
        className={clsx(
          'mt-4 w-full rounded-lg px-4 py-2 text-sm font-semibold transition-colors',
          isSimulating
            ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
            : 'bg-emerald-600 text-white hover:bg-emerald-500',
        )}
      >
        {isSimulating ? 'Simulating...' : 'Simulate'}
      </button>
    </div>
  );
}

export default function PolicySandbox() {
  const { data: drafts, isLoading, error } = useSimulationDrafts();
  const simulateMutation = useSimulate();
  const compareMutation = useSimulateCompare();

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [singleReport, setSingleReport] = useState<SimulationReport | null>(null);
  const [compareReports, setCompareReports] = useState<SimulationReport[] | null>(null);
  const [simulatingId, setSimulatingId] = useState<string | null>(null);

  if (isLoading) return <Loading text="Loading simulation drafts..." />;
  if (error) return <ErrorMessage error={error as Error} />;

  const draftList = drafts ?? [];

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSimulate(draftId: string) {
    setSimulatingId(draftId);
    setCompareReports(null);
    try {
      const report = await simulateMutation.mutateAsync(draftId);
      setSingleReport(report);
    } finally {
      setSimulatingId(null);
    }
  }

  async function handleCompare() {
    const ids = Array.from(selectedIds);
    if (ids.length < 2) return;
    setSingleReport(null);
    setSimulatingId('__compare__');
    try {
      const reports = await compareMutation.mutateAsync(ids);
      setCompareReports(reports);
    } finally {
      setSimulatingId(null);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Policy Sandbox</h1>
          <p className="mt-1 text-sm text-slate-400">
            Simulate policy changes before enacting them
          </p>
        </div>
        <Link
          to="/policy-shifts"
          className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
        >
          View enacted shifts {'\u2192'}
        </Link>
      </div>

      {/* Draft Cards Grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {draftList.map((draft) => (
          <DraftCard
            key={draft.id}
            draft={draft}
            selected={selectedIds.has(draft.id)}
            onToggleSelect={() => toggleSelect(draft.id)}
            onSimulate={() => handleSimulate(draft.id)}
            isSimulating={simulatingId === draft.id}
          />
        ))}
      </div>

      {/* Compare Button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleCompare}
          disabled={selectedIds.size < 2 || simulatingId === '__compare__'}
          className={clsx(
            'rounded-lg px-5 py-2 text-sm font-semibold transition-colors',
            selectedIds.size >= 2
              ? 'bg-blue-600 text-white hover:bg-blue-500'
              : 'bg-slate-700 text-slate-500 cursor-not-allowed',
          )}
        >
          {simulatingId === '__compare__'
            ? 'Comparing...'
            : `Compare Selected (${selectedIds.size})`}
        </button>
        {selectedIds.size > 0 && selectedIds.size < 2 && (
          <p className="text-xs text-slate-500">Select at least 2 drafts to compare</p>
        )}
      </div>

      {/* Loading indicator */}
      {simulatingId && (
        <Loading
          text={
            simulatingId === '__compare__'
              ? 'Running comparison simulation...'
              : 'Running simulation...'
          }
        />
      )}

      {/* Single Simulation Result */}
      {singleReport && !simulatingId && (
        <SimulationResultPanel
          report={singleReport}
          onDiscard={() => setSingleReport(null)}
        />
      )}

      {/* Comparison View */}
      {compareReports && !simulatingId && (
        <ComparisonView
          reports={compareReports}
          onDiscard={() => setCompareReports(null)}
        />
      )}

      {/* Empty state */}
      {draftList.length === 0 && (
        <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-8 text-center">
          <p className="text-sm text-slate-400">No draft policies available for simulation.</p>
        </div>
      )}
    </div>
  );
}
