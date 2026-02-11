// =============================================================================
// Domain detection — fetches /api/domain once and provides context
// =============================================================================

import { createContext, useContext } from 'react';
import { useQuery } from '@tanstack/react-query';

export interface DomainInfo {
  domain: string;
  name: string;
  terminology: {
    entity: string;
    institution: string;
    decision_maker: string;
    review_process: string;
    escalation_target: string;
    filing_authority: string;
  };
}

// Defaults (banking) used before /api/domain resolves
const BANKING_DEFAULT: DomainInfo = {
  domain: 'banking_aml',
  name: 'DecisionGraph',
  terminology: {
    entity: 'transaction',
    institution: 'bank',
    decision_maker: 'compliance officer',
    review_process: 'investigation',
    escalation_target: 'MLRO',
    filing_authority: 'FINTRAC',
  },
};

// Branding config derived from domain
export interface DomainBranding {
  logo: string;
  title: string;
  subtitle: string;
  footerLine1: string;
  footerLine2: string;
  dashboardHeading: string;
  dashboardSub: string;
}

function deriveBranding(d: DomainInfo): DomainBranding {
  if (d.domain === 'insurance_claims') {
    return {
      logo: 'CP',
      title: 'ClaimPilot',
      subtitle: 'Core v1.3 — Insurance',
      footerLine1: 'Claims Intelligence Engine',
      footerLine2: `FSRA / ${d.terminology.filing_authority}`,
      dashboardHeading: 'ClaimPilot Insurance Decision Engine — Overview',
      dashboardSub: 'Claims Intelligence Engine',
    };
  }
  // Banking / default
  return {
    logo: 'DG',
    title: 'DecisionGraph',
    subtitle: 'Core v1.3 — AML',
    footerLine1: 'Bank-Grade Compliance Engine',
    footerLine2: 'PCMLTFA / FINTRAC',
    dashboardHeading: 'DecisionGraph AML Decision Engine — Overview',
    dashboardSub: 'Bank-Grade Compliance Engine',
  };
}

export const DomainContext = createContext<{
  info: DomainInfo;
  branding: DomainBranding;
  isInsurance: boolean;
}>({
  info: BANKING_DEFAULT,
  branding: deriveBranding(BANKING_DEFAULT),
  isInsurance: false,
});

export function useDomain() {
  return useContext(DomainContext);
}

export function useDomainQuery() {
  return useQuery<DomainInfo>({
    queryKey: ['domain'],
    queryFn: async () => {
      try {
        const res = await fetch('/api/domain');
        if (!res.ok) return BANKING_DEFAULT;
        return await res.json();
      } catch {
        return BANKING_DEFAULT;
      }
    },
    staleTime: Infinity,
  });
}

export { BANKING_DEFAULT, deriveBranding };
