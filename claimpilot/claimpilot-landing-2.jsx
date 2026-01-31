import React, { useState } from 'react';
import { Shield, CheckCircle2, XCircle, Zap, Ban, Timer, Calendar, FileText, Mail, ExternalLink, Car, Heart, Home, Briefcase, ClipboardCheck, Navigation, BookOpen, AlertCircle, ArrowRight, Lock, RotateCcw, Users, TrendingUp, CheckSquare, HelpCircle, Server, Layers } from 'lucide-react';

export default function ClaimPilot() {
  const [showCalendly, setShowCalendly] = useState(false);
  const [activeLine, setActiveLine] = useState(0);
  const [demoStep, setDemoStep] = useState(0);

  const linesOfBusiness = [
    { icon: Car, name: "Auto", title: "Auto Claims" },
    { icon: Home, name: "Property", title: "Property & Casualty" },
    { icon: Heart, name: "Health", title: "Health & Medical" },
    { icon: Briefcase, name: "Workers Comp", title: "Workers' Compensation" }
  ];

  const demoSteps = [
    {
      title: "Claim Context",
      subtitle: "System recognizes what rules apply",
      content: (
        <div className="space-y-4">
          <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
            <div className="text-sm text-slate-400 mb-2">Claim Identified</div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-slate-500">Province:</span> <span className="text-white">Ontario</span></div>
              <div><span className="text-slate-500">Policy:</span> <span className="text-white">OAP 1</span></div>
              <div><span className="text-slate-500">Loss Type:</span> <span className="text-white">Collision</span></div>
              <div><span className="text-slate-500">Claimant:</span> <span className="text-white">Insured Driver</span></div>
            </div>
          </div>
          <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Navigation className="w-5 h-5 text-blue-400 mt-0.5" />
              <div>
                <div className="text-blue-400 font-medium">Ontario OAP 1 – Collision Coverage</div>
                <div className="text-sm text-slate-400 mt-1">
                  Coverage potentially applies • 4 exclusions to assess • Day 0 of 60
                </div>
              </div>
            </div>
          </div>
        </div>
      )
    },
    {
      title: "Coverage Checklist",
      subtitle: "Guided verification of preconditions",
      content: (
        <div className="space-y-4">
          <div className="text-sm text-slate-400 mb-2">Step 1: Coverage Preconditions</div>
          <div className="space-y-2">
            {[
              { text: "Policy active at time of loss", checked: true },
              { text: "Premiums paid", checked: true },
              { text: "Vehicle listed on policy", checked: true }
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-3 bg-slate-800 rounded-lg p-3">
                <div className={`w-5 h-5 rounded flex items-center justify-center ${item.checked ? 'bg-emerald-500' : 'bg-slate-700'}`}>
                  {item.checked && <CheckCircle2 className="w-4 h-4 text-white" />}
                </div>
                <span className="text-slate-300">{item.text}</span>
                {item.checked && <span className="text-xs text-emerald-400 ml-auto">Verified</span>}
              </div>
            ))}
          </div>
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3 text-sm">
            <span className="text-emerald-400">✓ Preconditions met.</span>
            <span className="text-slate-400 ml-2">Proceeding to exclusion review.</span>
          </div>
        </div>
      )
    },
    {
      title: "Exclusion Navigator",
      subtitle: "Policy rules surface what to check",
      content: (
        <div className="space-y-4">
          <div className="text-sm text-slate-400 mb-2">Based on loss type + province, review these exclusions:</div>
          <div className="space-y-2">
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-amber-400" />
              <div className="flex-1">
                <div className="text-amber-400 font-medium">Exclusion 4.2.1 – Commercial use</div>
                <div className="text-xs text-slate-400">Requires verification</div>
              </div>
              <ArrowRight className="w-4 h-4 text-amber-400" />
            </div>
            <div className="bg-slate-800 rounded-lg p-3 flex items-center gap-3 opacity-60">
              <CheckCircle2 className="w-5 h-5 text-slate-500" />
              <div className="flex-1">
                <div className="text-slate-400">Exclusion 4.3.3 – Impaired driving</div>
                <div className="text-xs text-slate-500">Not indicated</div>
              </div>
            </div>
            <div className="bg-slate-800 rounded-lg p-3 flex items-center gap-3 opacity-60">
              <CheckCircle2 className="w-5 h-5 text-slate-500" />
              <div className="flex-1">
                <div className="text-slate-400">Exclusion 4.5.1 – Racing</div>
                <div className="text-xs text-slate-500">Not indicated</div>
              </div>
            </div>
          </div>
          <div className="bg-slate-800 border border-slate-600 rounded-lg p-4 mt-4">
            <div className="text-sm text-slate-400 mb-2">To rule out Commercial Use, confirm:</div>
            <div className="text-white">"Was vehicle used for compensation at time of loss?"</div>
          </div>
        </div>
      )
    },
    {
      title: "Fact Capture",
      subtitle: "Adjuster records what they learn",
      content: (
        <div className="space-y-4">
          <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
            <div className="text-sm text-slate-400 mb-3">Evidence Collected</div>
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <FileText className="w-4 h-4 text-blue-400 mt-1" />
                <div>
                  <div className="text-slate-300 text-sm">Driver Statement</div>
                  <div className="text-slate-500 text-xs">"Was doing Uber at time of loss"</div>
                </div>
              </div>
            </div>
          </div>
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <XCircle className="w-5 h-5 text-red-400 mt-0.5" />
              <div>
                <div className="text-red-400 font-medium">Exclusion 4.2.1 Applies</div>
                <div className="text-sm text-slate-400 mt-1">
                  Commercial use confirmed by driver statement. Coverage excluded under policy section 4.2.1.
                </div>
              </div>
            </div>
          </div>
          <div className="text-xs text-slate-500 flex items-center gap-2">
            <Lock className="w-3 h-3" />
            Reasoning chain recorded with timestamp
          </div>
        </div>
      )
    },
    {
      title: "Documentation Gate",
      subtitle: "System ensures completeness before decision",
      content: (
        <div className="space-y-4">
          <div className="text-sm text-slate-400 mb-2">To support decision under Exclusion 4.2.1, collect:</div>
          <div className="space-y-2">
            {[
              { text: "Police report", checked: true },
              { text: "Driver statement confirming commercial use", checked: true },
              { text: "App activity screenshot (if available)", checked: false, optional: true }
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-3 bg-slate-800 rounded-lg p-3">
                <div className={`w-5 h-5 rounded flex items-center justify-center ${item.checked ? 'bg-emerald-500' : 'bg-slate-700 border border-slate-600'}`}>
                  {item.checked && <CheckCircle2 className="w-4 h-4 text-white" />}
                </div>
                <span className={item.checked ? 'text-slate-300' : 'text-slate-500'}>{item.text}</span>
                {item.optional && <span className="text-xs text-slate-600 ml-auto">Optional</span>}
              </div>
            ))}
          </div>
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <span className="text-emerald-400 text-sm">Required documentation complete</span>
              <button className="bg-emerald-500 text-white px-4 py-1.5 rounded text-sm font-medium">
                Proceed to Decision
              </button>
            </div>
          </div>
        </div>
      )
    },
    {
      title: "Decision & Approval",
      subtitle: "Right decision, properly authorized",
      content: (
        <div className="space-y-4">
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Users className="w-5 h-5 text-amber-400 mt-0.5" />
              <div>
                <div className="text-amber-400 font-medium">Supervisor Review Required</div>
                <div className="text-sm text-slate-400 mt-1">
                  Denial decision • Exclusion-based • Escalated per authority matrix
                </div>
              </div>
            </div>
          </div>
          <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
            <div className="text-sm text-slate-400 mb-3">Supervisor sees:</div>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-blue-400" />
                <span className="text-slate-300">Complete reasoning chain</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-blue-400" />
                <span className="text-slate-300">All required evidence attached</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-blue-400" />
                <span className="text-slate-300">Policy section cited</span>
              </div>
            </div>
          </div>
          <div className="flex gap-3">
            <button className="flex-1 bg-emerald-500 text-white py-2 rounded-lg font-medium">
              Approve Decision
            </button>
            <button className="flex-1 bg-slate-700 text-slate-300 py-2 rounded-lg font-medium">
              Request Changes
            </button>
          </div>
        </div>
      )
    }
  ];

  const scrollToSection = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

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
            <button onClick={() => scrollToSection('demo')} className="text-slate-400 hover:text-white transition-colors">How It Works</button>
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
              <ClipboardCheck className="w-5 h-5" />
              See How It Works
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

      {/* What Legacy Systems Miss */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">What Your Claims System Wasn't Built For</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Guidewire, Duck Creek, and legacy systems handle transactions. 
              But the <span className="text-slate-200">decision quality</span> gap remains wide open.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 mb-12">
            {/* What Legacy Systems Do */}
            <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-slate-700 rounded-lg">
                  <Server className="w-6 h-6 text-slate-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold">Your Core System</h3>
                  <p className="text-sm text-slate-500">What it does well</p>
                </div>
              </div>
              <div className="space-y-3">
                {[
                  { text: "Store claim data and documents", check: true },
                  { text: "Route work to adjusters", check: true },
                  { text: "Process payments", check: true },
                  { text: "Generate reports and dashboards", check: true },
                  { text: "Track claim status and timelines", check: true },
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    <span className="text-slate-300">{item.text}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* What's Missing */}
            <div className="bg-red-500/5 rounded-xl p-6 border border-red-500/20">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-red-500/20 rounded-lg">
                  <AlertCircle className="w-6 h-6 text-red-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-red-400">The Gap</h3>
                  <p className="text-sm text-slate-500">What it doesn't do</p>
                </div>
              </div>
              <div className="space-y-3">
                {[
                  { text: "Guide adjusters through policy rules in real-time" },
                  { text: "Surface which exclusions to check for this loss type" },
                  { text: "Ensure required evidence is collected before decisions" },
                  { text: "Capture the reasoning chain as decisions are made" },
                  { text: "Enforce consistency across adjusters" },
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <XCircle className="w-5 h-5 text-red-400" />
                    <span className="text-slate-400">{item.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* The Result */}
          <div className="bg-slate-800/50 rounded-xl p-8 border border-slate-700">
            <h3 className="text-lg font-semibold mb-6 text-center">The Result: Decision Quality Problems</h3>
            <div className="grid md:grid-cols-4 gap-6">
              <div className="text-center">
                <div className="text-3xl font-bold text-red-400 mb-2">23%</div>
                <div className="text-sm text-slate-400">of denials overturned on appeal</div>
                <div className="text-xs text-slate-500 mt-1">Industry average</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-red-400 mb-2">3-5x</div>
                <div className="text-sm text-slate-400">variation in decisions on similar claims</div>
                <div className="text-xs text-slate-500 mt-1">Between adjusters</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-red-400 mb-2">40%</div>
                <div className="text-sm text-slate-400">of adjuster time on rework</div>
                <div className="text-xs text-slate-500 mt-1">Missing info, incomplete files</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-red-400 mb-2">???</div>
                <div className="text-sm text-slate-400">"Why was this denied?"</div>
                <div className="text-xs text-slate-500 mt-1">Can't answer months later</div>
              </div>
            </div>
          </div>

          {/* How ClaimPilot Fills the Gap */}
          <div className="mt-12">
            <h3 className="text-lg font-semibold mb-6 text-center">ClaimPilot Fills the Gap</h3>
            <div className="grid md:grid-cols-3 gap-6">
              <div className="bg-blue-500/10 rounded-xl p-6 border border-blue-500/20">
                <div className="flex items-center gap-3 mb-4">
                  <Navigation className="w-6 h-6 text-blue-400" />
                  <h4 className="font-semibold">Decision Guidance</h4>
                </div>
                <p className="text-sm text-slate-400">
                  Policy rules surface automatically based on claim context. 
                  Adjusters see exactly what to check — exclusions, conditions, required evidence.
                </p>
              </div>
              <div className="bg-blue-500/10 rounded-xl p-6 border border-blue-500/20">
                <div className="flex items-center gap-3 mb-4">
                  <Lock className="w-6 h-6 text-blue-400" />
                  <h4 className="font-semibold">Reasoning Capture</h4>
                </div>
                <p className="text-sm text-slate-400">
                  Every decision includes the complete chain: which rules applied, 
                  what evidence supported it, who approved it. No reconstruction needed.
                </p>
              </div>
              <div className="bg-blue-500/10 rounded-xl p-6 border border-blue-500/20">
                <div className="flex items-center gap-3 mb-4">
                  <Users className="w-6 h-6 text-blue-400" />
                  <h4 className="font-semibold">Consistency Enforcement</h4>
                </div>
                <p className="text-sm text-slate-400">
                  Same claim facts → same guidance → same rules applied. 
                  Whether it's a new adjuster or a 20-year veteran.
                </p>
              </div>
            </div>
          </div>

          {/* Integration Note */}
          <div className="mt-8 bg-slate-800/30 rounded-lg p-4 flex items-center justify-center gap-3 text-sm text-slate-400">
            <Layers className="w-5 h-5" />
            <span>ClaimPilot works alongside your existing claims system — not instead of it.</span>
          </div>
        </div>
      </section>

      {/* Demo Walkthrough */}
      <section id="demo" className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">How It Works</h2>
            <p className="text-slate-400">
              A real claim workflow: Ontario auto collision, step by step
            </p>
          </div>

          <div className="grid md:grid-cols-5 gap-8">
            {/* Step Selector */}
            <div className="md:col-span-2 space-y-2">
              {demoSteps.map((step, i) => (
                <button
                  key={i}
                  onClick={() => setDemoStep(i)}
                  className={`w-full text-left p-4 rounded-lg transition-all ${
                    demoStep === i 
                      ? 'bg-blue-500/20 border border-blue-500/40' 
                      : 'bg-slate-800/50 border border-transparent hover:bg-slate-800'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                      demoStep === i ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-400'
                    }`}>
                      {i + 1}
                    </div>
                    <div>
                      <div className={`font-medium ${demoStep === i ? 'text-white' : 'text-slate-300'}`}>
                        {step.title}
                      </div>
                      <div className="text-xs text-slate-500">{step.subtitle}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Step Content */}
            <div className="md:col-span-3">
              <div className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
                <div className="bg-slate-800 px-4 py-3 border-b border-slate-700 flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <div className="w-3 h-3 rounded-full bg-amber-500" />
                  <div className="w-3 h-3 rounded-full bg-emerald-500" />
                  <span className="text-slate-400 text-sm ml-2">ClaimPilot — Claim #2024-0847</span>
                </div>
                <div className="p-6">
                  <h3 className="text-lg font-semibold mb-1">{demoSteps[demoStep].title}</h3>
                  <p className="text-sm text-slate-400 mb-6">{demoSteps[demoStep].subtitle}</p>
                  {demoSteps[demoStep].content}
                </div>
              </div>

              {/* Navigation */}
              <div className="flex justify-between mt-4">
                <button
                  onClick={() => setDemoStep(Math.max(0, demoStep - 1))}
                  disabled={demoStep === 0}
                  className={`px-4 py-2 rounded-lg text-sm ${
                    demoStep === 0 
                      ? 'text-slate-600 cursor-not-allowed' 
                      : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  ← Previous
                </button>
                <button
                  onClick={() => setDemoStep(Math.min(demoSteps.length - 1, demoStep + 1))}
                  disabled={demoStep === demoSteps.length - 1}
                  className={`px-4 py-2 rounded-lg text-sm ${
                    demoStep === demoSteps.length - 1
                      ? 'text-slate-600 cursor-not-allowed' 
                      : 'text-blue-400 hover:text-white hover:bg-blue-500/20'
                  }`}
                >
                  Next →
                </button>
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
              explainable, and reproducible. Here's why ClaimPilot is built differently.
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

      {/* Defensible by Design Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold mb-4">Defensible Decisions — By Design</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              ClaimPilot is not built to "prepare for disputes." It's built to guide decisions 
              correctly <span className="text-slate-200">in the moment</span>. Defensibility is a byproduct.
            </p>
          </div>

          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-8">
            <div className="space-y-4 mb-8">
              {[
                { text: "Every recommendation is grounded in explicit rules", icon: BookOpen },
                { text: "Every conclusion cites the authority it relies on", icon: FileText },
                { text: "Every judgment shows the facts that mattered", icon: ClipboardCheck },
                { text: "Every escalation is recorded with rationale", icon: Users },
                { text: "Similar prior cases are surfaced for context", icon: RotateCcw }
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-4">
                  <div className="p-2 bg-blue-500/10 rounded-lg">
                    <item.icon className="w-5 h-5 text-blue-400" />
                  </div>
                  <span className="text-slate-300">{item.text}</span>
                </div>
              ))}
            </div>

            <div className="border-t border-slate-700 pt-6">
              <p className="text-slate-400 text-center">
                So when a decision is questioned — weeks or months later — the explanation 
                already exists. <span className="text-slate-200">Because it was created at the moment of judgment.</span>
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
