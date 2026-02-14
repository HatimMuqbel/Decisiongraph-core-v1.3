import type { ReactNode } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import { useReportJson, useReportPdf } from '../hooks/useApi';
import { Loading, ErrorMessage, Badge, StatsCard } from '../components';
import { dispositionVariant, confidenceVariant } from '../components/Badge';
import { getLabel } from '../components/EvidenceTable';
import {
  ReportShell,
  LinchpinStatement,
  RiskHeatmap,
  TypologyMap,
  NegativePathSearch,
  EvidenceGapTracker,
  VerbatimCitations,
  CausalChain,
  AuditMetadata,
  ReportEvidenceTable,
  PrecedentIntelligence,
  DecisionPathNarrative,
} from '../components/report';
import type { ReportTier, ReportViewModel } from '../types';
import { getMinimumTier } from '../types';
import { clsx } from 'clsx';

export default function ReportViewer() {
  const { decisionId } = useParams<{ decisionId: string }>();
  const [searchParams] = useSearchParams();
  const requestedTier = searchParams.get('tier');

  const {
    data: reportData,
    isLoading,
    error,
  } = useReportJson(decisionId ?? '');

  const report = reportData?.report;

  // Tier state — initialized from auto-escalation
  const [currentTier, setCurrentTier] = useState<ReportTier>(1);

  useEffect(() => {
    if (report) {
      const minTier = getMinimumTier(report);
      const urlTier = requestedTier ? (Number(requestedTier) as ReportTier) : null;
      const initialTier = urlTier && urlTier >= minTier ? urlTier : minTier;
      setCurrentTier(initialTier);
    }
  }, [report, requestedTier]);

  const handleChangeTier = useCallback(
    (tier: ReportTier) => {
      if (!report) return;
      const minTier = getMinimumTier(report);
      if (tier >= minTier) setCurrentTier(tier);
    },
    [report],
  );

  if (!decisionId) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-lg text-white">No decision ID provided.</p>
        <Link to="/" className="mt-4 text-sm text-emerald-400 hover:text-emerald-300">
          &larr; Back to Dashboard
        </Link>
      </div>
    );
  }

  if (isLoading) {
    return <Loading text="Loading compliance report…" />;
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Link to="/" className="text-xs text-white hover:text-white">
          &larr; Back to Dashboard
        </Link>
        <ErrorMessage error={error as Error} title="Failed to load report" />
        <p className="text-xs text-white">
          Decision ID: <span className="font-mono">{decisionId}</span>
        </p>
        <p className="text-xs text-white">
          The report may not be in the engine cache. Run a case first through the Demo Cases page, then visit this report.
        </p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="space-y-4">
        <ErrorMessage error={new Error('Report data not found.')} />
        <Link to="/" className="text-sm text-emerald-400 hover:text-emerald-300">
          &larr; Back to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className={clsx(
      'space-y-0',
      // Tier 3 uses lighter background for print readability
      currentTier === 3 && 'report-print-mode',
    )}>
      <ReportShell
        report={report}
        currentTier={currentTier}
        onChangeTier={handleChangeTier}
      >
        {/* ── TIER 1: Analyst View ─────────────────────────────── */}
        <Tier1Content report={report} />

        {/* ── TIER 2: Reviewer View ────────────────────────────── */}
        {currentTier >= 2 && <Tier2Content report={report} />}

        {/* ── TIER 3: Regulator View ───────────────────────────── */}
        {currentTier >= 3 && <Tier3Content report={report} />}
      </ReportShell>
    </div>
  );
}

// ── TIER 1 ──────────────────────────────────────────────────────────────────

