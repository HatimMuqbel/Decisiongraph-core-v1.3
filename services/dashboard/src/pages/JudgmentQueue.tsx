import { useState } from 'react';
import { useDemoCases, useDecide } from '../hooks/useApi';
import {
  Loading,
  ErrorMessage,
  Badge,
  Modal,
  EvidenceTable,
  dispositionVariant,
} from '../components';
import type { DemoCase, DecisionPack } from '../types';

export default function JudgmentQueue() {
  const { data: cases, isLoading, error } = useDemoCases();
  const decideMut = useDecide();
  const [selectedCase, setSelectedCase] = useState<DemoCase | null>(null);
  const [result, setResult] = useState<DecisionPack | null>(null);
  const [filter, setFilter] = useState<string>('');

  if (isLoading) return <Loading />;
  if (error) return <ErrorMessage error={error as Error} />;

  const filtered =
    cases?.filter(
      (c) =>
        !filter ||
        c.name.toLowerCase().includes(filter.toLowerCase()) ||
        c.category.toLowerCase().includes(filter.toLowerCase())
    ) ?? [];

  async function runCase(c: DemoCase) {
    setSelectedCase(c);
    setResult(null);
    try {
      const factsObj: Record<string, unknown> = {};
      c.facts?.forEach((f) => {
        factsObj[f.field_id] = f.value;
      });
      const pack = await decideMut.mutateAsync({
        case_id: c.id,
        ...factsObj,
        customer: factsObj,
        transaction: factsObj,
      });
      setResult(pack);
    } catch {
      // error handled by mutation state
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Judgment Queue</h1>
          <p className="mt-1 text-sm text-slate-400">
            Review demo cases and run them through the decision engine
          </p>
        </div>
        <input
          type="text"
          placeholder="Filter cases…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
        />
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700">
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
                Expected
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                Signals
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-400">
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr key={c.id} className="border-b border-slate-800 hover:bg-slate-700/30">
                <td className="px-4 py-3 font-mono text-xs text-slate-400">{c.id}</td>
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-200">{c.name}</p>
                  <p className="mt-0.5 text-xs text-slate-500">{c.description}</p>
                </td>
                <td className="px-4 py-3">
                  <Badge
                    variant={
                      c.category === 'PASS' ? 'success' : c.category === 'ESCALATE' ? 'danger' : 'warning'
                    }
                  >
                    {c.category}
                  </Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={dispositionVariant(c.expected_verdict)}>{c.expected_verdict}</Badge>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {c.tags?.slice(0, 3).map((t, i) => (
                      <span
                        key={i}
                        className="rounded-md bg-slate-700 px-1.5 py-0.5 text-xs text-slate-300"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => runCase(c)}
                    className="rounded-lg bg-emerald-500/20 px-3 py-1.5 text-xs font-medium text-emerald-400 hover:bg-emerald-500/30 transition"
                  >
                    Run Engine
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Result Modal */}
      <Modal
        open={!!selectedCase}
        onClose={() => {
          setSelectedCase(null);
          setResult(null);
        }}
        title={selectedCase?.name ?? 'Case Details'}
        wide
      >
        {decideMut.isPending && <Loading text="Running decision engine…" />}
        {decideMut.error && <ErrorMessage error={decideMut.error as Error} title="Engine error" />}
        {result && (
          <div className="space-y-5">
            {/* Verdict */}
            <div className="flex items-center gap-4">
              <Badge variant={dispositionVariant(result.decision.verdict)} size="md">
                {result.decision.verdict}
              </Badge>
              <span className="text-sm text-slate-400">{result.decision.action}</span>
              {result.decision.str_required && (
                <Badge variant="danger" size="md">
                  STR REQUIRED
                </Badge>
              )}
            </div>

            {/* Decision ID */}
            <div className="rounded-lg bg-slate-900 p-3">
              <p className="text-xs text-slate-500">Decision ID</p>
              <p className="mt-0.5 break-all font-mono text-xs text-slate-300">
                {result.meta.decision_id}
              </p>
            </div>

            {/* Evidence */}
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-300">Evidence Used</h3>
              <EvidenceTable evidence={result.evaluation_trace.evidence_used} />
            </div>

            {/* Rules Fired */}
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-300">Rules Fired</h3>
              <div className="space-y-1">
                {result.evaluation_trace.rules_fired.map((r, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <Badge
                      variant={r.result === 'TRIGGERED' ? 'danger' : 'success'}
                    >
                      {r.result}
                    </Badge>
                    <span className="font-mono text-slate-300">{r.code}</span>
                    <span className="text-slate-500">{r.reason}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Classifier */}
            {result.classifier && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-300">Classification</h3>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-500">Outcome:</span>{' '}
                    <span className="text-slate-200">{result.classifier.outcome}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Tier 1 signals:</span>{' '}
                    <span className="text-slate-200">{result.classifier.suspicion_count}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Tier 2 signals:</span>{' '}
                    <span className="text-slate-200">{result.classifier.investigative_count}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Override:</span>{' '}
                    <Badge variant={result.classifier.override_applied ? 'warning' : 'success'}>
                      {result.classifier.override_applied ? 'YES' : 'NO'}
                    </Badge>
                  </div>
                </div>
              </div>
            )}

            {/* Rationale */}
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-300">Rationale</h3>
              <p className="text-xs text-slate-400 leading-relaxed">{result.rationale.summary}</p>
            </div>
          </div>
        )}
        {!decideMut.isPending && !decideMut.error && !result && selectedCase && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-300">Case Facts</h3>
            <EvidenceTable
              evidence={
                selectedCase.facts?.map((f) => ({ field: f.field_id, value: f.value })) ?? []
              }
            />
          </div>
        )}
      </Modal>
    </div>
  );
}
