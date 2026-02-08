import Badge, { changeTypeVariant, dispositionVariant } from './Badge';
import type { PolicyShiftSummary } from '../types';

interface PolicyShiftCardProps {
  shift: PolicyShiftSummary;
  onClick?: () => void;
}

export default function PolicyShiftCard({ shift, onClick }: PolicyShiftCardProps) {
  return (
    <div
      onClick={onClick}
      className="group cursor-pointer rounded-xl border border-slate-700/60 bg-slate-800 p-5 transition-all hover:border-slate-600 hover:shadow-lg"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-semibold text-slate-100 group-hover:text-emerald-400 transition-colors">
            {shift.name}
          </h3>
          <p className="mt-1 text-sm text-slate-400">{shift.description}</p>
        </div>
        <Badge variant={changeTypeVariant(shift.primary_change)} size="md">
          {shift.primary_change.replace('_', ' ')}
        </Badge>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-4">
        <div>
          <p className="text-xs font-medium uppercase text-slate-500">Cases Affected</p>
          <p className="mt-0.5 text-lg font-bold text-slate-100">{shift.cases_affected}</p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase text-slate-500">Impact</p>
          <p className="mt-0.5 text-lg font-bold text-amber-400">{shift.pct_affected}%</p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase text-slate-500">Total Analyzed</p>
          <p className="mt-0.5 text-lg font-bold text-slate-100">{shift.total_cases_analyzed}</p>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <span className="text-xs text-slate-500">Citation:</span>
        <span className="text-xs text-slate-400">{shift.citation}</span>
      </div>

      <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
        <span>Policy {shift.policy_version_before}</span>
        <span>→</span>
        <span className="text-emerald-400">{shift.policy_version_after}</span>
      </div>

      <p className="mt-3 text-xs text-slate-400 leading-relaxed">{shift.summary}</p>
    </div>
  );
}
