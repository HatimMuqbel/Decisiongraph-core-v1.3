import type { ReportViewModel } from '../../types';

interface VerbatimCitationsProps {
  report: ReportViewModel;
}

/**
 * Side-by-side: exact PCMLTFA/FINTRAC policy text | case data that triggered it.
 * Maps rules_fired to evidence_used for full regulatory provenance chain.
 * Shows ALL rules (both triggered and cleared) — auditors need to see comprehensive review.
 */
export default function VerbatimCitations({ report }: VerbatimCitationsProps) {
  const allRules = report.rules_fired ?? [];
  const triggeredRules = allRules.filter((r) => r.result === 'TRIGGERED');
  const clearedRules = allRules.filter((r) => r.result !== 'TRIGGERED');

  // Build evidence lookup by field
  const evidenceMap = new Map<string, string>();
  report.evidence_used?.forEach((e) => {
    evidenceMap.set(e.field, String(e.value));
  });

  // Smart evidence matching: map rule codes to relevant evidence fields
  const RULE_EVIDENCE_MAP: Record<string, string[]> = {
    HARD_STOP_CHECK: ['screening.sanctions_match', 'screening.adverse_media', 'prior.account_closures'],
    PEP_ISOLATION: ['customer.pep', 'screening.pep_match'],
    SUSPICION_TEST: ['flag.structuring', 'flag.rapid_movement', 'flag.layering', 'flag.unusual_for_profile'],
    STRUCTURING_PATTERN: ['flag.structuring', 'txn.just_below_threshold', 'txn.multiple_same_day', 'txn.round_amount'],
    LAYERING: ['flag.layering', 'flag.rapid_movement', 'txn.cross_border'],
    SHELL_ENTITY: ['flag.shell_company', 'customer.type'],
    THIRD_PARTY_UNEXPLAINED: ['flag.third_party'],
    FALSE_SOURCE: ['txn.source_of_funds_clear', 'txn.stated_purpose'],
    SANCTIONS_SIGNAL: ['screening.sanctions_match'],
    ADVERSE_MEDIA_CONFIRMED: ['screening.adverse_media'],
    SAR_PATTERN: ['prior.sars_filed'],
    EVASION_BEHAVIOR: ['flag.unusual_for_profile', 'txn.pattern_matches_profile'],
    ROUND_TRIP: ['txn.cross_border', 'txn.destination_country_risk'],
    TRADE_BASED_LAUNDERING: ['txn.cross_border', 'txn.stated_purpose'],
    FUNNEL: ['txn.multiple_same_day', 'txn.cross_border'],
    VIRTUAL_ASSET_LAUNDERING: ['txn.type'],
    TERRORIST_FINANCING: ['screening.sanctions_match', 'screening.adverse_media'],
  };

  const getRelevantEvidence = (ruleCode: string) => {
    const fields = RULE_EVIDENCE_MAP[ruleCode] ?? [];
    return (report.evidence_used ?? []).filter((e) => fields.includes(e.field));
  };

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-white">
        Verbatim Policy Citations
      </h3>
      <p className="mb-4 text-[10px] text-white">
        PCMLTFA / FINTRAC regulatory provisions mapped to triggering case data — full evidence chain
      </p>

      {/* Triggered citations — the ones that mattered */}
      {triggeredRules.length > 0 && (
        <div className="space-y-3 mb-6">
          <h4 className="text-xs font-medium text-red-400 uppercase tracking-wide">
            Triggered Provisions ({triggeredRules.length})
          </h4>
          {triggeredRules.map((rule, i) => (
            <CitationRow
              key={i}
              rule={rule}
              evidence={getRelevantEvidence(rule.code)}
              variant="triggered"
            />
          ))}
        </div>
      )}

      {/* Cleared citations — proves comprehensive review */}
      {clearedRules.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-medium text-emerald-400 uppercase tracking-wide">
            Verified Clear ({clearedRules.length})
          </h4>
          {clearedRules.map((rule, i) => (
            <CitationRow
              key={i}
              rule={rule}
              evidence={getRelevantEvidence(rule.code)}
              variant="clear"
            />
          ))}
        </div>
      )}

      {allRules.length === 0 && (
        <p className="text-sm text-white">No policy citations available for this case.</p>
      )}

      {/* Hash provenance */}
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-white border-t border-slate-700/30 pt-3">
        <span>Policy Hash: <span className="font-mono">{report.policy_hash?.slice(0, 16) ?? 'N/A'}</span></span>
        <span>Input Hash: <span className="font-mono">{report.input_hash?.slice(0, 16) ?? 'N/A'}</span></span>
        <span>Engine: v{report.engine_version}</span>
      </div>
    </div>
  );
}

interface RuleFiredWithCitation {
  code: string;
  result: string;
  reason: string;
  citation_ref?: string;
  citation_text?: string;
}

function CitationRow({
  rule,
  evidence,
  variant,
}: {
  rule: RuleFiredWithCitation;
  evidence: { field: string; value: unknown }[];
  variant: 'triggered' | 'clear';
}) {
  const borderColor = variant === 'triggered' ? 'border-red-500/30' : 'border-emerald-500/20';
  const policyBadgeBg = variant === 'triggered' ? 'bg-red-500/20 text-red-400 border-red-500/20' : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/20';
  const resultColor = variant === 'triggered' ? 'text-red-400' : 'text-emerald-400';

  return (
    <div className={`grid grid-cols-1 gap-0.5 rounded-lg border ${borderColor} overflow-hidden md:grid-cols-2`}>
      {/* Left: Policy citation with real regulatory text */}
      <div className="bg-slate-900 p-4">
        <div className="mb-2 flex items-center gap-2">
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium border ${policyBadgeBg}`}>
            POLICY
          </span>
          <span className="font-mono text-xs text-slate-300">{rule.code}</span>
        </div>
        {rule.citation_ref && (
          <p className="text-[11px] font-medium text-slate-300 mb-1.5">
            {rule.citation_ref}
          </p>
        )}
        <p className="text-xs leading-relaxed text-white italic">
          {rule.citation_text || rule.reason}
        </p>
        {rule.citation_text && rule.reason && rule.reason !== rule.citation_text && (
          <p className="mt-2 text-[10px] text-white">
            Engine finding: {rule.reason}
          </p>
        )}
      </div>

      {/* Right: Case data that triggered/cleared this policy */}
      <div className="bg-slate-900/50 p-4">
        <div className="mb-2 flex items-center gap-2">
          <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-medium text-blue-400 border border-blue-500/20">
            CASE DATA
          </span>
          <span className={`text-[10px] font-medium ${resultColor}`}>
            {rule.result}
          </span>
        </div>
        <div className="space-y-1">
          {evidence.length > 0 ? (
            evidence.slice(0, 6).map((e, j) => (
              <div key={j} className="flex items-center gap-2 text-xs">
                <span className="font-mono text-white">{e.field}</span>
                <span className="text-white">=</span>
                <span className="text-slate-300 font-medium">{String(e.value)}</span>
              </div>
            ))
          ) : (
            <p className="text-[10px] text-white italic">No matching evidence fields present</p>
          )}
        </div>
      </div>
    </div>
  );
}
