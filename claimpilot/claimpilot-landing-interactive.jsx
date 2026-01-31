import React, { useState, useEffect, useCallback } from 'react';
import { Shield, CheckCircle2, XCircle, Zap, Ban, Timer, Calendar, FileText, Mail, ExternalLink, Car, Heart, Home, Briefcase, ClipboardCheck, Navigation, BookOpen, AlertCircle, ArrowRight, Lock, RotateCcw, Users, TrendingUp, CheckSquare, HelpCircle, Server, Layers, Play, RefreshCw, ChevronDown, Plus, X, Hash, Anchor, Ship } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Fallback demo data if API is unavailable
const FALLBACK_CASES = [
  {
    id: "auto-approve-standard",
    name: "Auto - Standard Collision (APPROVE)",
    line_of_business: "auto",
    policy_id: "CA-ON-OAP1-2024",
    expected_outcome: "pay",
    facts: [
      { field: "policy.status", value: "active" },
      { field: "driver.rideshare_app_active", value: false },
      { field: "vehicle.use_at_loss", value: "personal" },
      { field: "driver.bac_level", value: 0.0 },
      { field: "driver.impairment_indicated", value: false },
      { field: "driver.license_status", value: "valid" },
      { field: "driver.license_class_valid", value: true },
      { field: "loss.racing_activity", value: false },
      { field: "loss.intentional_indicators", value: false }
    ]
  },
  {
    id: "auto-deny-rideshare",
    name: "Auto - Rideshare Active (DENY)",
    line_of_business: "auto",
    policy_id: "CA-ON-OAP1-2024",
    expected_outcome: "deny",
    facts: [
      { field: "policy.status", value: "active" },
      { field: "driver.rideshare_app_active", value: true },
      { field: "vehicle.use_at_loss", value: "rideshare" },
      { field: "driver.bac_level", value: 0.0 },
      { field: "driver.impairment_indicated", value: false },
      { field: "loss.racing_activity", value: false }
    ]
  },
  {
    id: "auto-deny-dui",
    name: "Auto - DUI (DENY)",
    line_of_business: "auto",
    policy_id: "CA-ON-OAP1-2024",
    expected_outcome: "deny",
    facts: [
      { field: "policy.status", value: "active" },
      { field: "driver.bac_level", value: 0.12 },
      { field: "driver.impairment_indicated", value: true },
      { field: "police_report.impaired_charges", value: true }
    ]
  }
];

const SUGGESTED_FACTS = {
  auto: [
    { field: "vehicle.use_at_loss", type: "select", options: ["personal", "commercial", "rideshare"] },
    { field: "driver.rideshare_app_active", type: "boolean" },
    { field: "driver.bac_level", type: "number" },
    { field: "driver.impairment_indicated", type: "boolean" },
    { field: "driver.license_status", type: "select", options: ["valid", "suspended", "expired"] },
    { field: "driver.license_class_valid", type: "boolean" },
    { field: "loss.racing_activity", type: "boolean" },
    { field: "loss.intentional_indicators", type: "boolean" },
    { field: "police_report.impaired_charges", type: "boolean" }
  ],
  property: [
    { field: "loss.cause", type: "select", options: ["fire", "flood", "theft", "wind", "water"] },
    { field: "dwelling.days_vacant", type: "number" },
    { field: "dwelling.occupied", type: "boolean" },
    { field: "damage.gradual", type: "boolean" },
    { field: "maintenance.deferred", type: "boolean" }
  ],
  health: [
    { field: "drug.on_formulary", type: "boolean" },
    { field: "drug.prior_auth_approved", type: "boolean" },
    { field: "condition.preexisting", type: "boolean" },
    { field: "member.coverage_months", type: "number" },
    { field: "treatment.experimental", type: "boolean" }
  ],
  workers_comp: [
    { field: "injury.work_related", type: "boolean" },
    { field: "injury.arose_out_of_employment", type: "boolean" },
    { field: "injury.intoxication_sole_cause", type: "boolean" },
    { field: "injury.self_inflicted", type: "boolean" },
    { field: "employer.wsib_registered", type: "boolean" }
  ],
  liability: [
    { field: "occurrence.during_policy_period", type: "boolean" },
    { field: "injury.expected_intended", type: "boolean" },
    { field: "loss.pollution_related", type: "boolean" },
    { field: "loss.professional_services", type: "boolean" }
  ],
  marine: [
    { field: "vessel.seaworthy", type: "boolean" },
    { field: "operator.licensed", type: "boolean" },
    { field: "navigation.approved_waters", type: "boolean" },
    { field: "operator.intoxicated", type: "boolean" }
  ]
};

