import { clsx } from 'clsx';
import type { ReportTier, ReportViewModel } from '../../types';
import { computeAutoEscalation, getMinimumTier } from '../../types';

interface TierBadgeProps {
  currentTier: ReportTier;
  report: ReportViewModel;
  onChangeTier: (tier: ReportTier) => void;
}

const TIER_META: Record<ReportTier, { label: string; role: string; color: string }> = {
  1: { label: 'Tier 1', role: 'Analyst View', color: 'emerald' },
  2: { label: 'Tier 2', role: 'Reviewer View', color: 'amber' },
  3: { label: 'Tier 3', role: 'Regulator View', color: 'red' },
};

export default function TierBadge({ currentTier, report, onChangeTier }: TierBadgeProps) {
  const minTier = getMinimumTier(report);
  const reasons = computeAutoEscalation(report);
  const highestReasons = reasons.filter((r) => r.tier === minTier);

  return (
    <div className="space-y-2">
      {/* Tier tabs */}
      <div className="flex items-center gap-1">
        {([1, 2, 3] as ReportTier[]).map((tier) => {
          const meta = TIER_META[tier];
          const isActive = currentTier === tier;
          const isLocked = tier < minTier;

          return (
            <button
              key={tier}
              onClick={() => !isLocked && onChangeTier(tier)}
              disabled={isLocked}
              className={clsx(
                'relative rounded-lg px-3 py-1.5 text-xs font-medium transition-all',
                isActive && tier === 1 && 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40',
                isActive && tier === 2 && 'bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/40',
                isActive && tier === 3 && 'bg-red-500/20 text-red-400 ring-1 ring-red-500/40',
                !isActive && !isLocked && 'text-white hover:bg-slate-700 hover:text-slate-300',
                isLocked && 'cursor-not-allowed opacity-30',
              )}
            >
              <span>{meta.label}</span>
              <span className="ml-1 text-[10px] opacity-70">{meta.role}</span>
              {tier === minTier && minTier > 1 && (
                <span className="absolute -right-1 -top-1 flex h-3 w-3 items-center justify-center rounded-full bg-amber-500 text-[7px] font-bold text-black">
                  !
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Auto-escalation notice */}
      {minTier > 1 && highestReasons.length > 0 && (
        <div
          className={clsx(
            'rounded-lg px-3 py-2 text-xs',
            minTier === 2 && 'border border-amber-500/20 bg-amber-500/10 text-amber-300',
            minTier === 3 && 'border border-red-500/20 bg-red-500/10 text-red-300',
          )}
        >
          <span className="font-semibold">
            Auto-escalated to {TIER_META[minTier].role}:
          </span>{' '}
          {highestReasons.map((r) => r.reason).join('; ')}
        </div>
      )}
    </div>
  );
}
