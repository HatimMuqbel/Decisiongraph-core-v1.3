import type { RegimeAnalysis } from '../../types';

interface Props {
  patternSummary?: string;
  institutionalPosture?: string;
  regimeAnalysis?: RegimeAnalysis;
  postShiftGapStatement?: string;
  suspicionPosture?: string[];
}

export default function InstitutionalPosture({ patternSummary, institutionalPosture, regimeAnalysis, postShiftGapStatement, suspicionPosture }: Props) {
  if (!patternSummary && !institutionalPosture) {
    return (
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <p className="text-sm text-slate-500 italic">
          Insufficient resolved precedents to establish institutional posture for this case profile.
        </p>
      </div>
    );
  }

  // Build regime context addendum
  const ra = regimeAnalysis;
  const hasRegime = ra && ra.shifts_detected && ra.shifts_detected.length > 0;
  let regimeNote = '';
  if (hasRegime) {
    const shift = ra.shifts_detected[0];
    const preDist = ra.pre_shift_distribution;
    const postDist = ra.post_shift_distribution;
    const preDominant = Object.entries(preDist).sort(([, a], [, b]) => b - a)[0];
    const postDominant = Object.entries(postDist).sort(([, a], [, b]) => b - a)[0];
    const prePct = preDominant ? Math.round((preDominant[1] / ra.pre_shift_count) * 100) : 0;
    const postPct = postDominant ? Math.round((postDominant[1] / ra.post_shift_count) * 100) : 0;
    regimeNote = `Note: Historical practice spans two policy regimes. Under current policy (post ${shift.effective_date}), ${ra.post_shift_count} comparable cases resulted in ${postDominant?.[0] ?? 'N/A'} (${postPct}%). Under prior policy, ${prePct}% were ${preDominant?.[0] ?? 'N/A'}. Current posture reflects ${shift.name}.`;
  }

  return (
    <div className="rounded-xl border border-blue-500/20 bg-slate-800 p-5">
      {patternSummary && (
        <div className="mb-3">
          <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-blue-400">
            Institutional Pattern
          </h4>
          <p className="text-sm leading-relaxed text-slate-300">{patternSummary}</p>
        </div>
      )}
      {institutionalPosture && (
        <div>
          <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-blue-400">
            Institutional Posture
          </h4>
          <p className="text-sm leading-relaxed text-slate-300">{institutionalPosture}</p>
        </div>
      )}
      {regimeNote && (
        <div className="mt-3 border-t border-slate-700/60 pt-3">
          <p className="text-xs leading-relaxed text-amber-300/80 italic">{regimeNote}</p>
        </div>
      )}
      {postShiftGapStatement && (
        <div className="mt-3 border-t border-slate-700/60 pt-3">
          <p className="text-xs leading-relaxed text-red-300/80 italic">{postShiftGapStatement}</p>
        </div>
      )}
      {suspicionPosture && suspicionPosture.length > 0 && (
        <div className="mt-3 border-t border-slate-700/60 pt-3">
          <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-blue-400">
            Suspicion Posture
          </h4>
          {suspicionPosture.map((line, i) => (
            <p key={i} className={`text-sm leading-relaxed ${line.startsWith('\u26a0') ? 'text-red-300 font-semibold' : 'text-slate-300'}`}>
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
