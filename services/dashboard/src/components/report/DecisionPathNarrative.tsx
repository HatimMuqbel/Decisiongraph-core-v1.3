import type { ReportViewModel } from '../../types';

interface PathStep {
  number: number;
  symbol: string;
  title: string;
  detail_lines: string[];
  arrow_line: string;
}

interface Props {
  report: ReportViewModel;
}

export default function DecisionPathNarrative({ report }: Props) {
  const narrative = report.decision_path_narrative as
    | { steps: PathStep[]; path_code: string }
    | undefined;

  if (!narrative?.steps?.length) return null;

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-white">
        Decision Path
      </h3>
      <div className="border-l-4 border-slate-600 pl-4 space-y-0">
        {narrative.steps.map((step, i) => (
          <div
            key={step.number}
            className={i > 0 ? 'mt-4 border-t border-slate-700/40 pt-4' : ''}
          >
            <div className="text-sm font-bold text-slate-200">
              {step.symbol} {step.title}
            </div>
            {step.detail_lines.map((line, j) => (
              <p key={j} className="mt-1 ml-6 text-xs text-slate-400">
                {line}
              </p>
            ))}
            <p className="mt-2 ml-6 text-xs font-semibold text-slate-500">
              &rarr; {step.arrow_line}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
