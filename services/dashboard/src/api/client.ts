// =============================================================================
// API Client — connects to DecisionGraph FastAPI backend
// =============================================================================

const API_BASE = import.meta.env.VITE_API_URL || '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── Health / Info ───────────────────────────────────────────────────────────

import type {
  HealthResponse,
  ReadyResponse,
  VersionResponse,
  DemoCase,
  DecisionPack,
  ReportJsonResponse,
  TemplateInfo,
  TemplateDetail,
  PolicyShiftSummary,
  PolicyShiftDetail,
  DraftShift,
  SimulationReport,
} from '../types';

export const api = {
  // Health
  health: () => request<HealthResponse>('/health'),
  ready: () => request<ReadyResponse>('/ready'),
  version: () => request<VersionResponse>('/version'),

  // Demo cases
  demoCases: (category?: string) =>
    request<DemoCase[]>(category ? `/demo/cases?category=${category}` : '/demo/cases'),
  demoCase: (id: string) => request<DemoCase>(`/demo/cases/${id}`),

  // Decisions
  decide: (caseData: Record<string, unknown>) =>
    request<DecisionPack>('/decide', {
      method: 'POST',
      body: JSON.stringify(caseData),
    }),

  // Reports
  reportJson: (decisionId: string, includeRaw = false) =>
    request<ReportJsonResponse>(
      `/report/${decisionId}/json${includeRaw ? '?include_raw=true' : ''}`
    ),
  reportMarkdown: (decisionId: string) =>
    request<{ decision_id: string; format: string; content: string; generated_at: string }>(
      `/report/${decisionId}/markdown`
    ),
  reportPdf: async (decisionId: string): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/report/${decisionId}/pdf`);
    if (!res.ok) throw new Error(`PDF export failed: ${res.status}`);
    return res.blob();
  },

  // Templates
  templates: () => request<TemplateInfo[]>('/templates'),
  template: (id: string) => request<TemplateDetail>(`/templates/${id}`),
  evaluateTemplate: (templateId: string, facts: Record<string, unknown>, evidence: Record<string, string>) =>
    request<DecisionPack>('/templates/evaluate', {
      method: 'POST',
      body: JSON.stringify({ template_id: templateId, facts, evidence }),
    }),

  // Policy Shifts
  policyShifts: () => request<PolicyShiftSummary[]>('/api/policy-shifts'),
  policyShiftCases: (shiftId: string) =>
    request<PolicyShiftDetail>(`/api/policy-shifts/${shiftId}/cases`),

  // Policy Simulation
  simulationDrafts: () => request<DraftShift[]>('/api/simulate/drafts'),
  simulate: (draftId: string) =>
    request<SimulationReport>('/api/simulate', {
      method: 'POST',
      body: JSON.stringify({ draft_id: draftId }),
    }),
  simulateCompare: (draftIds: string[]) =>
    request<SimulationReport[]>('/api/simulate/compare', {
      method: 'POST',
      body: JSON.stringify({ draft_ids: draftIds }),
    }),
};

export default api;
