import { useEffect } from 'react';
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
      <AppWithDomain />
    </QueryClientProvider>
  );
}
