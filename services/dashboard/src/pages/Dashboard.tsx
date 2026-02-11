import { useDemoCases } from '../hooks/useApi';
import { useDomain } from '../hooks/useDomain';
import { StatsCard, Loading, ErrorMessage, Badge, dispositionVariant } from '../components';
import { Link } from 'react-router-dom';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const OUTCOME_COLORS: Record<string, string> = {
  ALLOW: '#10b981',
  EDD: '#f59e0b',
  BLOCK: '#ef4444',
  PAY_CLAIM: '#10b981',
  INVESTIGATE: '#f59e0b',
  DENY_CLAIM: '#ef4444',
};

// ── Banking scenario data ──────────────────────────────────────────────────
const BANKING_SCENARIO_DATA = [
  { name: 'Clean Customer', weight: 25, disposition: 'ALLOW' },
  { name: 'New Large Clear', weight: 8, disposition: 'ALLOW' },
  { name: 'Structuring', weight: 6, disposition: 'EDD' },
  { name: 'Round Amount', weight: 4, disposition: 'EDD' },
  { name: 'Source Unclear', weight: 5, disposition: 'EDD' },
  { name: 'Purpose Unclear', weight: 4, disposition: 'EDD' },
  { name: 'Adverse Media', weight: 4, disposition: 'EDD' },
  { name: 'Rapid Movement', weight: 4, disposition: 'EDD' },
  { name: 'Profile Deviation', weight: 4, disposition: 'EDD' },
  { name: 'Third Party', weight: 3, disposition: 'EDD' },
];
const BANKING_OUTCOME_PIE = [
  { name: 'ALLOW', value: 36, fill: OUTCOME_COLORS.ALLOW },
  { name: 'EDD', value: 56, fill: OUTCOME_COLORS.EDD },
  { name: 'BLOCK', value: 8, fill: OUTCOME_COLORS.BLOCK },
];

// ── Insurance scenario data ────────────────────────────────────────────────
const INSURANCE_SCENARIO_DATA = [
  { name: 'Auto Standard', weight: 15, disposition: 'PAY_CLAIM' },
  { name: 'Property Fire', weight: 10, disposition: 'PAY_CLAIM' },
  { name: 'Health Formulary', weight: 8, disposition: 'PAY_CLAIM' },
  { name: 'WSIB Work Injury', weight: 8, disposition: 'PAY_CLAIM' },
  { name: 'Marine Storm', weight: 5, disposition: 'PAY_CLAIM' },
  { name: 'Auto Impaired', weight: 8, disposition: 'DENY_CLAIM' },
  { name: 'Fraud Indicator', weight: 6, disposition: 'INVESTIGATE' },
  { name: 'SIU Referral', weight: 5, disposition: 'INVESTIGATE' },
  { name: 'Property Vacancy', weight: 5, disposition: 'DENY_CLAIM' },
  { name: 'Edge Cases', weight: 12, disposition: 'INVESTIGATE' },
];
const INSURANCE_OUTCOME_PIE = [
  { name: 'PAY_CLAIM', value: 55, fill: OUTCOME_COLORS.PAY_CLAIM },
  { name: 'INVESTIGATE', value: 28, fill: OUTCOME_COLORS.INVESTIGATE },
  { name: 'DENY_CLAIM', value: 17, fill: OUTCOME_COLORS.DENY_CLAIM },
];

export default function Dashboard() {
  const { data: cases, isLoading, error } = useDemoCases();
  const { branding, isInsurance } = useDomain();

  if (isLoading) return <Loading text="Loading dashboard..." />;
  if (error) return <ErrorMessage error={error as Error} />;

  const scenarioData = isInsurance ? INSURANCE_SCENARIO_DATA : BANKING_SCENARIO_DATA;
  const outcomePie = isInsurance ? INSURANCE_OUTCOME_PIE : BANKING_OUTCOME_PIE;
  const seedLabel = isInsurance ? '20 insurance scenarios' : '20 AML scenarios';
  const seedCount = isInsurance ? '1,618' : '1,500';
  const shiftCount = isInsurance ? '3' : '4';
  const fieldCount = isInsurance ? '23' : '28';
  const filingAuthority = isInsurance ? 'FSRA' : 'FINTRAC';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-400">
          {branding.dashboardHeading}
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard label="Total Seeds" value={seedCount} sub={seedLabel} />
        <StatsCard label="Demo Cases" value={cases?.length ?? 0} sub={`${cases?.length ?? 0} pre-built`} />
        <StatsCard label="Policy Shifts" value={shiftCount} sub="Shadow projections active" />
        <StatsCard label="Registry Fields" value={fieldCount} sub="Weighted scoring fields" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Outcome Distribution Pie */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">
            Seed Outcome Distribution
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={outcomePie}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={3}
                dataKey="value"
                label={({ name, value }) => `${name.replace('_', ' ')} ${value}%`}
              >
                {outcomePie.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                itemStyle={{ color: '#e2e8f0' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Scenario Bar Chart */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">
            Scenario Weight Distribution (%)
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={scenarioData} layout="vertical" margin={{ left: 80 }}>
              <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis
                dataKey="name"
                type="category"
                width={80}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                itemStyle={{ color: '#e2e8f0' }}
              />
              <Bar dataKey="weight" radius={[0, 4, 4, 0]}>
                {scenarioData.map((entry, idx) => (
                  <Cell key={idx} fill={OUTCOME_COLORS[entry.disposition] || '#64748b'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Demo Cases */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Demo Cases
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-left">
                <th className="px-3 py-2 text-xs font-medium uppercase text-slate-400">Case</th>
                <th className="px-3 py-2 text-xs font-medium uppercase text-slate-400">Category</th>
                <th className="px-3 py-2 text-xs font-medium uppercase text-slate-400">Expected</th>
                <th className="px-3 py-2 text-xs font-medium uppercase text-slate-400">Key Levers</th>
                <th className="px-3 py-2 text-xs font-medium uppercase text-slate-400">Action</th>
              </tr>
            </thead>
            <tbody>
              {cases?.map((c) => (
                <tr key={c.id} className="border-b border-slate-800 hover:bg-slate-800/50">
                  <td className="px-3 py-3">
                    <p className="font-medium text-slate-200">{c.name}</p>
                    <p className="text-xs text-slate-500">{c.description}</p>
                  </td>
                  <td className="px-3 py-3">
                    <Badge
                      variant={
                        c.category === 'PASS'
                          ? 'success'
                          : c.category === 'ESCALATE'
                          ? 'danger'
                          : 'warning'
                      }
                    >
                      {c.category}
                    </Badge>
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant={dispositionVariant(c.expected_verdict)}>
                      {c.expected_verdict}
                    </Badge>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap gap-1">
                      {c.key_levers?.slice(0, 3).map((l, i) => (
                        <span key={i} className="text-xs text-slate-400">
                          {l}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <Link
                      to={`/cases/${c.id}`}
                      className="text-xs font-medium text-emerald-400 hover:text-emerald-300"
                    >
                      Run &rarr;
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Report Viewer CTA */}
      <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-5">
        <h2 className="mb-2 text-sm font-semibold text-blue-400">
          Progressive Disclosure Compliance Reports
        </h2>
        <p className="text-xs text-slate-400 mb-3">
          Run any demo case through the engine, then view the full 3-tier compliance report.
          Reports include risk heatmaps, typology analysis, negative path search, verbatim
          citations, and full audit metadata for {filingAuthority} examination.
        </p>
        <Link
          to="/cases"
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition"
        >
          Open Demo Cases to Generate Reports &rarr;
        </Link>
      </div>
    </div>
  );
}
