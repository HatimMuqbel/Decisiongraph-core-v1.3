import type { ConfidenceDimension } from '../../types';
import { clsx } from 'clsx';

interface Props {
  level: string;
  dimensions: ConfidenceDimension[];
  bottleneck?: string;
  hardRule?: string;
  firstImpressionAlert?: string;
  transferableCount?: number;
  comparableCount?: number;
}

const LEVEL_CONFIG: Record<string, { color: string; width: string }> = {
  VERY_HIGH: { color: 'bg-emerald-500', width: '95%' },
  HIGH:      { color: 'bg-emerald-500', width: '75%' },
  MODERATE:  { color: 'bg-amber-500',   width: '50%' },
  LOW:       { color: 'bg-red-500',     width: '25%' },
  NONE:      { color: 'bg-slate-600',   width: '5%' },
};

const LEVEL_TEXT_COLOR: Record<string, string> = {
  VERY_HIGH: 'text-emerald-400',
  HIGH:      'text-emerald-400',
  MODERATE:  'text-amber-400',
  LOW:       'text-red-400',
  NONE:      'text-white',
};

const DIM_LABELS: Record<string, string> = {
  pool_adequacy:        'Pool Adequacy',
  similarity_quality:   'Similarity Quality',
  outcome_consistency:  'Outcome Consistency',
  evidence_completeness: 'Evidence Completeness',
};

export default function TerminalConfidenceCard({ level, dimensions, bottleneck, hardRule, firstImpressionAlert, transferableCount, comparableCount }: Props) {
  const levelCfg = LEVEL_CONFIG[level] ?? LEVEL_CONFIG.NONE;

  return (
    <div className="rounded-xl border border-blue-500/30 bg-slate-800 p-5">
      <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white">
        Terminal Confidence
      </h4>

      <div className={clsx('text-3xl font-bold', LEVEL_TEXT_COLOR[level] ?? 'text-white')}>
        {level.replace('_', ' ')}
      </div>

      {bottleneck && (
        <p className="mt-1 text-xs text-white">
          Bottleneck: {DIM_LABELS[bottleneck] ?? bottleneck}
        </p>
      )}

      {hardRule && (
        <p className="mt-1 text-xs text-red-400/80 italic">{hardRule}</p>
      )}

      {firstImpressionAlert && (
        <div className="mt-2 rounded-lg bg-red-500/10 border border-red-500/20 p-2">
          <p className="text-xs text-red-400 font-semibold">⚠ FIRST-IMPRESSION CASE</p>
          <p className="mt-0.5 text-[11px] text-red-300/80">{firstImpressionAlert}</p>
        </div>
      )}

      <div className="mt-4 space-y-3">
        {dimensions.map((dim) => {
          // Fix 2: outcome_consistency with "No terminal precedents" note → display N/A
          const isNaDimension =
            dim.name === 'outcome_consistency' &&
            dim.note &&
            dim.note.toLowerCase().includes('no terminal precedent');
          const displayLevel = isNaDimension ? 'N/A' : dim.level.replace('_', ' ');
          const cfg = isNaDimension
            ? { color: 'bg-slate-600', width: '0%' }
            : (LEVEL_CONFIG[dim.level] ?? LEVEL_CONFIG.NONE);
          const isBottleneck = dim.bottleneck;
          const label = DIM_LABELS[dim.name] ?? dim.name;

          return (
            <div key={dim.name}>
              <div className="flex items-center justify-between text-[11px]">
                <span className={clsx(
                  'text-white',
                  isBottleneck && 'font-semibold text-slate-200',
                )}>
                  {label}
                  {isBottleneck && <span className="ml-1 text-amber-400">★</span>}
                </span>
                <span className={clsx(
                  'font-medium',
                  isNaDimension ? 'text-white' : (LEVEL_TEXT_COLOR[dim.level] ?? 'text-white'),
                )}>
                  {displayLevel}
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-700">
                <div
                  className={clsx('h-full rounded-full transition-all', cfg.color)}
                  style={{ width: cfg.width }}
                />
              </div>
              {dim.note && (
                <p className="mt-0.5 text-[10px] text-white leading-tight">
                  {dim.note}
                  {dim.name === 'pool_adequacy' && transferableCount != null && comparableCount != null && transferableCount < comparableCount && (
                    <span className="text-amber-400"> (Transferable: {transferableCount}/{comparableCount})</span>
                  )}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
