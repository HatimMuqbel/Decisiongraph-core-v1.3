import type { EnhancedPrecedent } from '../../types';

interface Props {
  divergence: NonNullable<EnhancedPrecedent['divergence_justification']>;
  overrideStatement?: string | null;
}

export default function DivergenceJustification({ divergence, overrideStatement }: Props) {
  return (
    <div className="rounded-xl border-l-4 border-l-amber-500 border border-amber-500/20 bg-amber-500/5 p-5">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-amber-400">
        Divergence Justification
      </h4>
      <p className="text-sm leading-relaxed text-amber-200/90">{divergence.statement}</p>

      {divergence.contrary_details && divergence.contrary_details.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-amber-500/20 text-left">
                <th className="px-2 py-1.5 text-amber-400/70">Precedent</th>
                <th className="px-2 py-1.5 text-amber-400/70">Outcome</th>
                <th className="px-2 py-1.5 text-amber-400/70">Similarity</th>
                <th className="px-2 py-1.5 text-amber-400/70">Distinguishing Factors</th>
              </tr>
            </thead>
            <tbody>
              {divergence.contrary_details.map((cd, i) => (
                <tr key={i} className="border-b border-amber-500/10">
                  <td className="px-2 py-1.5 font-mono text-slate-400">{cd.precedent_id?.slice(0, 10)}…</td>
                  <td className="px-2 py-1.5 text-red-400">{cd.outcome}</td>
                  <td className="px-2 py-1.5 text-slate-300">{cd.similarity_pct}%</td>
                  <td className="px-2 py-1.5 text-slate-400">{cd.distinguishing_factors}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {overrideStatement && (
        <div className="mt-3 rounded-lg bg-red-500/10 border border-red-500/20 p-3">
          <p className="text-xs font-medium text-red-400">Override Statement</p>
          <p className="mt-1 text-xs text-red-300">{overrideStatement}</p>
        </div>
      )}

      {/* Compliance Officer Sign-Off */}
      <div className="mt-4 rounded-lg border border-amber-500/20 bg-slate-800 p-4">
        <h5 className="mb-3 text-xs font-semibold text-amber-400">
          Compliance Officer Sign-Off Required (INV-009)
        </h5>
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <span className="w-20 text-xs text-slate-500">Reviewer</span>
            <div className="flex-1 border-b border-slate-700 py-1 text-xs text-slate-600 italic">
              ____________________
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="w-20 text-xs text-slate-500">Date</span>
            <div className="flex-1 border-b border-slate-700 py-1 text-xs text-slate-600 italic">
              ____________________
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="w-20 text-xs text-slate-500">Rationale</span>
            <div className="flex-1 border-b border-slate-700 py-1 text-xs text-slate-600 italic">
              ____________________
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
