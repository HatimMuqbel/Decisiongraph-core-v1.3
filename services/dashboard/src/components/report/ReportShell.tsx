import type { ReactNode } from 'react';
import type { ReportViewModel, ReportTier } from '../../types';
import TierBadge from './TierBadge';
import Badge, { dispositionVariant } from '../Badge';

interface ReportShellProps {
  report: ReportViewModel;
  currentTier: ReportTier;
  onChangeTier: (tier: ReportTier) => void;
  children: ReactNode;
}

export default function ReportShell({ report, currentTier, onChangeTier, children }: ReportShellProps) {
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

          {/* Right: Tier tabs */}
          <div className="flex-shrink-0">
            <TierBadge currentTier={currentTier} report={report} onChangeTier={onChangeTier} />
          </div>
        </div>
      </div>

      {/* Body content (tier-specific) */}
      {children}
    </div>
  );
}
