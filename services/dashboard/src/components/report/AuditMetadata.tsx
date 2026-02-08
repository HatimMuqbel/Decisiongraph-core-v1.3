import type { ReportViewModel } from '../../types';

interface AuditMetadataProps {
  report: ReportViewModel;
}

/**
 * Full technical audit trail for Tier 3 (Regulator View).
 * Shows timestamps, hashes, versions, SLA timeline, corrections.
 */
export default function AuditMetadata({ report }: AuditMetadataProps) {
  const sla = report.sla_timeline;
  const integrity = report.decision_integrity_alert;
  const deviation = report.precedent_deviation_alert;
  const corrections = report.corrections_applied;

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Audit Metadata
      </h3>
      <p className="mb-4 text-[10px] text-slate-600">
        Full technical provenance for regulatory examination
      </p>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Decision Provenance */}
        <div className="rounded-lg bg-slate-900 p-4">
          <h4 className="mb-3 text-xs font-medium text-slate-400">Decision Provenance</h4>
          <div className="space-y-2 text-xs">
            <Row label="Decision ID" value={report.decision_id} mono />
            <Row label="Decision ID (Short)" value={report.decision_id_short} mono />
            <Row label="Case ID" value={report.case_id} mono />
            <Row label="Input Hash" value={report.input_hash} mono />
            <Row label="Policy Hash" value={report.policy_hash} mono />
            <Row label="Timestamp" value={report.timestamp} />
            <Row label="Jurisdiction" value={report.jurisdiction} />
          </div>
        </div>

        {/* System Versions */}
        <div className="rounded-lg bg-slate-900 p-4">
          <h4 className="mb-3 text-xs font-medium text-slate-400">System Versions</h4>
          <div className="space-y-2 text-xs">
            <Row label="Engine Version" value={report.engine_version} />
            <Row label="Policy Version" value={report.policy_version} />
            <Row label="Report Schema" value={report.report_schema_version} />
            <Row label="Narrative Compiler" value={report.narrative_compiler_version} />
            <Row label="Classifier Version" value={report.classifier_version} />
            <Row label="Domain" value={report.domain} />
            <Row label="Source Type" value={report.source_type} />
            {report.scenario_code && <Row label="Scenario Code" value={report.scenario_code} />}
          </div>
        </div>

        {/* SLA Timeline */}
        {sla && (
          <div className="rounded-lg bg-slate-900 p-4">
            <h4 className="mb-3 text-xs font-medium text-slate-400">SLA Timeline</h4>
            <div className="space-y-2 text-xs">
              <Row label="Case Created" value={sla.case_created} />
              <Row label="EDD Deadline" value={sla.edd_deadline} />
              <Row label="Final Disposition Due" value={sla.final_disposition_due} />
              <Row label="STR Filing Window" value={sla.str_filing_window} />
            </div>
          </div>
        )}

        {/* Disposition Reconciliation */}
        <div className="rounded-lg bg-slate-900 p-4">
          <h4 className="mb-3 text-xs font-medium text-slate-400">Disposition Reconciliation</h4>
          <div className="space-y-2 text-xs">
            <Row label="Engine Disposition" value={report.engine_disposition} />
            <Row label="Governed Disposition" value={report.governed_disposition} />
            <Row label="Classification Outcome" value={report.classification_outcome} />
            <Row label="Classifier Sovereign" value={report.classifier_is_sovereign ? 'Yes' : 'No'} />
            <Row label="Suspicion Count" value={String(report.suspicion_count ?? 0)} />
            <Row label="Investigative Count" value={String(report.investigative_count ?? 0)} />
          </div>
        </div>

        {/* Precedent Metrics */}
        <div className="rounded-lg bg-slate-900 p-4">
          <h4 className="mb-3 text-xs font-medium text-slate-400">Precedent Metrics</h4>
          <div className="space-y-2 text-xs">
            <Row label="Alignment" value={`${report.precedent_alignment_pct ?? 0}%`} />
            <Row label="Match Rate" value={`${report.precedent_match_rate ?? 0}%`} />
            <Row label="Scored Precedents" value={String(report.scored_precedent_count ?? 0)} />
            <Row label="Comparable Pool" value={String(report.total_comparable_pool ?? 0)} />
            <Row label="Consistency Alert" value={report.precedent_consistency_alert ? 'Yes' : 'No'} />
            {report.precedent_consistency_detail && (
              <Row label="Consistency Detail" value={report.precedent_consistency_detail} />
            )}
          </div>
        </div>

        {/* Report Sections */}
        {report.report_sections && report.report_sections.length > 0 && (
          <div className="rounded-lg bg-slate-900 p-4">
            <h4 className="mb-3 text-xs font-medium text-slate-400">
              Report Sections ({report.report_sections.length})
            </h4>
            <ol className="list-decimal list-inside space-y-0.5 text-xs text-slate-400">
              {report.report_sections.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {/* Alerts */}
      {(integrity || deviation) && (
        <div className="mt-4 space-y-2">
          {integrity && (
            <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3">
              <h4 className="text-xs font-semibold text-red-400">
                Decision Integrity Alert — {integrity.severity}
              </h4>
              <p className="mt-1 text-xs text-red-300">{integrity.message}</p>
              <div className="mt-2 flex gap-3 text-[10px] text-red-400/70">
                <span>Type: {integrity.type}</span>
                <span>Original: {integrity.original_verdict}</span>
                <span>Classifier: {integrity.classifier_outcome}</span>
              </div>
            </div>
          )}
          {deviation && (
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3">
              <h4 className="text-xs font-semibold text-amber-400">
                Precedent Deviation Alert
              </h4>
              <p className="mt-1 text-xs text-amber-300">{deviation.message}</p>
            </div>
          )}
        </div>
      )}

      {/* Corrections */}
      {corrections && Object.keys(corrections).length > 0 && (
        <div className="mt-4 rounded-lg bg-slate-900 p-4">
          <h4 className="mb-2 text-xs font-medium text-slate-400">Corrections Applied</h4>
          <pre className="text-[10px] text-slate-500 overflow-x-auto">
            {JSON.stringify(corrections, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <span className="text-slate-500 flex-shrink-0">{label}</span>
      <span className={`text-right text-slate-300 break-all ${mono ? 'font-mono text-[10px]' : ''}`}>
        {value || '—'}
      </span>
    </div>
  );
}
