import { NavLink, Outlet } from 'react-router-dom';
import { clsx } from 'clsx';
import { useDomain } from '../hooks/useDomain';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '◉' },
  { to: '/cases', label: 'Demo Cases', icon: '⬡' },
  { to: '/seeds', label: 'Seed Explorer', icon: '◎' },
  { to: '/policy-shifts', label: 'Policy Shifts', icon: '⇄' },
  { to: '/sandbox', label: 'Policy Sandbox', icon: '⚗' },
  { to: '/registry', label: 'Field Registry', icon: '▤' },
  { to: '/audit', label: 'Audit Search', icon: '⌕' },
];

// Note: Report Viewer is at /reports/:decisionId — accessed by clicking decisions from all pages

export default function Layout() {
  const { branding } = useDomain();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="flex w-60 flex-col border-r border-slate-700/60 bg-slate-900">
        {/* Logo */}
        <div className="flex items-center gap-3 border-b border-slate-700/60 px-5 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 text-sm font-bold">
            {branding.logo}
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-100">{branding.title}</p>
            <p className="text-[10px] text-slate-500">{branding.subtitle}</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-0.5 px-3 py-4">
          {NAV_ITEMS.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-emerald-500/10 text-emerald-400 font-medium'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                )
              }
            >
              <span className="text-base">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="border-t border-slate-700/60 px-5 py-3">
          <p className="text-[10px] text-slate-600">{branding.footerLine1}</p>
          <p className="text-[10px] text-slate-600">{branding.footerLine2}</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-slate-900 p-6">
        <Outlet />
      </main>
    </div>
  );
}
