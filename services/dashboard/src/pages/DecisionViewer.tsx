import { useParams, Link } from 'react-router-dom';
import { useState } from 'react';
import { useDemoCase, useDecide, useReportJson } from '../hooks/useApi';
import {
  Loading,
  ErrorMessage,
  Badge,
  EvidenceTable,
  StatsCard,
  dispositionVariant,
  confidenceVariant,
} from '../components';

export default function DecisionViewer() {
  const { id } = useParams<{ id: string }>();
  const { data: demoCase, isLoading: loadingCase, error: caseError } = useDemoCase(id ?? '');
  const decideMut = useDecide();
  const [decisionId, setDecisionId] = useState<string | null>(null);
  const { data: report } = useReportJson(decisionId ?? '');

  if (!id) return <p className="text-slate-400">No case ID provided.</p>;
  if (loadingCase) return <Loading />;
  if (caseError) return <ErrorMessage error={caseError as Error} />;
  if (!demoCase) return <ErrorMessage error={new Error('Case not found')} />;

  async function handleRun() {
    if (!demoCase) return;
    const factsObj: Record<string, unknown> = {};
    demoCase.facts?.forEach((f) => {
      factsObj[f.field_id] = f.value;
    });
    try {
      const pack = await decideMut.mutateAsync({
        case_id: demoCase.id,
        ...factsObj,
        customer: factsObj,
        transaction: factsObj,
      });
      setDecisionId(pack.meta.decision_id);
    } catch {
      // handled by mutation state
    }
  }

  const pack = decideMut.data;
  const vm = report?.report;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link to="/cases" className="text-xs text-slate-500 hover:text-slate-400">
            &larr; Back to Demo Cases
          </Link>
          <h1 className="mt-1 text-2xl font-bold text-slate-100">{demoCase.name}</h1>
          <p className="mt-1 text-sm text-slate-400">{demoCase.description}</p>
        </div>
        <button
          onClick={handleRun}
          disabled={decideMut.isPending}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 transition"
        >
          {decideMut.isPending ? 'Running…' : 'Run Through Engine'}
        </button>
      </div>

      {decideMut.error && <ErrorMessage error={decideMut.error as Error} />}

      {/* Case Facts */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Input Facts ({demoCase.facts?.length ?? 0} fields)
        </h2>
        <EvidenceTable
          evidence={demoCase.facts?.map((f) => ({ field: f.field_id, value: f.value })) ?? []}
        />
      </div>

      {/* Decision Result */}
      {pack && (
        <div className="space-y-5">
          {/* Verdict Stats */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatsCard
              label="Verdict"
              value={pack.decision.verdict}
            />
            <StatsCard
              label="Action"
              value={pack.decision.action || 'N/A'}
            />
            <StatsCard
              label="Tier 1 Signals"
              value={pack.classifier?.suspicion_count ?? 0}
            />
            <StatsCard
              label="Tier 2 Signals"
              value={pack.classifier?.investigative_count ?? 0}
            />
          </div>

          {/* Disposition */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Decision Outcome
            </h2>
            <div className="flex items-center gap-3">
              <Badge variant={dispositionVariant(pack.decision.verdict)} size="md">
                {pack.decision.verdict}
              </Badge>
              {pack.decision.str_required && (
                <Badge variant="danger" size="md">STR REQUIRED</Badge>
              )}
              {pack.decision.classifier_override && (
                <Badge variant="warning" size="md">CLASSIFIER OVERRIDE</Badge>
              )}
            </div>
          </div>

          {/* Elimination Trace */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Decision Path
            </h2>
            <p className="font-mono text-xs text-slate-300">
              {pack.evaluation_trace.decision_path || 'N/A'}
            </p>
          </div>

          {/* Rules Fired */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Rules Fired
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-400">Code</th>
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-400">Result</th>
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase text-slate-400">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {pack.evaluation_trace.rules_fired.map((r, i) => (
                    <tr key={i} className="border-b border-slate-800">
                      <td className="px-3 py-2 font-mono text-xs text-slate-300">{r.code}</td>
                      <td className="px-3 py-2">
                        <Badge variant={r.result === 'TRIGGERED' ? 'danger' : 'success'}>
                          {r.result}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-400">{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Evidence Used */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Evidence Used (Registry Labels)
            </h2>
            <EvidenceTable evidence={pack.evaluation_trace.evidence_used} />
          </div>

          {/* Precedent Analysis */}
          {pack.precedent_analysis?.available && (
            <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
                Precedent Analysis
              </h2>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <p className="text-xs text-slate-500">Confidence</p>
                  <p className="text-lg font-bold text-slate-100">
                    {Math.round((pack.precedent_analysis.precedent_confidence ?? 0) * 100)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Supporting</p>
                  <p className="text-lg font-bold text-emerald-400">
                    {pack.precedent_analysis.supporting_precedents}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Contrary</p>
                  <p className="text-lg font-bold text-red-400">
                    {pack.precedent_analysis.contrary_precedents}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Neutral</p>
                  <p className="text-lg font-bold text-slate-400">
                    {pack.precedent_analysis.neutral_precedents}
                  </p>
                </div>
              </div>

              {/* Sample cases */}
              {pack.precedent_analysis.sample_cases?.length > 0 && (
                <div className="mt-4">
                  <h3 className="mb-2 text-xs font-semibold text-slate-400">Sample Precedents</h3>
                  <div className="space-y-2">
                    {pack.precedent_analysis.sample_cases.slice(0, 5).map((sc, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-3 rounded-lg bg-slate-900 px-3 py-2"
                      >
                        <Badge variant={dispositionVariant(sc.outcome_normalized)}>
                          {sc.outcome_label}
                        </Badge>
                        <span className="font-mono text-xs text-slate-400">{sc.precedent_id}</span>
                        <Badge
                          variant={
                            sc.classification === 'supporting'
                              ? 'success'
                              : sc.classification === 'contrary'
                              ? 'danger'
                              : 'neutral'
                          }
                        >
                          {sc.classification}
                        </Badge>
                        <span className="text-xs text-slate-500">{sc.similarity_pct}% similar</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Rationale */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Rationale
            </h2>
            <p className="text-sm text-slate-300 leading-relaxed">{pack.rationale.summary}</p>
            {pack.rationale.str_rationale && (
              <div className="mt-3 rounded-lg border border-red-500/20 bg-red-500/10 p-3">
                <p className="text-xs font-medium text-red-400">STR Rationale</p>
                <p className="mt-1 text-xs text-red-300">{pack.rationale.str_rationale}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
