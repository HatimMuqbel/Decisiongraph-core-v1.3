import { useState } from 'react';
import type { ReportViewModel } from '../../types';
import GovernedAlignmentCard from './GovernedAlignmentCard';
import TerminalConfidenceCard from './TerminalConfidenceCard';
import PolicyRegimeContext from './PolicyRegimeContext';
import InstitutionalPosture from './InstitutionalPosture';
import PrecedentCaseCard from './PrecedentCaseCard';
import DivergenceJustification from './DivergenceJustification';
import DriverCausalityPanel from './DriverCausalityPanel';

interface Props {
  report: ReportViewModel;
}

export default function PrecedentIntelligence({ report }: Props) {
  const pa = report.precedent_analysis;
  const ep = report.enhanced_precedent;
  const [showAll, setShowAll] = useState(false);

  if (!pa?.available) {
    return (
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Precedent Intelligence
        </h3>
        <p className="text-sm text-slate-500">
          {pa?.message ?? 'Precedent analysis unavailable for this case.'}
        </p>
      </div>
    );
  }

  // v3 data sources (prefer enhanced_precedent, fallback to precedent_analysis)
  const confidenceLevel = ep?.confidence_level ?? pa.confidence_level;
  const dimensions = ep?.confidence_dimensions ?? pa.confidence_dimensions ?? [];
  const bottleneck = ep?.confidence_bottleneck ?? pa.confidence_bottleneck;
  const hardRule = ep?.confidence_hard_rule ?? pa.confidence_hard_rule;
  const alignCount = ep?.governed_alignment_count ?? pa.governed_alignment_count ?? 0;
  const alignTotal = ep?.governed_alignment_total ?? pa.governed_alignment_total ?? 0;
  const cases = pa.sample_cases ?? [];
  const visibleCases = showAll ? cases : cases.slice(0, 5);
  const driverCausality = ep?.driver_causality;
  const divergence = ep?.divergence_justification;
  const regimeAnalysis = ep?.regime_analysis;
  const isV3 = !!confidenceLevel && dimensions.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Precedent Intelligence
        </h3>
        <span className="text-[10px] text-slate-600">
          {pa.scoring_version === 'v3' ? 'v3 Governed Model' : 'v2 Legacy'}
        </span>
      </div>

      {/* Row 1: Alignment + Confidence side by side */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <GovernedAlignmentCard
          count={alignCount}
          total={alignTotal}
          alignmentContext={ep?.alignment_context}
          opAligned={ep?.op_alignment_count}
          opTotal={ep?.op_alignment_total}
          regAligned={ep?.reg_alignment_count}
          regTotal={ep?.reg_alignment_total}
          combinedAligned={ep?.combined_alignment_count}
          regAllUndetermined={ep?.reg_alignment_all_undetermined}
        />
        {isV3 ? (
          <TerminalConfidenceCard
            level={confidenceLevel!}
            dimensions={dimensions}
            bottleneck={bottleneck}
            hardRule={hardRule}
            firstImpressionAlert={ep?.first_impression_alert}
            transferableCount={ep?.transferable_count}
            comparableCount={cases.length}
          />
        ) : (
          /* v2 fallback: flat confidence */
          <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Precedent Confidence
            </h4>
            <div className="text-3xl font-bold text-slate-200">
              {Math.round((pa.precedent_confidence ?? 0) * 100)}%
            </div>
            <div className="mt-3 grid grid-cols-3 gap-3 text-center text-xs">
              <div>
                <p className="text-slate-500">Supporting</p>
                <p className="text-lg font-bold text-emerald-400">{pa.supporting_precedents ?? 0}</p>
              </div>
              <div>
                <p className="text-slate-500">Contrary</p>
                <p className="text-lg font-bold text-red-400">{pa.contrary_precedents ?? 0}</p>
              </div>
              <div>
                <p className="text-slate-500">Neutral</p>
                <p className="text-lg font-bold text-slate-400">{pa.neutral_precedents ?? 0}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Row 1.5: Policy Regime Context (only when shifts detected) */}
      {regimeAnalysis && regimeAnalysis.shifts_detected?.length > 0 && (
        <PolicyRegimeContext regimeAnalysis={regimeAnalysis} />
      )}

      {/* Row 2: Institutional Posture */}
      <InstitutionalPosture
        patternSummary={ep?.pattern_summary}
        institutionalPosture={ep?.institutional_posture}
        regimeAnalysis={regimeAnalysis}
        postShiftGapStatement={ep?.post_shift_gap_statement}
        suspicionPosture={ep?.suspicion_posture}
      />

      {/* Row 3: Top Comparable Cases */}
      {cases.length > 0 && (
        <div>
          {(() => {
            const ntCount = cases.filter(c => c.non_transferable).length;
            const tCount = cases.length - ntCount;
            return (
              <div className="mb-2">
                <h4 className="text-xs font-semibold text-slate-400">
                  Top Comparable Cases ({cases.length})
                </h4>
                {ntCount > 0 && (
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Comparable: {cases.length} | Transferable: {tCount} | Non-Transferable: {ntCount}
                    {tCount < 3 && (
                      <span className="text-amber-400 ml-1">⚠ Effective precedent support is minimal.</span>
                    )}
                  </p>
                )}
              </div>
            );
          })()}
          <div className="space-y-2">
            {visibleCases.map((sc, i) => (
              <PrecedentCaseCard key={i} sc={sc} defaultOpen={i === 0} caseDisposition={report.governed_disposition} caseReporting={report.canonical_outcome?.reporting} />
            ))}
          </div>
          {cases.length > 5 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="mt-2 text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              {showAll ? 'Show top 5 only' : `Show all ${cases.length} cases`}
            </button>
          )}
        </div>
      )}

      {/* Row 4: Divergence Justification (conditional) */}
      {divergence && (
        <DivergenceJustification
          divergence={divergence}
          overrideStatement={ep?.override_statement}
        />
      )}

      {/* Driver Causality */}
      {driverCausality && (
        <DriverCausalityPanel
          sharedDrivers={driverCausality.shared_drivers ?? []}
          divergentDrivers={driverCausality.divergent_drivers ?? []}
        />
      )}

      {/* Non-Transferable Precedents */}
      {ep?.non_transferable_explanations && ep.non_transferable_explanations.length > 0 && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-amber-400">
            Non-Transferable Precedents ({ep.non_transferable_explanations.length})
          </h4>
          <div className="space-y-2">
            {ep.non_transferable_explanations.slice(0, 3).map((nt, i) => (
              <div key={i} className="rounded-lg bg-slate-800 p-3">
                <span className="font-mono text-xs text-slate-400">{nt.precedent_id}</span>
                {nt.reasons.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {nt.reasons.map((r, j) => (
                      <li key={j} className="text-[11px] text-amber-300/80">• {r}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
