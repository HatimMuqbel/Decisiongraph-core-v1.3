interface Props {
  patternSummary?: string;
  institutionalPosture?: string;
}

export default function InstitutionalPosture({ patternSummary, institutionalPosture }: Props) {
  if (!patternSummary && !institutionalPosture) {
    return (
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <p className="text-sm text-slate-500 italic">
          Insufficient resolved precedents to establish institutional posture for this case profile.
        </p>
      </div>
    );
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
    </div>
  );
}
