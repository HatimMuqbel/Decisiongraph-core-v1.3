import { useDemoCases } from '../hooks/useApi';
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
  Legend,
} from 'recharts';

const COLORS = {
  PASS: '#10b981',
  ESCALATE: '#f59e0b',
  EDGE: '#ef4444',
};

const OUTCOME_COLORS: Record<string, string> = {
  ALLOW: '#10b981',
  EDD: '#f59e0b',
  BLOCK: '#ef4444',
};

// Scenario distribution for the 20 AML scenarios (from seed generator weights)
const SCENARIO_DATA = [
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
  { name: 'Layering/Shell', weight: 4, disposition: 'EDD' },
  { name: 'High Risk Country', weight: 4, disposition: 'EDD' },
  { name: 'Cash Intensive', weight: 4, disposition: 'EDD' },
  { name: 'PEP Large', weight: 4, disposition: 'EDD' },
  { name: 'PEP Screening', weight: 3, disposition: 'EDD' },
  { name: 'Sanctions Match', weight: 3, disposition: 'BLOCK' },
  { name: '1 Prior SAR', weight: 3, disposition: 'ALLOW' },
  { name: 'Multiple SARs', weight: 3, disposition: 'EDD' },
  { name: 'Heavy SAR Hist', weight: 2, disposition: 'BLOCK' },
  { name: 'Prev Closure', weight: 3, disposition: 'EDD' },
];

const OUTCOME_PIE = [
  { name: 'ALLOW', value: 36, fill: OUTCOME_COLORS.ALLOW },
  { name: 'EDD', value: 56, fill: OUTCOME_COLORS.EDD },
  { name: 'BLOCK', value: 8, fill: OUTCOME_COLORS.BLOCK },
];

export default function Dashboard() {
  const { data: cases, isLoading, error } = useDemoCases();

  if (isLoading) return <Loading text="Loading dashboard…" />;
  if (error) return <ErrorMessage error={error as Error} />;

  const categoryCounts = { PASS: 0, ESCALATE: 0, EDGE: 0 };
  cases?.forEach((c) => {
    const cat = c.category as keyof typeof categoryCounts;
    if (cat in categoryCounts) categoryCounts[cat]++;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-400">
          DecisionGraph AML Decision Engine — Overview
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard label="Total Seeds" value="1,500" sub="20 AML scenarios" />
        <StatsCard label="Demo Cases" value={cases?.length ?? 0} sub="10 pre-built" />
        <StatsCard label="Policy Shifts" value="4" sub="Shadow projections active" />
        <StatsCard label="Registry Fields" value="28" sub="5 field groups" />
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
                data={OUTCOME_PIE}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={3}
                dataKey="value"
                label={({ name, value }) => `${name} ${value}%`}
              >
                {OUTCOME_PIE.map((entry) => (
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
            <BarChart data={SCENARIO_DATA.slice(0, 10)} layout="vertical" margin={{ left: 80 }}>
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
                {SCENARIO_DATA.slice(0, 10).map((entry, idx) => (
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
    </div>
  );
}