export default function ClaimPilotLanding() {
  const [showCalendly, setShowCalendly] = useState(false);
  const [demoCases, setDemoCases] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [facts, setFacts] = useState([]);
  const [evidence, setEvidence] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiAvailable, setApiAvailable] = useState(true);
  const [buildOwnMode, setBuildOwnMode] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState('CA-ON-OAP1-2024');
  const [lossType, setLossType] = useState('collision');
  const [showCaseDropdown, setShowCaseDropdown] = useState(false);

  // Load demo cases and policies on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        const [casesRes, policiesRes] = await Promise.all([
          fetch(`${API_URL}/demo/cases`),
          fetch(`${API_URL}/policies`)
        ]);

        if (casesRes.ok && policiesRes.ok) {
          const casesData = await casesRes.json();
          const policiesData = await policiesRes.json();
          setDemoCases(casesData);
          setPolicies(policiesData);
          setApiAvailable(true);

          // Auto-select first case
          if (casesData.length > 0) {
            selectCase(casesData[0]);
          }
        } else {
          throw new Error('API returned error');
        }
      } catch (err) {
        console.warn('API unavailable, using fallback data:', err);
        setApiAvailable(false);
        setDemoCases(FALLBACK_CASES);
        if (FALLBACK_CASES.length > 0) {
          selectCase(FALLBACK_CASES[0]);
        }
      }
    };
    loadData();
  }, []);

  const selectCase = (caseData) => {
    setSelectedCase(caseData);
    setBuildOwnMode(false);
    setFacts(caseData.facts.map(f => ({ ...f, id: Math.random().toString(36).substr(2, 9) })));
    setEvidence(caseData.evidence || []);
    setEvaluation(null);
    setShowCaseDropdown(false);
  };

  const startBuildOwn = () => {
    setBuildOwnMode(true);
    setSelectedCase(null);
    setFacts([{ id: '1', field: 'policy.status', value: 'active' }]);
    setEvidence([]);
    setEvaluation(null);
    setShowCaseDropdown(false);
  };

  const evaluateClaim = useCallback(async () => {
    setLoading(true);

    const policyId = buildOwnMode ? selectedPolicy : (selectedCase?.policy_id || 'CA-ON-OAP1-2024');

    const requestBody = {
      policy_id: policyId,
      loss_type: lossType,
      loss_date: new Date().toISOString().split('T')[0],
      report_date: new Date().toISOString().split('T')[0],
      facts: facts.map(f => ({
        field: f.field,
        value: f.value,
        certainty: 'confirmed'
      })),
      evidence: evidence.map(e => ({
        doc_type: e.doc_type || e,
        status: 'verified'
      }))
    };

    try {
      const res = await fetch(`${API_URL}/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });

      if (res.ok) {
        const data = await res.json();
        setEvaluation(data);
      } else {
        const errorText = await res.text();
        console.error('Evaluation error:', errorText);
        // Use fallback evaluation
        setEvaluation(createFallbackEvaluation(facts));
      }
    } catch (err) {
      console.error('API error:', err);
      setEvaluation(createFallbackEvaluation(facts));
    }

    setLoading(false);
  }, [facts, evidence, selectedCase, buildOwnMode, selectedPolicy, lossType]);

  const createFallbackEvaluation = (facts) => {
    const hasRideshare = facts.some(f => f.field === 'driver.rideshare_app_active' && f.value === true);
    const hasDUI = facts.some(f => f.field === 'driver.bac_level' && parseFloat(f.value) > 0.08);
    const hasImpairment = facts.some(f => f.field === 'driver.impairment_indicated' && f.value === true);

    if (hasRideshare) {
      return {
        claim_id: 'DEMO-' + Math.random().toString(36).substr(2, 8).toUpperCase(),
        recommended_disposition: 'deny',
        disposition_reason: 'Exclusion(s) triggered: 4.2.1',
        certainty: 'high',
        exclusions_triggered: ['4.2.1'],
        exclusions_evaluated: [{
          code: '4.2.1',
          name: 'Commercial Use',
          triggered: true,
          reason: 'Vehicle was being used for commercial rideshare purposes',
          policy_wording: 'We do not cover loss or damage that occurs while the automobile is used to carry passengers for compensation or hire, including but not limited to use with ride-sharing applications.'
        }],
        policy_pack_hash: 'demo-fallback-hash'
      };
    }

    if (hasDUI || hasImpairment) {
      return {
        claim_id: 'DEMO-' + Math.random().toString(36).substr(2, 8).toUpperCase(),
        recommended_disposition: 'deny',
        disposition_reason: 'Exclusion(s) triggered: 4.3.3',
        certainty: 'high',
        exclusions_triggered: ['4.3.3'],
        exclusions_evaluated: [{
          code: '4.3.3',
          name: 'Impaired Operation',
          triggered: true,
          reason: 'Driver was impaired at time of loss (BAC > 0.08)',
          policy_wording: 'We do not cover loss or damage that occurs while the automobile is operated by any person while under the influence of intoxicating liquor or drugs to such a degree as to be incapable of proper control of the automobile.'
        }],
        policy_pack_hash: 'demo-fallback-hash'
      };
    }

    return {
      claim_id: 'DEMO-' + Math.random().toString(36).substr(2, 8).toUpperCase(),
      recommended_disposition: 'pay',
      disposition_reason: 'Coverage applies, no exclusions triggered',
      certainty: 'high',
      exclusions_triggered: [],
      exclusions_evaluated: [
        { code: '4.2.1', name: 'Commercial Use', triggered: false, reason: 'Not triggered - personal use confirmed' },
        { code: '4.3.3', name: 'Impaired Operation', triggered: false, reason: 'Not triggered - no impairment indicated' }
      ],
      policy_pack_hash: 'demo-fallback-hash'
    };
  };

  const updateFact = (id, field, value) => {
    setFacts(prev => prev.map(f => f.id === id ? { ...f, [field]: value } : f));
  };

  const removeFact = (id) => {
    setFacts(prev => prev.filter(f => f.id !== id));
  };

  const addFact = (factDef) => {
    const defaultValue = factDef.type === 'boolean' ? false : factDef.type === 'number' ? 0 : factDef.options?.[0] || '';
    setFacts(prev => [...prev, { id: Math.random().toString(36).substr(2, 9), field: factDef.field, value: defaultValue }]);
  };

  const addCustomFact = () => {
    setFacts(prev => [...prev, { id: Math.random().toString(36).substr(2, 9), field: '', value: '' }]);
  };

  const scrollToSection = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  const linesOfBusiness = [
    { icon: Car, name: "Auto", title: "Auto Claims" },
    { icon: Home, name: "Property", title: "Property & Casualty" },
    { icon: Heart, name: "Health", title: "Health & Medical" },
    { icon: Briefcase, name: "Workers Comp", title: "Workers' Compensation" },
    { icon: Shield, name: "Liability", title: "Commercial Liability" },
    { icon: Ship, name: "Marine", title: "Marine & Pleasure Craft" }
  ];

  const getLineOfBusiness = (policyId) => {
    const policy = policies.find(p => p.id === policyId);
    return policy?.line_of_business || 'auto';
  };

  const currentLoB = buildOwnMode ? getLineOfBusiness(selectedPolicy) : (selectedCase?.line_of_business || 'auto');
  const suggestedFacts = SUGGESTED_FACTS[currentLoB] || SUGGESTED_FACTS.auto;
  const usedFields = new Set(facts.map(f => f.field));
  const availableFacts = suggestedFacts.filter(sf => !usedFields.has(sf.field));

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 bg-slate-950/90 backdrop-blur-sm border-b border-slate-800 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Navigation className="w-6 h-6 text-blue-400" />
            <span className="font-bold text-lg">ClaimPilot</span>
          </div>
          <div className="hidden md:flex items-center gap-6 text-sm">
            <button onClick={() => scrollToSection('problem')} className="text-slate-400 hover:text-white transition-colors">Why</button>
            <button onClick={() => scrollToSection('demo')} className="text-slate-400 hover:text-white transition-colors">Try It</button>
            <button onClick={() => scrollToSection('benefits')} className="text-slate-400 hover:text-white transition-colors">Benefits</button>
          </div>
          <button
            onClick={() => setShowCalendly(true)}
            className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Book a Demo
          </button>
        </div>
      </nav>

      {/* Calendly Modal */}
      {showCalendly && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setShowCalendly(false)}>
          <div className="bg-slate-900 rounded-xl p-6 max-w-md w-full" onClick={e => e.stopPropagation()}>
            <h3 className="text-xl font-semibold mb-4">Schedule a Demo</h3>
            <p className="text-slate-400 mb-6">
              See how ClaimPilot guides adjusters through rule-backed decisions.
            </p>
            <a
              href="https://calendly.com/YOUR_LINK_HERE"
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full bg-blue-500 hover:bg-blue-600 text-white text-center px-6 py-3 rounded-lg font-medium transition-colors mb-3"
            >
              Open Scheduling Page <ExternalLink className="w-4 h-4 inline ml-2" />
            </a>
            <button
              onClick={() => setShowCalendly(false)}
              className="block w-full text-slate-400 hover:text-white text-center py-2"
            >
              Maybe later
            </button>
          </div>
        </div>
      )}

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="flex flex-wrap justify-center gap-2 mb-6">
            <div className="inline-flex items-center gap-2 bg-blue-500/10 text-blue-400 px-4 py-2 rounded-full text-sm">
              <BookOpen className="w-4 h-4" />
              Rule-Guided Decisions
            </div>
            <div className="inline-flex items-center gap-2 bg-emerald-500/10 text-emerald-400 px-4 py-2 rounded-full text-sm">
              <CheckCircle2 className="w-4 h-4" />
              Adjuster Decides
            </div>
            <div className="inline-flex items-center gap-2 bg-red-500/10 text-red-400 px-4 py-2 rounded-full text-sm">
              <Ban className="w-4 h-4" />
              Zero LLM • Zero Hallucination
            </div>
          </div>

          <h1 className="text-5xl md:text-6xl font-bold mb-6 leading-tight">
            Make the Right Decision.<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">
              Every Time.
            </span>
          </h1>

          <p className="text-xl text-slate-400 mb-8 max-w-2xl mx-auto">
            ClaimPilot guides adjusters through policy rules, surfaces what needs to be checked,
            and ensures every decision is backed by the right evidence.
            <span className="text-slate-300"> The adjuster decides. We help them decide correctly.</span>
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
            <button
              onClick={() => setShowCalendly(true)}
              className="bg-blue-500 hover:bg-blue-600 text-white px-8 py-4 rounded-xl font-semibold text-lg transition-colors flex items-center justify-center gap-2"
            >
              <Calendar className="w-5 h-5" />
              Schedule Demo
            </button>
            <button
              onClick={() => scrollToSection('demo')}
              className="bg-slate-800 hover:bg-slate-700 text-white px-8 py-4 rounded-xl font-semibold text-lg transition-colors flex items-center justify-center gap-2"
            >
              <Play className="w-5 h-5" />
              Try It Now
            </button>
          </div>

          {/* Value Props */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto">
            <div className="bg-slate-800/50 rounded-lg p-4">
              <Navigation className="w-6 h-6 text-blue-400 mx-auto mb-2" />
              <div className="text-sm font-medium">Guided Workflow</div>
              <div className="text-xs text-slate-400">Policy rules surface automatically</div>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-4">
              <CheckSquare className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
              <div className="text-sm font-medium">Complete Decisions</div>
              <div className="text-xs text-slate-400">Nothing missed, nothing forgotten</div>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-4">
              <Users className="w-6 h-6 text-amber-400 mx-auto mb-2" />
              <div className="text-sm font-medium">Consistent Teams</div>
              <div className="text-xs text-slate-400">Same rules, every adjuster</div>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-4">
              <RotateCcw className="w-6 h-6 text-cyan-400 mx-auto mb-2" />
              <div className="text-sm font-medium">Clear Reasoning</div>
              <div className="text-xs text-slate-400">Always know why</div>
            </div>
          </div>
        </div>
      </section>

      {/* Problem Section */}
      <section id="problem" className="py-20 px-6 bg-slate-900/50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">The Claims Decision Challenge</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Adjusters make thousands of judgment calls. Without guidance, decisions vary.
              Wrong decisions cost money — in leakage, in overturns, in rework.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 mb-12">
            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-slate-400 flex items-center gap-2">
                <HelpCircle className="w-5 h-5" />
                Without Guidance
              </h3>
              {[
                "Adjusters interpret policy language differently",
                "Easy to miss an exclusion or coverage condition",
                "New adjusters don't know what experienced ones know",
                "Supervisors review after the fact, not during",
                "When questions arise later, reasoning is unclear"
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-3 bg-slate-800/50 rounded-lg p-4">
                  <div className="w-2 h-2 rounded-full bg-slate-500 mt-2" />
                  <span className="text-slate-400">{item}</span>
                </div>
              ))}
            </div>
            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-blue-400 flex items-center gap-2">
                <Navigation className="w-5 h-5" />
                With ClaimPilot
              </h3>
              {[
                "Policy rules guide every adjuster the same way",
                "System surfaces what to check — nothing missed",
                "Institutional knowledge built into the workflow",
                "Escalations happen at the right moment with full context",
                "Complete reasoning captured as decisions are made"
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-3 bg-slate-800/50 rounded-lg p-4">
                  <Zap className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                  <span className="text-slate-300">{item}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Key Insight */}
          <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-6 max-w-3xl mx-auto">
            <div className="text-center">
              <div className="text-blue-400 font-semibold mb-2">The ClaimPilot Principle</div>
              <p className="text-xl text-slate-200">
                "The adjuster decides. We guide and document."
              </p>
              <p className="text-slate-400 mt-3 text-sm">
                ClaimPilot doesn't replace judgment — it ensures judgment is informed,
                consistent, and captured. Your adjusters stay in control.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Interactive Demo Section */}
      <section id="demo" className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">Try It Now</h2>
            <p className="text-slate-400">
              Select a scenario or build your own. Toggle facts and see the recommendation change instantly.
            </p>
            {!apiAvailable && (
              <div className="mt-4 inline-flex items-center gap-2 bg-amber-500/10 text-amber-400 px-4 py-2 rounded-full text-sm">
                <AlertCircle className="w-4 h-4" />
                Demo mode — using sample data
              </div>
            )}
          </div>

          <div className="grid lg:grid-cols-2 gap-8">
            {/* Left Panel: Facts Input */}
            <div className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
              <div className="bg-slate-800 px-4 py-3 border-b border-slate-700">
                <div className="flex items-center justify-between">
                  <span className="font-medium">Claim Facts</span>

                  {/* Case Selector Dropdown */}
                  <div className="relative">
                    <button
                      onClick={() => setShowCaseDropdown(!showCaseDropdown)}
                      className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg text-sm transition-colors"
                    >
                      <span className="truncate max-w-[200px]">
                        {buildOwnMode ? 'Build Your Own' : (selectedCase?.name || 'Select Case')}
                      </span>
                      <ChevronDown className="w-4 h-4" />
                    </button>

                    {showCaseDropdown && (
                      <div className="absolute right-0 mt-2 w-72 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-10 max-h-80 overflow-y-auto">
                        <button
                          onClick={startBuildOwn}
                          className="w-full text-left px-4 py-3 hover:bg-slate-700 border-b border-slate-700 flex items-center gap-2"
                        >
                          <Plus className="w-4 h-4 text-blue-400" />
                          <span className="text-blue-400 font-medium">Build Your Own Case</span>
                        </button>
                        {demoCases.map(c => (
                          <button
                            key={c.id}
                            onClick={() => selectCase(c)}
                            className={`w-full text-left px-4 py-3 hover:bg-slate-700 ${selectedCase?.id === c.id ? 'bg-slate-700' : ''}`}
                          >
                            <div className="font-medium text-sm">{c.name}</div>
                            <div className="text-xs text-slate-500">{c.policy_id}</div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="p-4 space-y-4 max-h-[500px] overflow-y-auto">
                {/* Build Your Own Controls */}
                {buildOwnMode && (
                  <div className="space-y-3 pb-4 border-b border-slate-700">
                    <div>
                      <label className="text-xs text-slate-500 mb-1 block">Policy Pack</label>
                      <select
                        value={selectedPolicy}
                        onChange={(e) => setSelectedPolicy(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                      >
                        {policies.length > 0 ? (
                          policies.map(p => (
                            <option key={p.id} value={p.id}>{p.name} ({p.id})</option>
                          ))
                        ) : (
                          <option value="CA-ON-OAP1-2024">Ontario Auto OAP 1</option>
                        )}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-slate-500 mb-1 block">Loss Type</label>
                      <select
                        value={lossType}
                        onChange={(e) => setLossType(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                      >
                        <option value="collision">Collision</option>
                        <option value="comprehensive">Comprehensive</option>
                        <option value="fire">Fire</option>
                        <option value="theft">Theft</option>
                        <option value="water_damage">Water Damage</option>
                      </select>
                    </div>
                  </div>
                )}

                {/* Facts List */}
                <div className="space-y-2">
                  {facts.map(fact => {
                    const factDef = suggestedFacts.find(sf => sf.field === fact.field);
                    return (
                      <div key={fact.id} className="flex items-center gap-2 bg-slate-800 rounded-lg p-3">
                        {buildOwnMode ? (
                          <input
                            type="text"
                            value={fact.field}
                            onChange={(e) => updateFact(fact.id, 'field', e.target.value)}
                            className="flex-1 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm"
                            placeholder="field.name"
                          />
                        ) : (
                          <span className="flex-1 text-sm text-slate-300">{fact.field}</span>
                        )}

                        {/* Value Input */}
                        {factDef?.type === 'boolean' || typeof fact.value === 'boolean' ? (
                          <div className="flex gap-1">
                            <button
                              onClick={() => updateFact(fact.id, 'value', true)}
                              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                                fact.value === true
                                  ? 'bg-emerald-500 text-white'
                                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                              }`}
                            >
                              Yes
                            </button>
                            <button
                              onClick={() => updateFact(fact.id, 'value', false)}
                              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                                fact.value === false
                                  ? 'bg-red-500 text-white'
                                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                              }`}
                            >
                              No
                            </button>
                          </div>
                        ) : factDef?.type === 'select' ? (
                          <select
                            value={fact.value}
                            onChange={(e) => updateFact(fact.id, 'value', e.target.value)}
                            className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm"
                          >
                            {factDef.options.map(opt => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                        ) : factDef?.type === 'number' ? (
                          <input
                            type="number"
                            value={fact.value}
                            onChange={(e) => updateFact(fact.id, 'value', parseFloat(e.target.value) || 0)}
                            className="w-20 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-right"
                            step="0.01"
                          />
                        ) : (
                          <input
                            type="text"
                            value={fact.value}
                            onChange={(e) => updateFact(fact.id, 'value', e.target.value)}
                            className="w-32 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm"
                          />
                        )}

                        {buildOwnMode && (
                          <button
                            onClick={() => removeFact(fact.id)}
                            className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Quick Add Facts */}
                {buildOwnMode && availableFacts.length > 0 && (
                  <div className="pt-4 border-t border-slate-700">
                    <div className="text-xs text-slate-500 mb-2">Quick add:</div>
                    <div className="flex flex-wrap gap-2">
                      {availableFacts.slice(0, 5).map(sf => (
                        <button
                          key={sf.field}
                          onClick={() => addFact(sf)}
                          className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 px-2 py-1 rounded text-xs transition-colors"
                        >
                          <Plus className="w-3 h-3" />
                          {sf.field.split('.').pop()}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {buildOwnMode && (
                  <button
                    onClick={addCustomFact}
                    className="w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 border border-dashed border-slate-600 py-2 rounded-lg text-sm text-slate-400 transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                    Add Custom Fact
                  </button>
                )}
              </div>

              <div className="px-4 py-3 bg-slate-800 border-t border-slate-700">
                <button
                  onClick={evaluateClaim}
                  disabled={loading}
                  className="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-blue-500/50 text-white py-3 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Evaluating...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      Evaluate Claim
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Right Panel: Recommendation */}
            <div className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
              <div className="bg-slate-800 px-4 py-3 border-b border-slate-700 flex items-center justify-between">
                <span className="font-medium">Recommendation</span>
                {evaluation && (
                  <span className="text-xs text-slate-500 font-mono">{evaluation.claim_id}</span>
                )}
              </div>

              <div className="p-4 space-y-4 max-h-[500px] overflow-y-auto">
                {!evaluation ? (
                  <div className="text-center py-12 text-slate-500">
                    <Navigation className="w-12 h-12 mx-auto mb-4 opacity-30" />
                    <p>Click "Evaluate Claim" to see the recommendation</p>
                    <p className="text-sm mt-2">Or toggle facts above and watch it change</p>
                  </div>
                ) : (
                  <>
                    {/* Main Recommendation */}
                    <div className={`rounded-xl p-6 ${
                      evaluation.recommended_disposition === 'pay'
                        ? 'bg-emerald-500/10 border border-emerald-500/30'
                        : evaluation.recommended_disposition === 'deny'
                        ? 'bg-red-500/10 border border-red-500/30'
                        : 'bg-amber-500/10 border border-amber-500/30'
                    }`}>
                      <div className="flex items-center gap-3 mb-3">
                        {evaluation.recommended_disposition === 'pay' ? (
                          <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                        ) : evaluation.recommended_disposition === 'deny' ? (
                          <XCircle className="w-8 h-8 text-red-400" />
                        ) : (
                          <AlertCircle className="w-8 h-8 text-amber-400" />
                        )}
                        <div>
                          <div className={`text-2xl font-bold ${
                            evaluation.recommended_disposition === 'pay'
                              ? 'text-emerald-400'
                              : evaluation.recommended_disposition === 'deny'
                              ? 'text-red-400'
                              : 'text-amber-400'
                          }`}>
                            {evaluation.recommended_disposition === 'pay' ? 'APPROVE' :
                             evaluation.recommended_disposition === 'deny' ? 'DENY' : 'REQUEST INFO'}
                          </div>
                          <div className="text-sm text-slate-400">
                            Certainty: {evaluation.certainty}
                          </div>
                        </div>
                      </div>
                      <p className="text-slate-300">{evaluation.disposition_reason}</p>
                    </div>

                    {/* Exclusions Evaluated */}
                    {evaluation.exclusions_evaluated && evaluation.exclusions_evaluated.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium text-slate-400 mb-3">Exclusions Evaluated</h4>
                        <div className="space-y-2">
                          {evaluation.exclusions_evaluated.map((exc, i) => (
                            <div
                              key={i}
                              className={`rounded-lg p-3 ${
                                exc.triggered
                                  ? 'bg-red-500/10 border border-red-500/20'
                                  : 'bg-slate-800 border border-slate-700'
                              }`}
                            >
                              <div className="flex items-start gap-2">
                                {exc.triggered ? (
                                  <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                                ) : (
                                  <CheckCircle2 className="w-4 h-4 text-slate-500 mt-0.5 flex-shrink-0" />
                                )}
                                <div className="flex-1 min-w-0">
                                  <div className={`font-medium text-sm ${exc.triggered ? 'text-red-400' : 'text-slate-400'}`}>
                                    {exc.code} — {exc.name}
                                  </div>
                                  <div className="text-xs text-slate-500 mt-1">{exc.reason}</div>

                                  {exc.triggered && exc.policy_wording && (
                                    <div className="mt-3 bg-slate-900 rounded p-3 border-l-2 border-red-500">
                                      <div className="text-xs text-slate-500 mb-1">Policy Wording:</div>
                                      <p className="text-sm text-slate-300 italic">"{exc.policy_wording}"</p>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Provenance */}
                    {evaluation.policy_pack_hash && (
                      <div className="pt-4 border-t border-slate-700">
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <Hash className="w-3 h-3" />
                          <span>Policy Pack Hash: {evaluation.policy_pack_hash.substring(0, 16)}...</span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                          <Lock className="w-3 h-3" />
                          <span>Deterministic • Reproducible • Auditable</span>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>

          {/* The "Aha" Moment Hint */}
          <div className="mt-8 bg-blue-500/5 border border-blue-500/20 rounded-xl p-6 max-w-2xl mx-auto">
            <div className="flex items-start gap-4">
              <Zap className="w-6 h-6 text-blue-400 flex-shrink-0 mt-1" />
              <div>
                <h4 className="font-semibold text-blue-400 mb-2">Try This</h4>
                <p className="text-slate-400 text-sm">
                  Select the "Auto - Standard Collision" case (shows <span className="text-emerald-400">APPROVE</span>),
                  then toggle <code className="bg-slate-800 px-1.5 py-0.5 rounded text-xs">rideshare_app_active</code> to <span className="text-emerald-400">Yes</span>.
                  Watch it instantly change to <span className="text-red-400">DENY</span> with the policy wording cited.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section id="benefits" className="py-20 px-6 bg-slate-900/50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">Fewer Wrong Decisions</h2>
            <p className="text-slate-400">
              The right decision, made consistently, documented automatically
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 mb-12">
            <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700">
              <TrendingUp className="w-8 h-8 text-emerald-400 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Reduce Leakage</h3>
              <p className="text-slate-400 text-sm">
                When adjusters consistently apply coverage rules and exclusions,
                you pay what you owe — not more.
              </p>
            </div>
            <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700">
              <RotateCcw className="w-8 h-8 text-blue-400 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Fewer Overturns</h3>
              <p className="text-slate-400 text-sm">
                Decisions backed by complete evidence and clear reasoning
                hold up to scrutiny — internal and external.
              </p>
            </div>
            <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700">
              <Timer className="w-8 h-8 text-amber-400 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Faster Cycle Time</h3>
              <p className="text-slate-400 text-sm">
                Guided workflows eliminate guesswork. Adjusters know exactly
                what to check and when to escalate.
              </p>
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700">
              <Users className="w-8 h-8 text-cyan-400 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Onboard Faster</h3>
              <p className="text-slate-400 text-sm">
                New adjusters get institutional knowledge built into their workflow.
                Expertise isn't locked in senior heads.
              </p>
            </div>
            <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700">
              <BookOpen className="w-8 h-8 text-purple-400 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Always Know Why</h3>
              <p className="text-slate-400 text-sm">
                Every decision includes the reasoning chain. Questions months later?
                The answer is already documented.
              </p>
            </div>
            <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700">
              <Shield className="w-8 h-8 text-rose-400 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Support Gray Areas</h3>
              <p className="text-slate-400 text-sm">
                Not everything is black and white. ClaimPilot supports "requires judgment"
                and "escalate for interpretation" — your discretion, documented.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Lines of Business */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-4">Works Across Lines</h2>
          <p className="text-slate-400 mb-8">
            ClaimPilot adapts to your policy forms, coverage rules, and escalation paths
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            {linesOfBusiness.map((line) => (
              <div
                key={line.name}
                className="flex items-center gap-3 bg-slate-800/50 px-6 py-4 rounded-xl border border-slate-700"
              >
                <line.icon className="w-6 h-6 text-blue-400" />
                <span className="font-medium">{line.title}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Why No LLM Section */}
      <section className="py-20 px-6 bg-slate-900/50">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 bg-red-500/10 text-red-400 px-4 py-2 rounded-full text-sm mb-4">
              <Ban className="w-4 h-4" />
              No AI Guessing
            </div>
            <h2 className="text-3xl font-bold mb-4">Why ClaimPilot Uses Zero LLM</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              AI assistants can be helpful — but not for decisions that must be consistent,
              explainable, and reproducible.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 mb-8">
            <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-red-500/20 rounded-lg">
                  <AlertCircle className="w-6 h-6 text-red-400" />
                </div>
                <h3 className="text-lg font-semibold text-red-400">LLM/AI-Assisted Tools</h3>
              </div>
              <div className="space-y-3">
                {[
                  { title: "Hallucinations", desc: "Can confidently suggest wrong policy interpretation" },
                  { title: "Inconsistent", desc: "Same claim details may get different guidance tomorrow" },
                  { title: "Unexplainable", desc: "Can't show exactly why it suggested something" },
                  { title: "Training drift", desc: "Model updates silently change behavior" },
                  { title: "Black box", desc: "When asked 'why?' — there's no clear answer" }
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <XCircle className="w-4 h-4 text-red-400 mt-1 flex-shrink-0" />
                    <div>
                      <span className="text-red-300 font-medium">{item.title}:</span>
                      <span className="text-slate-400 text-sm ml-1">{item.desc}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-emerald-500/20 rounded-lg">
                  <Shield className="w-6 h-6 text-emerald-400" />
                </div>
                <h3 className="text-lg font-semibold text-emerald-400">ClaimPilot (Deterministic)</h3>
              </div>
              <div className="space-y-3">
                {[
                  { title: "No hallucinations", desc: "Rules are explicit — what you encode is what you get" },
                  { title: "100% consistent", desc: "Same inputs always produce identical guidance" },
                  { title: "Fully explainable", desc: "Every suggestion traces to a specific rule" },
                  { title: "Version controlled", desc: "Rule changes are deliberate and tracked" },
                  { title: "Clear reasoning", desc: "Always know exactly why — show the chain" }
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-1 flex-shrink-0" />
                    <div>
                      <span className="text-emerald-300 font-medium">{item.title}:</span>
                      <span className="text-slate-400 text-sm ml-1">{item.desc}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-6 max-w-3xl mx-auto">
            <div className="text-center">
              <p className="text-slate-300">
                <span className="text-blue-400 font-semibold">The bottom line:</span> When an adjuster
                follows ClaimPilot's guidance, you can show exactly which rule applied and why.
                No "the AI thought so." No unexplainable suggestions. Just clear, traceable logic.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-4">See ClaimPilot in Action</h2>
          <p className="text-slate-400 mb-8 max-w-xl mx-auto">
            We'll walk through a real claim scenario for your line of business.
            See how guided decisions actually work.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
            <button
              onClick={() => setShowCalendly(true)}
              className="bg-blue-500 hover:bg-blue-600 text-white px-8 py-4 rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
            >
              <Calendar className="w-5 h-5" />
              Book a Demo
            </button>
            <a
              href="mailto:hello@claimpilot.io"
              className="bg-slate-800 hover:bg-slate-700 text-white px-8 py-4 rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
            >
              <Mail className="w-5 h-5" />
              Contact Us
            </a>
          </div>

          <div className="flex flex-wrap justify-center gap-6 text-sm text-slate-500">
            <span className="flex items-center gap-2">
              <Shield className="w-4 h-4" />
              Works with your existing claims system
            </span>
            <span className="flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Your policy forms, your rules
            </span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-slate-800">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Navigation className="w-5 h-5 text-blue-400" />
            <span className="font-semibold">ClaimPilot</span>
            <span className="text-slate-500 text-sm">© 2026</span>
          </div>
          <div className="flex gap-6 text-sm text-slate-500">
            <a href="#" className="hover:text-white transition-colors">Documentation</a>
            <a href="#" className="hover:text-white transition-colors">Privacy</a>
            <a href="#" className="hover:text-white transition-colors">Terms</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
