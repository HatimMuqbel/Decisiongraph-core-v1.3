import type { ReactNode } from 'react';
import type { ReportViewModel, ReportTier } from '../../types';
import TierBadge from './TierBadge';
import Badge, { dispositionVariant } from '../Badge';
import { useReportHtml, useReportPdf } from '../../hooks/useApi';

interface ReportShellProps {
  report: ReportViewModel;
  currentTier: ReportTier;
  onChangeTier: (tier: ReportTier) => void;
  children: ReactNode;
}

export default function ReportShell({ report, currentTier, onChangeTier, children }: ReportShellProps) {
  const htmlMutation = useReportHtml();
  const pdfMutation = useReportPdf();

  const handleHtmlExport = () => {
    htmlMutation.mutate(report.decision_id, {
      onSuccess: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `compliance_report_${report.case_id}_${report.decision_id_short}.html`;
        a.click();
        URL.revokeObjectURL(url);
      },
    });
  };

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
    <div className="space-y-4">
      {/* Header Bar */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          {/* Left: ID, case, timestamp */}
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-slate-100">Compliance Report</h1>
              <Badge variant={dispositionVariant(report.verdict)} size="md">
                {report.verdict}
              </Badge>
              {report.str_required && (
                <Badge variant="danger" size="md">STR REQUIRED</Badge>
              )}
            </div>

            <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-white">
              <span>
                <span className="text-white">Decision:</span>{' '}
                <span className="font-mono text-slate-300">{report.decision_id_short || report.decision_id?.slice(0, 16)}</span>
              </span>
              <span>
                <span className="text-white">Case:</span>{' '}
                <span className="font-mono text-slate-300">{report.case_id}</span>
              </span>
              <span>
                <span className="text-white">Timestamp:</span>{' '}
                <span className="text-slate-300">{report.timestamp}</span>
              </span>
              <span>
                <span className="text-white">Pack:</span>{' '}
                <span className="text-slate-300">v{report.policy_version}</span>
              </span>
            </div>

            {/* Integrity hashes */}
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-[10px] text-white">
              <span>
                Input Hash: <span className="font-mono">{report.input_hash_short || report.input_hash?.slice(0, 16)}</span>
              </span>
              <span>
                Policy Hash: <span className="font-mono">{report.policy_hash_short || report.policy_hash?.slice(0, 16)}</span>
              </span>
              {report.jurisdiction && <span>Jurisdiction: {report.jurisdiction}</span>}
            </div>
          </div>

          {/* Right: Tier tabs + Export buttons */}
          <div className="flex flex-col items-end gap-3 flex-shrink-0">
            <TierBadge currentTier={currentTier} report={report} onChangeTier={onChangeTier} />
            <div className="flex items-center gap-2">
              <button
                onClick={handleHtmlExport}
                disabled={htmlMutation.isPending}
                className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 transition-colors disabled:opacity-50"
              >
                {htmlMutation.isPending ? '...' : 'Export HTML'}
              </button>
              <button
                onClick={handlePdfExport}
                disabled={pdfMutation.isPending}
                className="flex items-center gap-1.5 rounded-lg bg-slate-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-500 transition-colors disabled:opacity-50"
              >
                {pdfMutation.isPending ? '...' : 'Export PDF'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Body content (tier-specific) */}
      {children}
    </div>
  );
}
