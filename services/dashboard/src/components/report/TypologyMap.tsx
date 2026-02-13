import type { ReportViewModel } from '../../types';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts';

interface TypologyMapProps {
  report: ReportViewModel;
}

/**
 * Shows match percentages against known AML/KYC typology patterns.
 * Derives from tier1/tier2 signals and rules_fired to compute rough percentages.
 */

const TYPOLOGIES = [
  { key: 'STRUCTURING_PATTERN', label: 'Structuring' },
  { key: 'LAYERING', label: 'Layering' },
  { key: 'TRADE_BASED_LAUNDERING', label: 'Trade-Based ML' },
  { key: 'FUNNEL', label: 'Funnel Account' },
  { key: 'THIRD_PARTY_UNEXPLAINED', label: 'Third-Party' },
  { key: 'FALSE_SOURCE', label: 'False Source of Funds' },
  { key: 'SHELL_ENTITY', label: 'Shell Entity' },
  { key: 'EVASION_BEHAVIOR', label: 'Evasion Behavior' },
  { key: 'SAR_PATTERN', label: 'SAR Pattern' },
  { key: 'ROUND_TRIP', label: 'Round Trip' },
  { key: 'VIRTUAL_ASSET_LAUNDERING', label: 'Virtual Asset ML' },
  { key: 'TERRORIST_FINANCING', label: 'Terrorist Financing' },
  { key: 'SANCTIONS_SIGNAL', label: 'Sanctions' },
  { key: 'ADVERSE_MEDIA_CONFIRMED', label: 'Adverse Media' },
];

export default function TypologyMap({ report }: TypologyMapProps) {
  const signalCodes = new Set([
    ...report.tier1_signals.map((s) => s.code),
    ...report.tier2_signals.map((s) => s.code),
  ]);

  const rulesCodes = new Set(
    report.rules_fired?.filter((r) => r.result === 'TRIGGERED').map((r) => r.code) ?? [],
  );

  const data = TYPOLOGIES.map((t) => {
    let pct = 0;
    if (signalCodes.has(t.key)) pct += 60;
    // Check if any rule codes contain the typology key fragment
    const keyFragment = t.key.toLowerCase();
    rulesCodes.forEach((rc) => {
      if (rc.toLowerCase().includes(keyFragment.slice(0, 6))) pct += 30;
    });
    // Cap at 100
    pct = Math.min(pct, 100);
    return { ...t, pct };
  })
    .filter((d) => d.pct > 0)
    .sort((a, b) => b.pct - a.pct);

  if (data.length === 0) {
    // Check if the backend detected FORMING typology indicators even though
    // no signal codes matched the hardcoded typology keys.
    const pt = (report.primary_typology ?? '').toLowerCase();
    const isForming = pt.includes('indicators present') || pt.includes('forming');

    return (
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Typology Map
        </h3>
        {isForming ? (
          <p className="text-sm text-amber-400">
            Typology indicators detected at FORMING stage. Pattern not yet established — below
            escalation threshold.
          </p>
        ) : (
          <p className="text-sm text-slate-400">No suspicious typology patterns detected.</p>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Typology Match Analysis
      </h3>
      <ResponsiveContainer width="100%" height={Math.max(120, data.length * 36)}>
        <BarChart data={data} layout="vertical" margin={{ left: 100, right: 30 }}>
          <XAxis type="number" domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 10 }} unit="%" />
          <YAxis
            dataKey="label"
            type="category"
            width={100}
            tick={{ fill: '#94a3b8', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            itemStyle={{ color: '#e2e8f0' }}
            formatter={(value: number) => `${value}%`}
          />
          <Bar dataKey="pct" radius={[0, 4, 4, 0]} maxBarSize={20}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={d.pct >= 60 ? '#ef4444' : d.pct >= 30 ? '#f59e0b' : '#64748b'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
