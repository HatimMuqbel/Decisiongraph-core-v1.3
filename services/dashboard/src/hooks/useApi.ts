// =============================================================================
// React Query Hooks — type-safe data fetching for all API endpoints
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../api/client';

// ── Health / Info ───────────────────────────────────────────────────────────

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 30_000 });
}

export function useReady() {
  return useQuery({ queryKey: ['ready'], queryFn: api.ready, retry: false });
}

export function useVersion() {
  return useQuery({ queryKey: ['version'], queryFn: api.version, staleTime: 60_000 });
}

// ── Demo Cases ──────────────────────────────────────────────────────────────

export function useDemoCases(category?: string) {
  return useQuery({
    queryKey: ['demoCases', category],
    queryFn: () => api.demoCases(category),
    staleTime: 5 * 60_000,
  });
}

export function useDemoCase(id: string) {
  return useQuery({
    queryKey: ['demoCase', id],
    queryFn: () => api.demoCase(id),
    enabled: !!id,
  });
}

// ── Decisions ───────────────────────────────────────────────────────────────

export function useDecide() {
  return useMutation({
    mutationFn: (caseData: Record<string, unknown>) => api.decide(caseData),
  });
}

// ── Reports ─────────────────────────────────────────────────────────────────

export function useReportJson(decisionId: string, includeRaw = false) {
  return useQuery({
    queryKey: ['report', decisionId, includeRaw],
    queryFn: () => api.reportJson(decisionId, includeRaw),
    enabled: !!decisionId,
    staleTime: Infinity,
  });
}

export function useReportMarkdown(decisionId: string) {
  return useQuery({
    queryKey: ['reportMd', decisionId],
    queryFn: () => api.reportMarkdown(decisionId),
    enabled: !!decisionId,
    staleTime: Infinity,
  });
}

export function useReportPdf() {
  return useMutation({
    mutationFn: (decisionId: string) => api.reportPdf(decisionId),
  });
}

// ── Templates ───────────────────────────────────────────────────────────────

export function useTemplates() {
  return useQuery({
    queryKey: ['templates'],
    queryFn: api.templates,
    staleTime: 5 * 60_000,
  });
}

export function useTemplate(id: string) {
  return useQuery({
    queryKey: ['template', id],
    queryFn: () => api.template(id),
    enabled: !!id,
  });
}

export function useEvaluateTemplate() {
  return useMutation({
    mutationFn: ({
      templateId,
      facts,
      evidence,
    }: {
      templateId: string;
      facts: Record<string, unknown>;
      evidence: Record<string, string>;
    }) => api.evaluateTemplate(templateId, facts, evidence),
  });
}

// ── Policy Shifts ───────────────────────────────────────────────────────────

export function usePolicyShifts() {
  return useQuery({
    queryKey: ['policyShifts'],
    queryFn: api.policyShifts,
    staleTime: 5 * 60_000,
  });
}

export function usePolicyShiftCases(shiftId: string) {
  return useQuery({
    queryKey: ['policyShiftCases', shiftId],
    queryFn: () => api.policyShiftCases(shiftId),
    enabled: !!shiftId,
    staleTime: 5 * 60_000,
  });
}
