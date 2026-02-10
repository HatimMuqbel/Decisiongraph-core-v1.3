interface Props {
  sharedDrivers: string[];
  divergentDrivers: string[];
}

function formatLabel(d: string): string {
  return d.replace(/^(flag|txn|customer|screening)[\s.]/, '').replace(/[._]/g, ' ');
}

export default function DriverCausalityPanel({ sharedDrivers, divergentDrivers }: Props) {
  if (sharedDrivers.length === 0 && divergentDrivers.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Decision Driver Analysis
      </h4>

      {sharedDrivers.length > 0 && (
        <div className="mb-3">
          <span className="text-[11px] font-medium text-emerald-400">Shared Drivers:</span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {sharedDrivers.map((d, i) => (
              <span
                key={i}
                className="inline-block rounded-md bg-emerald-500/15 px-2.5 py-1 text-[11px] font-medium text-emerald-400 border border-emerald-500/20"
              >
                {formatLabel(d)}
              </span>
            ))}
          </div>
        </div>
      )}

      {divergentDrivers.length > 0 && (
        <div>
          <span className="text-[11px] font-medium text-red-400">Divergent Drivers:</span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {divergentDrivers.map((d, i) => (
              <span
                key={i}
                className="inline-block rounded-md bg-red-500/15 px-2.5 py-1 text-[11px] font-medium text-red-400 border border-red-500/20"
              >
                {formatLabel(d)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
