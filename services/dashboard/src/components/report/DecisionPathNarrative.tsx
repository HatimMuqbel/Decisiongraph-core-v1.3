import { useState } from 'react';
import { clsx } from 'clsx';
import type { ReportViewModel } from '../../types';

// ── Types ────────────────────────────────────────────────────────────────────

interface PathStep {
  number: number;
  symbol: string;
  title: string;
  detail_lines: string[];
  arrow_line: string;
}

type StepStatus = 'passed' | 'blocked' | 'skipped' | 'pending';

// ── Status derivation ────────────────────────────────────────────────────────

const BLOCKED_PATTERNS = ['BLOCKED', 'PROHIBITED', 'INSUFFICIENT'];
const SKIPPED_PATTERNS = ['NOT EVALUATED', 'SKIPPED'];
const PASSED_PATTERNS = ['PASSED', 'PERMITTED', 'CONFIRMED', 'NO REPORT', 'PASS', 'NO_REPORT'];

function deriveStatus(step: PathStep): StepStatus {
  const arrow = step.arrow_line.toUpperCase();
  if (SKIPPED_PATTERNS.some((p) => arrow.includes(p))) return 'skipped';
  if (BLOCKED_PATTERNS.some((p) => arrow.includes(p))) return 'blocked';
  if (PASSED_PATTERNS.some((p) => arrow.includes(p))) return 'passed';
  return 'pending';
}

function extractBadgeText(arrowLine: string): string {
  const colonIdx = arrowLine.lastIndexOf(':');
  if (colonIdx === -1) return arrowLine;
  let text = arrowLine.slice(colonIdx + 1).trim();
  const dashIdx = text.indexOf('—');
  if (dashIdx > 0) text = text.slice(0, dashIdx).trim();
  const emIdx = text.indexOf('\u2014');
  if (emIdx > 0) text = text.slice(0, emIdx).trim();
  return text.replace(/_/g, ' ');
}

// ── Color config ─────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<StepStatus, {
  card: string;
  borderTop: string;
  badge: string;
  badgeText: string;
  connector: string;
  connectorArrow: string;
}> = {
  passed: {
    card: 'border-emerald-500/30 bg-emerald-500/10',
    borderTop: 'border-t-emerald-500',
    badge: 'bg-emerald-500/20 ring-1 ring-emerald-500/40',
    badgeText: 'text-emerald-400',
    connector: 'bg-slate-600',
    connectorArrow: 'border-l-slate-600',
  },
  blocked: {
    card: 'border-red-500/30 bg-red-500/10',
    borderTop: 'border-t-red-500',
    badge: 'bg-red-500/20 ring-1 ring-red-500/40',
    badgeText: 'text-red-400',
    connector: 'bg-red-500/60',
    connectorArrow: 'border-l-red-500/60',
  },
  skipped: {
    card: 'border-slate-600/40 bg-slate-700/30',
    borderTop: 'border-t-slate-600',
    badge: 'bg-slate-700/50 ring-1 ring-slate-600/40',
    badgeText: 'text-slate-500',
    connector: 'bg-slate-700/50',
    connectorArrow: 'border-l-slate-700/50',
  },
  pending: {
    card: 'border-amber-500/30 bg-amber-500/10',
    borderTop: 'border-t-amber-500',
    badge: 'bg-amber-500/20 ring-1 ring-amber-500/40',
    badgeText: 'text-amber-400',
    connector: 'bg-slate-600',
    connectorArrow: 'border-l-slate-600',
  },
};

// ── Horizontal connector arrow ───────────────────────────────────────────────

function HConnector({ status }: { status: StepStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <div className="flex items-center self-center flex-shrink-0 mx-[-2px]">
      <div className={clsx('h-0.5 w-4 rounded-full', style.connector)} />
      <div
        className={clsx(
          'h-0 w-0 border-t-[4px] border-b-[4px] border-l-[6px] border-t-transparent border-b-transparent',
          style.connectorArrow,
        )}
      />
    </div>
  );
}

// ── Single step card (compact, horizontal) ───────────────────────────────────

