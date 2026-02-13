import type { ReportViewModel } from '../../types';

interface LinchpinStatementProps {
  report: ReportViewModel;
}

export default function LinchpinStatement({ report }: LinchpinStatementProps) {
  const statement =
    report.decision_explainer ||
    report.summary ||
    'No decision summary available.';

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white">
        Decision Summary
      </h3>
      <p className="text-base font-medium leading-relaxed text-slate-100">
        {statement}
      </p>
      {report.primary_typology &&
        report.primary_typology !== 'No suspicious typology identified' && (
          <div className="mt-3 flex items-center gap-2">
            <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-400 border border-amber-500/20">
              Primary Typology
            </span>
            <span className="text-sm text-slate-300">{report.primary_typology}</span>
          </div>
        )}
    </div>
  );
}
