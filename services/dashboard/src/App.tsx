import { Component, useEffect } from 'react';
import type { ReactNode, ErrorInfo } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components';
import {
  Dashboard,
  JudgmentQueue,
  DecisionViewer,
  ReportViewer,
  SeedExplorer,
  PolicyShifts,
  PolicySandbox,
  AuditSearch,
  FieldRegistry,
} from './pages';
import {
  DomainContext,
  useDomainQuery,
  BANKING_DEFAULT,
  deriveBranding,
} from './hooks/useDomain';

class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-900 p-8">
          <div className="max-w-lg space-y-4 text-center">
            <h1 className="text-xl font-bold text-red-400">Something went wrong</h1>
            <p className="text-sm text-slate-300">{this.state.error?.message}</p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.href = '/';
              }}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 transition"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppWithDomain() {
  const { data: domainInfo } = useDomainQuery();
  const info = domainInfo ?? BANKING_DEFAULT;
  const branding = deriveBranding(info);
  const isInsurance = info.domain === 'insurance_claims';

  useEffect(() => {
    document.title = isInsurance
      ? 'ClaimPilot — Insurance Claims Engine'
      : 'DecisionGraph — AML Decision Engine';
  }, [isInsurance]);

  return (
    <DomainContext.Provider value={{ info, branding, isInsurance }}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/cases" element={<JudgmentQueue />} />
            <Route path="/cases/:caseId" element={<DecisionViewer />} />
            <Route path="/reports/:decisionId" element={<ReportViewer />} />
            <Route path="/seeds" element={<SeedExplorer />} />
            <Route path="/policy-shifts" element={<PolicyShifts />} />
            <Route path="/sandbox" element={<PolicySandbox />} />
            <Route path="/audit" element={<AuditSearch />} />
            <Route path="/registry" element={<FieldRegistry />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DomainContext.Provider>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <AppWithDomain />
      </ErrorBoundary>
    </QueryClientProvider>
  );
}
