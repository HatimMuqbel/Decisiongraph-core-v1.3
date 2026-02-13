import { useParams, Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useDemoCase, useDecide, useReportJson } from '../hooks/useApi';
import { useDomain } from '../hooks/useDomain';
import {
  Loading,
  ErrorMessage,
  Badge,
  EvidenceTable,
  StatsCard,
  dispositionVariant,
} from '../components';
import { PrecedentIntelligence } from '../components/report';
import { api } from '../api/client';

export default function DecisionViewer() {
  const { caseId: id } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const { isInsurance } = useDomain();
  const { data: demoCase, isLoading: loadingCase, error: caseError } = useDemoCase(id ?? '');
  const decideMut = useDecide();
  const [decisionId, setDecisionId] = useState<string | null>(null);
  // For insurance, fetch report directly by case ID; for banking, fetch after /decide
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [insuranceReport, setInsuranceReport] = useState<any>(null);
  const [insuranceRunning, setInsuranceRunning] = useState(false);
  const [insuranceError, setInsuranceError] = useState<Error | null>(null);
  const { data: report } = useReportJson(decisionId ?? '');

  if (!id) return <p className="text-white">No case ID provided.</p>;
  if (loadingCase) return <Loading />;
  if (caseError) return <ErrorMessage error={caseError as Error} />;
  if (!demoCase) return <ErrorMessage error={new Error('Case not found')} />;

  async function handleRunInsurance() {
    if (!id) return;
    setInsuranceRunning(true);
    setInsuranceError(null);
    try {
      const data = await api.reportJson(id);
      setInsuranceReport(data.report);
      setDecisionId(id);
    } catch (e) {
      setInsuranceError(e as Error);
    } finally {
      setInsuranceRunning(false);
    }
  }

  async function handleRunBanking() {
    if (!demoCase) return;
    try {
      const pack = await decideMut.mutateAsync({
        case_id: demoCase.id,
        facts: demoCase.facts?.map((f) => ({
          field: f.field_id,
          value: f.value,
          label: f.label,
        })) ?? [],
      });
      setDecisionId(pack.meta.decision_id);
    } catch {
      // handled by mutation state
    }
  }

  const handleRun = isInsurance ? handleRunInsurance : handleRunBanking;
  const isRunning = isInsurance ? insuranceRunning : decideMut.isPending;
  const runError = isInsurance ? insuranceError : (decideMut.error as Error | null);

  const pack = decideMut.data;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const vm: any = isInsurance ? insuranceReport : report?.report;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link to="/cases" className="text-xs text-white hover:text-white">
            &larr; Back to Demo Cases
          </Link>
          <h1 className="mt-1 text-2xl font-bold text-slate-100">{demoCase.name}</h1>
          <p className="mt-1 text-sm text-white">{demoCase.description}</p>
        </div>
        <button
          onClick={handleRun}
          disabled={isRunning}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 transition"
        >
          {isRunning ? 'Running...' : 'Run Through Engine'}
        </button>
      </div>

      {/* View Full Report link */}
      {decisionId && (
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(`/reports/${decisionId}`)}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition"
          >
            View Full Report &rarr;
          </button>
          <span className="text-xs text-white">
            Decision: <span className="font-mono">{(decisionId ?? '').slice(0, 24)}</span>
          </span>
        </div>
      )}

      {runError && <ErrorMessage error={runError} />}

      {/* Case Facts */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-white">
          Input Facts ({demoCase.facts?.length ?? 0} fields)
        </h2>
        <EvidenceTable
          evidence={demoCase.facts?.map((f) => ({ field: f.field_id, value: f.value })) ?? []}
        />
      </div>

      {/* Insurance Report Result */}
      {isInsurance && vm && (
        <div className="space-y-5">
          {/* Verdict Stats */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatsCard label="Verdict" value={vm.verdict ?? 'N/A'} />
            <StatsCard label="Action" value={vm.action ?? 'N/A'} />
            <StatsCard label="Confidence" value={vm.decision_confidence ?? 'N/A'} />
            <StatsCard label="Comparable Cases" value={vm.scored_precedent_count ?? 0} />
          </div>

          {/* Disposition */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-white">
              Decision Outcome
            </h2>
            <div className="flex items-center gap-3">
              <Badge variant={dispositionVariant(vm.verdict ?? '')} size="md">
                {vm.action ?? vm.verdict ?? ''}
              </Badge>
              <span className="text-sm text-slate-300">{vm.decision_explainer ?? ''}</span>
            </div>
          </div>

          {/* Precedent Metrics */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-white">
              Precedent Analysis
            </h2>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
              <div>
                <p className="text-xs text-white">Alignment</p>
                <p className="text-lg font-bold text-slate-100">{vm.precedent_alignment_pct ?? 0}%</p>
              </div>
              <div>
                <p className="text-xs text-white">Match Rate</p>
                <p className="text-lg font-bold text-slate-100">{vm.precedent_match_rate ?? 0}%</p>
              </div>
              <div>
                <p className="text-xs text-white">Supporting</p>
                <p className="text-lg font-bold text-emerald-400">{vm.precedent_analysis?.supporting_precedents ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-white">Contrary</p>
                <p className="text-lg font-bold text-red-400">{vm.precedent_analysis?.contrary_precedents ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-white">Neutral</p>
                <p className="text-lg font-bold text-white">{vm.precedent_analysis?.neutral_precedents ?? 0}</p>
              </div>
            </div>
          </div>

          {/* Escalation */}
          {vm.escalation_summary && vm.escalation_summary !== 'No escalation factors' && (
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
              <h2 className="mb-2 text-sm font-semibold text-amber-400">Escalation Factors</h2>
              <p className="text-sm text-slate-300">{vm.escalation_summary}</p>
            </div>
          )}

          {/* Precedent Intelligence — full v3 panel */}
          {vm.precedent_analysis && <PrecedentIntelligence report={vm} />}
        </div>
      )}

      {/* Banking Decision Result */}
      {!isInsurance && pack && (
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
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-white">
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
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-white">
              Decision Path
            </h2>
            <p className="font-mono text-xs text-slate-300">
              {pack.evaluation_trace.decision_path || 'N/A'}
            </p>
          </div>

          {/* Rules Fired */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-white">
              Rules Fired
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase text-white">Code</th>
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase text-white">Result</th>
                    <th className="px-3 py-2 text-left text-xs font-medium uppercase text-white">Reason</th>
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
                      <td className="px-3 py-2 text-xs text-white">{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Evidence Used */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-white">
              Evidence Used (Registry Labels)
            </h2>
            <EvidenceTable evidence={pack.evaluation_trace.evidence_used} />
          </div>

          {/* Precedent Intelligence — uses report JSON when available */}
          {report?.report?.precedent_analysis?.available ? (
            <PrecedentIntelligence report={report.report} />
          ) : pack.precedent_analysis?.available ? (
            <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-white">
                Precedent Analysis
              </h2>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <p className="text-xs text-white">Confidence</p>
                  <p className="text-lg font-bold text-slate-100">
                    {pack.precedent_analysis.confidence_level ?? `${Math.round((pack.precedent_analysis.precedent_confidence ?? 0) * 100)}%`}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-white">Supporting</p>
                  <p className="text-lg font-bold text-emerald-400">
                    {pack.precedent_analysis.supporting_precedents}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-white">Contrary</p>
                  <p className="text-lg font-bold text-red-400">
                    {pack.precedent_analysis.contrary_precedents}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-white">Neutral</p>
                  <p className="text-lg font-bold text-white">
                    {pack.precedent_analysis.neutral_precedents}
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          {/* Rationale */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-white">
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