function Tier1Content({ report }: { report: ReportViewModel }) {
  return (
    <div className="space-y-5">
      {/* 1. Linchpin Statement */}
      <LinchpinStatement report={report} />

      {/* 2. Decision Path (5-step visual flow) */}
      <DecisionPathNarrative report={report} />

      {/* 3. Risk Heatmap + Quick Decision side by side */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <RiskHeatmap report={report} />

        {/* Quick Decision Outcome */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white">
            Decision Outcome
          </h3>
          <div className="flex flex-col items-center gap-3 py-4">
            <Badge
              variant={dispositionVariant(report.verdict)}
              size="md"
              className="text-lg px-5 py-2"
            >
              {report.verdict}
            </Badge>
            {report.decision_confidence_score != null && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-white">Confidence:</span>
                <Badge variant={confidenceVariant((report.decision_confidence_score ?? 0) / 100)}>
                  {report.decision_confidence ?? `${report.decision_confidence_score}%`}
                </Badge>
              </div>
            )}
            <div className="flex flex-wrap justify-center gap-2 mt-2">
              {report.str_required && <Badge variant="danger" size="md">STR REQUIRED</Badge>}
              {report.regulatory_status && report.regulatory_status !== 'NO REPORT' && (
                <Badge variant="warning" size="md">{report.regulatory_status}</Badge>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Decision Conflict Alert */}
      {report.classification_outcome && report.classification_outcome !== report.engine_disposition && (
        <div className="rounded-xl border-2 border-amber-500/50 bg-amber-500/5 p-5">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-amber-400">
            ⚠ Decision Conflict
          </h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-[10px] text-white">Classifier</p>
              <Badge variant="danger">{report.classification_outcome?.replace(/_/g, ' ')}</Badge>
            </div>
            <div>
              <p className="text-[10px] text-white">Engine</p>
              <Badge variant="warning">{report.engine_disposition?.replace(/_/g, ' ')}</Badge>
            </div>
            <div>
              <p className="text-[10px] text-white">Governed</p>
              <Badge variant={dispositionVariant(report.governed_disposition)}>
                {report.governed_disposition?.replace(/_/g, ' ')}
              </Badge>
            </div>
          </div>
          {report.decision_conflict_alert?.resolution && (
            <p className="mt-3 text-xs text-amber-300/80">
              <span className="font-semibold">Resolution:</span> {report.decision_conflict_alert.resolution}
            </p>
          )}
        </div>
      )}

      {/* 3. Key Signals Summary (top 5) */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white">
          Key Signals
        </h3>
        {report.decision_drivers && report.decision_drivers.length > 0 ? (
          <ul className="space-y-2">
            {report.decision_drivers.slice(0, 5).map((d, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="mt-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-slate-700 text-[10px] font-bold text-slate-300">
                  {i + 1}
                </span>
                <span className="text-sm text-slate-300">{d}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="space-y-2">
            {report.tier1_signals?.slice(0, 5).map((s, i) => (
              <div key={i} className="flex items-start gap-2">
                <Badge variant="danger" className="flex-shrink-0">{s.code}</Badge>
                <span className="text-xs text-white">{s.detail}</span>
              </div>
            ))}
            {(report.tier1_signals?.length ?? 0) === 0 && (
              <p className="text-sm text-white">No suspicious signals detected.</p>
            )}
          </div>
        )}
      </div>

      {/* 4. Evidence Snapshot (top 5 critical fields) */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white">
          Evidence Snapshot
        </h3>
        <SnapshotTable report={report} />
      </div>

      {/* 5. One-Click Action Buttons */}
      {(() => {
        const blockApproval = !!(
          report.decision_integrity_alert ||
          report.investigation_state === 'COMPLIANCE REVIEW REQUIRED' ||
          (report.precedent_analysis?.contrary_precedents ?? 0) > (report.precedent_analysis?.supporting_precedents ?? 0)
        );
        return (
          <div className="flex flex-wrap gap-3">
            {blockApproval ? (
              <div className="flex-1 min-w-[140px] rounded-lg bg-red-600/20 border border-red-500/30 px-5 py-3 text-sm font-semibold text-red-400 flex items-center justify-center gap-2">
                <span>⚠</span> Compliance Review Required
              </div>
            ) : (
              <button
                className="flex-1 min-w-[140px] rounded-lg bg-emerald-600 px-5 py-3 text-sm font-semibold text-white hover:bg-emerald-500 transition-colors flex items-center justify-center gap-2"
                onClick={() => {/* TODO: wire to judgment submission */}}
              >
                <span>✅</span> Approve
              </button>
            )}
            <button
              className="flex-1 min-w-[140px] rounded-lg bg-amber-600 px-5 py-3 text-sm font-semibold text-white hover:bg-amber-500 transition-colors flex items-center justify-center gap-2"
              onClick={() => {/* TODO: wire to request info */}}
            >
              <span>ℹ️</span> Request Info
            </button>
            <button
              className="flex-1 min-w-[140px] rounded-lg bg-slate-700 px-5 py-3 text-sm font-semibold text-slate-100 hover:bg-slate-600 transition-colors flex items-center justify-center gap-2"
              onClick={() => {/* TODO: expand to reviewer */}}
            >
              <span>🔍</span> Expand to Reviewer View
            </button>
          </div>
        );
      })()}

      {/* 5. Governance Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatsCard
          label="Disposition"
          value={report.canonical_outcome?.disposition ?? report.verdict}
          sub={report.canonical_outcome?.disposition_basis}
        />
        <StatsCard
          label="Reporting"
          value={report.canonical_outcome?.reporting ?? '—'}
          sub={report.regulatory_obligation ? 'Obligation' : undefined}
        />
        <StatsCard
          label="Investigation"
          value={report.investigation_state ?? 'N/A'}
        />
        <StatsCard
          label="Defensibility"
          value={report.defensibility_check?.status ?? 'N/A'}
          sub={report.defensibility_check?.message}
        />
      </div>

      {/* 6. Precedent Intelligence Panel */}
      {report.precedent_analysis?.available && (
        <PrecedentIntelligence report={report} />
      )}
    </div>
  );
}

// ── TIER 2 ──────────────────────────────────────────────────────────────────

function Tier2Content({ report }: { report: ReportViewModel }) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['typology', 'negative', 'evidence-gap']));

  const toggle = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      next.has(section) ? next.delete(section) : next.add(section);
      return next;
    });
  };

  return (
    <div className="space-y-5 border-t border-slate-700/40 pt-5">
      <h2 className="text-sm font-bold uppercase tracking-wider text-amber-400">
        Reviewer View — Additional Analysis
      </h2>

      {/* Typology Map */}
      <CollapsibleSection
        id="typology"
        title="Typology Match Analysis"
        expanded={expandedSections.has('typology')}
        onToggle={toggle}
      >
        <TypologyMap report={report} />
      </CollapsibleSection>

      {/* Negative Path Search */}
      <CollapsibleSection
        id="negative"
        title="Negative Path Search"
        expanded={expandedSections.has('negative')}
        onToggle={toggle}
      >
        <NegativePathSearch report={report} />
      </CollapsibleSection>

      {/* Evidence Gap Tracker */}
      <CollapsibleSection
        id="evidence-gap"
        title="Evidence Gap Tracker"
        expanded={expandedSections.has('evidence-gap')}
        onToggle={toggle}
      >
        <EvidenceGapTracker report={report} />
      </CollapsibleSection>

      {/* Full Evidence Table */}
      <CollapsibleSection
        id="full-evidence"
        title="Full Evidence Table"
        expanded={expandedSections.has('full-evidence')}
        onToggle={toggle}
      >
        <ReportEvidenceTable report={report} />
      </CollapsibleSection>

      {/* Signal Details */}
      <CollapsibleSection
        id="signals"
        title="Signal Details"
        expanded={expandedSections.has('signals')}
        onToggle={toggle}
      >
        <SignalDetails report={report} />
      </CollapsibleSection>

      {/* Escalation Summary */}
      {report.escalation_summary && (
        <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white">
            Escalation Summary
          </h3>
          <p className="text-sm leading-relaxed text-slate-300">{report.escalation_summary}</p>
          {report.escalation_reasons && report.escalation_reasons.length > 0 && (
            <ul className="mt-2 space-y-1">
              {report.escalation_reasons.map((r, i) => (
                <li key={i} className="text-xs text-amber-400">• {r}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* EDD Recommendations */}
      {report.edd_recommendations && report.edd_recommendations.length > 0 && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-amber-400">
            EDD Recommendations
          </h3>
          <ul className="space-y-2">
            {report.edd_recommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <span className="text-amber-400">→</span>
                <div>
                  <span className="text-slate-300">{rec.action}</span>
                  {rec.reference && (
                    <span className="ml-2 text-xs text-white">({rec.reference})</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Precedent Technical Detail — collapsible stats for auditors */}
      <CollapsibleSection
        id="precedent-detail"
        title="Precedent Technical Detail"
        expanded={expandedSections.has('precedent-detail')}
        onToggle={toggle}
      >
        <PrecedentTechnicalDetail report={report} />
      </CollapsibleSection>
    </div>
  );
}

// ── TIER 3 ──────────────────────────────────────────────────────────────────

function Tier3Content({ report }: { report: ReportViewModel }) {
  const pdfMutation = useReportPdf();

  const handlePdfExport = () => {
    pdfMutation.mutate(report.decision_id, {
      onSuccess: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `compliance_report_${report.case_id}_${report.decision_id_short}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      },
    });
  };

  return (
    <div className="space-y-5 border-t border-slate-700/40 pt-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold uppercase tracking-wider text-red-400">
          Regulator View — Full Audit Package
        </h2>
        <button
          onClick={handlePdfExport}
          disabled={pdfMutation.isPending}
          className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 transition-colors disabled:opacity-50"
        >
          {pdfMutation.isPending ? (
            <span className="animate-spin">⏳</span>
          ) : (
            <span>📄</span>
          )}
          Export PDF
        </button>
      </div>

      {/* Verbatim Citations */}
      <VerbatimCitations report={report} />

      {/* Causal Chain */}
      <CausalChain report={report} />

      {/* Audit Metadata */}
      <AuditMetadata report={report} />

      {/* Rationale */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white">
          Full Rationale
        </h3>
        <p className="text-sm leading-relaxed text-slate-300">{report.summary}</p>
        {report.classification_reason && (
          <div className="mt-3 rounded-lg bg-slate-900 p-3">
            <p className="text-xs text-white">Classification Reason</p>
            <p className="mt-1 text-xs text-slate-300">{report.classification_reason}</p>
          </div>
        )}
      </div>

      {/* Export options */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-white font-medium">Export Options</p>
            <p className="text-[10px] text-white mt-0.5">
              All three tiers are included in exported documents. Use
              <kbd className="mx-1 rounded bg-slate-700 px-1.5 py-0.5 text-[10px]">Ctrl+P</kbd>
              for browser print, or click Export PDF for a formatted compliance document.
            </p>
          </div>
          <button
            onClick={handlePdfExport}
            disabled={pdfMutation.isPending}
            className="flex items-center gap-2 rounded-lg bg-slate-700 px-4 py-2 text-xs font-medium text-slate-200 hover:bg-slate-600 transition-colors disabled:opacity-50"
          >
            📄 Download PDF
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function SnapshotTable({ report }: { report: ReportViewModel }) {
  // Show the most critical evidence items with proper registry labels
  const critical = [
    ...(report.risk_factors ?? []).map((rf) => ({ field: rf.field, value: rf.value })),
    ...(report.transaction_facts ?? []).slice(0, 5),
  ];
  const unique = critical.filter(
    (item, i, arr) => arr.findIndex((x) => x.field === item.field) === i,
  ).slice(0, 6);

  if (unique.length === 0) {
    return <p className="text-sm text-white">No evidence snapshot available.</p>;
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-slate-700 text-left">
          <th className="px-3 py-1.5 text-[10px] font-medium uppercase text-white">Field</th>
          <th className="px-3 py-1.5 text-[10px] font-medium uppercase text-white">Value</th>
        </tr>
      </thead>
      <tbody>
        {unique.map((item, i) => (
          <tr key={i} className="border-b border-slate-800/50">
            <td className="px-3 py-1.5 text-xs text-white">{getLabel(item.field)}</td>
            <td className="px-3 py-1.5 text-xs text-slate-200">{String(item.value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SignalDetails({ report }: { report: ReportViewModel }) {
  const tier1 = report.tier1_signals ?? [];
  const tier2 = report.tier2_signals ?? [];

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-white">
        All Signals ({tier1.length} Tier 1, {tier2.length} Tier 2)
      </h3>

      {tier1.length > 0 && (
        <div className="mb-4">
          <h4 className="mb-2 text-xs font-medium text-red-400">
            Tier 1 — Suspicion Indicators (DISQUALIFIER / MANDATORY_ESCALATION)
          </h4>
          <div className="space-y-1">
            {tier1.map((s, i) => (
              <div key={i} className="flex items-start gap-2 rounded-lg bg-red-500/5 px-3 py-2 text-xs">
                <Badge variant="danger" className="flex-shrink-0">{s.code}</Badge>
                <div className="min-w-0">
                  <p className="text-slate-300">{s.detail}</p>
                  {s.source && <p className="text-[10px] text-white">Source: {s.source}</p>}
                  {s.field && <p className="text-[10px] text-white">Field: {s.field}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tier2.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-medium text-amber-400">
            Tier 2 — Investigative Signals (EDD Triggers)
          </h4>
          <div className="space-y-1">
            {tier2.map((s, i) => (
              <div key={i} className="flex items-start gap-2 rounded-lg bg-amber-500/5 px-3 py-2 text-xs">
                <Badge variant="warning" className="flex-shrink-0">{s.code}</Badge>
                <div className="min-w-0">
                  <p className="text-slate-300">{s.detail}</p>
                  {s.source && <p className="text-[10px] text-white">Source: {s.source}</p>}
                  {s.field && <p className="text-[10px] text-white">Field: {s.field}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tier1.length === 0 && tier2.length === 0 && (
        <p className="text-sm text-white">No signals detected for this case.</p>
      )}
    </div>
  );
}

function PrecedentTechnicalDetail({ report }: { report: ReportViewModel }) {
  const pa = report.precedent_analysis;

  const totalPrecedents = (pa?.supporting_precedents ?? 0) + (pa?.contrary_precedents ?? 0) + (pa?.neutral_precedents ?? 0);
  const hasData = totalPrecedents > 0 || (pa?.sample_size ?? 0) > 0;

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-white">
        Precedent Analysis
      </h3>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <div className="text-center">
          <p className="text-xs text-white">Confidence</p>
          <p className="text-lg font-bold text-slate-100">
            {Math.round((pa?.precedent_confidence ?? 0) * 100)}%
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-white">Supporting</p>
          <p className="text-lg font-bold text-emerald-400">{pa?.supporting_precedents ?? 0}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-white">Contrary</p>
          <p className="text-lg font-bold text-red-400">{pa?.contrary_precedents ?? 0}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-white">Neutral</p>
          <p className="text-lg font-bold text-white">{pa?.neutral_precedents ?? 0}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-white">Pool</p>
          <p className="text-lg font-bold text-white">{pa?.sample_size ?? 0}</p>
        </div>
      </div>

      {/* Message when no precedent data */}
      {!hasData && (
        <div className="mt-4 rounded-lg bg-slate-900 p-3 text-center">
          <p className="text-xs text-white">
            {pa?.message || 'No comparable precedents found in the seed corpus for this scenario. Run more cases to build the precedent pool.'}
          </p>
        </div>
      )}

      {/* Sample cases */}
      {pa?.sample_cases && pa.sample_cases.length > 0 && (
        <div className="mt-4">
          <h4 className="mb-2 text-xs font-semibold text-white">
            Sample Precedents ({pa.sample_cases.length})
          </h4>
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {pa.sample_cases.slice(0, 10).map((sc, i) => (
              <div
                key={i}
                className="flex items-center gap-3 rounded-lg bg-slate-900 px-3 py-2 text-xs"
              >
                <Badge variant={dispositionVariant(sc.outcome_normalized || sc.disposition)}>
                  {sc.outcome_label || sc.disposition}
                </Badge>
                <span className="font-mono text-white">{sc.precedent_id}</span>
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
                <span className="text-white">{sc.similarity_pct}% similar</span>
                {sc.appealed && <Badge variant="warning">APPEALED</Badge>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Caution precedents */}
      {pa?.caution_precedents && pa.caution_precedents.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
          <h4 className="mb-2 text-xs font-medium text-amber-400">
            Caution Precedents ({pa.caution_precedents.length})
          </h4>
          <div className="space-y-1">
            {pa.caution_precedents.map((cp, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="font-mono text-white">{cp.precedent_id}</span>
                <Badge variant="warning">{cp.classification}</Badge>
                <span className="text-white">{cp.outcome} / {cp.disposition}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Appeal statistics */}
      {pa?.appeal_statistics && pa.appeal_statistics.total_appealed > 0 && (
        <div className="mt-4 grid grid-cols-4 gap-3 text-center">
          <div>
            <p className="text-[10px] text-white">Appealed</p>
            <p className="text-sm font-bold text-slate-200">{pa.appeal_statistics.total_appealed}</p>
          </div>
          <div>
            <p className="text-[10px] text-white">Upheld</p>
            <p className="text-sm font-bold text-emerald-400">{pa.appeal_statistics.upheld}</p>
          </div>
          <div>
            <p className="text-[10px] text-white">Overturned</p>
            <p className="text-sm font-bold text-red-400">{pa.appeal_statistics.overturned}</p>
          </div>
          <div>
            <p className="text-[10px] text-white">Upheld Rate</p>
            <p className="text-sm font-bold text-slate-200">
              {Math.round((pa.appeal_statistics.upheld_rate ?? 0) * 100)}%
            </p>
          </div>
        </div>
      )}

      {pa?.similarity_summary && (
        <p className="mt-3 text-xs text-white">{pa.similarity_summary}</p>
      )}
    </div>
  );
}

function CollapsibleSection({
  id,
  title,
  expanded,
  onToggle,
  children,
}: {
  id: string;
  title: string;
  expanded: boolean;
  onToggle: (id: string) => void;
  children: ReactNode;
}) {
  return (
    <div>
      <button
        onClick={() => onToggle(id)}
        className="mb-2 flex w-full items-center gap-2 text-left text-xs font-semibold uppercase tracking-wider text-white hover:text-slate-200 transition-colors"
      >
        <span className={clsx('transition-transform', expanded && 'rotate-90')}>▶</span>
        {title}
      </button>
      {expanded && children}
    </div>
  );
}
