import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components';
import {
  Dashboard,
  JudgmentQueue,
  DecisionViewer,
  SeedExplorer,
  PolicyShifts,
  AuditSearch,
  FieldRegistry,
} from './pages';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/cases" element={<JudgmentQueue />} />
            <Route path="/cases/:caseId" element={<DecisionViewer />} />
            <Route path="/seeds" element={<SeedExplorer />} />
            <Route path="/policy-shifts" element={<PolicyShifts />} />
            <Route path="/audit" element={<AuditSearch />} />
            <Route path="/registry" element={<FieldRegistry />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