function StepCard({ step, status, isExpanded, onToggle }: {
  step: PathStep;
  status: StepStatus;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const style = STATUS_STYLES[status];
  const hasDetail = step.detail_lines.length > 0;
  const dimmed = status === 'skipped';
  const badgeText = extractBadgeText(step.arrow_line);

  return (
    <div
      className={clsx(
        'rounded-lg border-t-[3px] border flex flex-col min-w-0 flex-1 transition-all',
        style.card,
        style.borderTop,
        dimmed && 'opacity-55',
        hasDetail && 'cursor-pointer',
      )}
      onClick={() => hasDetail && onToggle()}
    >
      <div className="px-3 py-2 flex flex-col items-center text-center gap-1">
        <span className={clsx('text-lg font-bold leading-none', style.badgeText)}>
          {step.symbol}
        </span>
        <span className="text-[10px] font-semibold text-slate-300 leading-tight">
          {step.title}
        </span>
        <span
          className={clsx(
            'mt-1 rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide whitespace-nowrap',
            style.badge,
            style.badgeText,
          )}
        >
          {badgeText}
        </span>
      </div>
    </div>
  );
}

// ── Expanded detail panel (shown below the row) ──────────────────────────────

function DetailPanel({ step, status }: { step: PathStep; status: StepStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <div className={clsx(
      'rounded-lg border px-4 py-3 mt-2',
      style.card,
    )}>
      <div className="flex items-center gap-2 mb-2">
        <span className={clsx('text-sm font-bold', style.badgeText)}>{step.symbol}</span>
        <span className="text-xs font-semibold text-slate-200">{step.title}</span>
      </div>
      {step.detail_lines.map((line, i) => (
        <p key={i} className="text-xs text-slate-400 leading-relaxed mb-1 ml-5">
          {line}
        </p>
      ))}
      <p className="mt-2 ml-5 text-xs font-semibold text-slate-500">
        &rarr; {step.arrow_line}
      </p>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export default function DecisionPathNarrative({ report }: { report: ReportViewModel }) {
  const narrative = report.decision_path_narrative;
  if (!narrative?.steps?.length) return null;

  const steps = narrative.steps as PathStep[];
  const statuses = steps.map(deriveStatus);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const lastArrow = steps[steps.length - 1]?.arrow_line ?? '';
  const terminalDisposition =
    extractBadgeText(lastArrow) || report.governed_disposition || report.verdict || 'UNKNOWN';

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-5">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-white">
        Decision Path
      </h3>

      {/* Horizontal flow: cards + arrows + outcome */}
      <div className="flex items-stretch gap-0 overflow-x-auto pb-2">
        {steps.map((step, i) => (
          <div key={step.number} className="contents">
            <StepCard
              step={step}
              status={statuses[i]}
              isExpanded={expandedIdx === i}
              onToggle={() => setExpandedIdx(expandedIdx === i ? null : i)}
            />
            {i < steps.length - 1 && (
              <HConnector status={statuses[i]} />
            )}
          </div>
        ))}

        {/* Final arrow into outcome */}
        <div className="flex items-center self-center flex-shrink-0 mx-[-2px]">
          <div className="h-0.5 w-4 rounded-full bg-slate-600" />
          <div className="h-0 w-0 border-t-[4px] border-b-[4px] border-l-[6px] border-t-transparent border-b-transparent border-l-slate-600" />
        </div>

        {/* Outcome pill */}
        <div className="flex-shrink-0 self-center rounded-lg bg-slate-900 border border-slate-700/60 px-3 py-2 text-center">
          <span className="text-[8px] font-semibold uppercase tracking-widest text-slate-500 block">
            Disposition
          </span>
          <span className="text-xs font-bold text-slate-100 whitespace-nowrap">
            {terminalDisposition}
          </span>
        </div>
      </div>

      {/* Expanded detail below the row */}
      {expandedIdx !== null && steps[expandedIdx]?.detail_lines.length > 0 && (
        <DetailPanel step={steps[expandedIdx]} status={statuses[expandedIdx]} />
      )}
    </div>
  );
}
