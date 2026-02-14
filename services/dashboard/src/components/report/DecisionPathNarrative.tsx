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
  // arrow_line looks like "Classifier recommends: STR REQUIRED" or "Gate 1: BLOCKED — reason"
  const colonIdx = arrowLine.lastIndexOf(':');
  if (colonIdx === -1) return arrowLine;
  let text = arrowLine.slice(colonIdx + 1).trim();
  // Trim off "— explanation" suffix
  const dashIdx = text.indexOf('—');
  if (dashIdx > 0) text = text.slice(0, dashIdx).trim();
  // Trim off " — explanation" with em-dash
  const emIdx = text.indexOf('\u2014');
  if (emIdx > 0) text = text.slice(0, emIdx).trim();
  return text.replace(/_/g, ' ');
}

// ── Color config ─────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<StepStatus, {
  card: string;
  border: string;
  badge: string;
  badgeText: string;
  connector: string;
}> = {
  passed: {
    card: 'border-emerald-500/30 bg-emerald-500/10',
    border: 'border-l-emerald-500',
    badge: 'bg-emerald-500/20 ring-1 ring-emerald-500/40',
    badgeText: 'text-emerald-400',
    connector: 'bg-slate-600',
  },
  blocked: {
    card: 'border-red-500/30 bg-red-500/10',
    border: 'border-l-red-500',
    badge: 'bg-red-500/20 ring-1 ring-red-500/40',
    badgeText: 'text-red-400',
    connector: 'bg-red-500/60',
  },
  skipped: {
    card: 'border-slate-600/40 bg-slate-700/30',
    border: 'border-l-slate-600',
    badge: 'bg-slate-700/50 ring-1 ring-slate-600/40',
    badgeText: 'text-slate-500',
    connector: 'bg-slate-700/50',
  },
  pending: {
    card: 'border-amber-500/30 bg-amber-500/10',
    border: 'border-l-amber-500',
    badge: 'bg-amber-500/20 ring-1 ring-amber-500/40',
    badgeText: 'text-amber-400',
    connector: 'bg-slate-600',
  },
};

// ── Connector arrow ──────────────────────────────────────────────────────────

function Connector({ status }: { status: StepStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <div className="flex justify-center py-1">
      <div className="flex flex-col items-center">
        <div className={clsx('h-4 w-0.5 rounded-full', style.connector)} />
        <div
          className={clsx(
            'h-0 w-0 border-l-[5px] border-r-[5px] border-t-[6px] border-l-transparent border-r-transparent',
            status === 'blocked' && 'border-t-red-500/60',
            status === 'skipped' && 'border-t-slate-700/50',
            status !== 'blocked' && status !== 'skipped' && 'border-t-slate-600',
          )}
        />
      </div>
    </div>
  );
}

// ── Single step card ─────────────────────────────────────────────────────────

function StepCard({ step, status }: { step: PathStep; status: StepStatus }) {
  const [expanded, setExpanded] = useState(false);
  const style = STATUS_STYLES[status];
  const hasDetail = step.detail_lines.length > 0;
  const dimmed = status === 'skipped';
  const badgeText = extractBadgeText(step.arrow_line);

  // Build a one-line summary from the first detail line, or fall back to arrow_line
  const summary = step.detail_lines[0] || step.arrow_line;

  return (
    <div
      className={clsx(
        'rounded-xl border-l-4 border bg-slate-800 transition-all',
        style.card,
        style.border,
        dimmed && 'opacity-55',
        hasDetail && 'cursor-pointer',
      )}
      onClick={() => hasDetail && setExpanded((e) => !e)}
    >
      <div className="flex items-start justify-between gap-3 px-4 py-3">
        {/* Left: step number + title + summary */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={clsx('text-base font-bold', style.badgeText)}>
              {step.symbol}
            </span>
            <span className="text-sm font-semibold text-slate-200">
              {step.title}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400 leading-relaxed">
            {summary}
          </p>
          {hasDetail && !expanded && (
            <p className="mt-1 text-[10px] text-slate-600 italic">
              tap for detail
            </p>
          )}
        </div>

        {/* Right: status badge */}
        <span
          className={clsx(
            'mt-0.5 flex-shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide',
            style.badge,
            style.badgeText,
          )}
        >
          {badgeText}
        </span>
      </div>

      {/* Expanded detail */}
      {expanded && hasDetail && (
        <div className="border-t border-slate-700/40 px-4 py-3 ml-7">
          {step.detail_lines.map((line, i) => (
            <p key={i} className="text-xs text-slate-400 leading-relaxed mb-1">
              {line}
            </p>
          ))}
          <p className="mt-2 text-xs font-semibold text-slate-500">
            &rarr; {step.arrow_line}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Final outcome bar ────────────────────────────────────────────────────────

function OutcomeBar({ disposition }: { disposition: string }) {
  return (
    <div className="rounded-lg bg-slate-900 border border-slate-700/60 px-5 py-3 text-center">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
        Governed Disposition
      </span>
      <p className="mt-1 text-sm font-bold text-slate-100 tracking-wide">
        {disposition.replace(/_/g, ' ')}
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

  // Terminal disposition from the last step's arrow_line, or fall back to governed_disposition
  const lastArrow = steps[steps.length - 1]?.arrow_line ?? '';
  const terminalDisposition =
    extractBadgeText(lastArrow) || report.governed_disposition || report.verdict || 'UNKNOWN';

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-5">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-white">
        Decision Path
      </h3>

      <div className="space-y-0">
        {steps.map((step, i) => (
          <div key={step.number}>
            <StepCard step={step} status={statuses[i]} />
            {i < steps.length - 1 && (
              <Connector status={statuses[i]} />
            )}
          </div>
        ))}

        {/* Final connector into outcome bar */}
        <div className="flex justify-center py-1">
          <div className="flex flex-col items-center">
            <div className="h-4 w-0.5 rounded-full bg-slate-600" />
            <div className="h-0 w-0 border-l-[5px] border-r-[5px] border-t-[6px] border-l-transparent border-r-transparent border-t-slate-600" />
          </div>
        </div>

        <OutcomeBar disposition={terminalDisposition} />
      </div>
    </div>
  );
}
