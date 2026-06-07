import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ChangeEventHandler, ReactNode } from 'react'
import {
  Activity,
  BarChart3,
  Boxes,
  Cpu,
  DollarSign,
  FileText,
  Layers3,
  LoaderCircle,
  Play,
  RefreshCcw,
  Settings,
  ShieldCheck,
  Workflow,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { api } from './api/client'
import type { AgentRun, BusinessOutcome, ModelPricing, Persona, Session, TaskSubmit } from './api/types'
import { useSSE } from './hooks/useSSE'
import { useSession } from './hooks/useSession'

const AUTHOR = 'Sarala Biswal'

type RunScope = 'platform' | 'project' | 'revenue'
type ViewId = 'business' | 'outcomes' | 'operations' | 'architecture' | 'settings'

type AgentKey =
  | 'agent-sprint-risk'
  | 'agent-resource-alloc'
  | 'agent-delivery-forecast'
  | 'agent-project-planning'
  | 'agent-renewal-risk'
  | 'agent-churn-signal'
  | 'agent-pipeline-forecast'

type AgentConfig = {
  id: AgentKey
  name: string
  domain: 'PROJECT_DELIVERY' | 'REVENUE_OPS'
  shortDomain: 'Project Management' | 'Revenue Management'
  description: string
  payload: Record<string, unknown>
}

type ProjectPlanningInput = {
  instruction: string
  timeline_weeks: number
  committed_revenue_usd: number
  team_members: Array<Record<string, unknown>>
}

type DemoScenario = {
  id: string
  domain: 'project' | 'revenue'
  title: string
  summary: string
  payloads: Partial<Record<AgentKey, Record<string, unknown>>>
}

type ActiveRun = {
  id: string
  label: string
  agentIds: AgentKey[]
  taskIds: string[]
  startedAt: number
}

type AgentRunStatus = 'QUEUED' | 'RUNNING' | 'COMPLETE' | 'FAILED'

type RunProgress = {
  active: ActiveRun
  complete: number
  failed: number
  percent: number
  running: number
  statuses: Array<{
    agent: AgentConfig
    status: AgentRunStatus
  }>
  terminal: boolean
  total: number
}

const projectAgents: AgentKey[] = [
  'agent-sprint-risk',
  'agent-resource-alloc',
  'agent-delivery-forecast',
  'agent-project-planning',
]

const revenueAgents: AgentKey[] = [
  'agent-renewal-risk',
  'agent-churn-signal',
  'agent-pipeline-forecast',
]

const agentCatalog: Record<AgentKey, AgentConfig> = {
  'agent-sprint-risk': {
    id: 'agent-sprint-risk',
    name: 'SprintRiskAgent',
    domain: 'PROJECT_DELIVERY',
    shortDomain: 'Project Management',
    description: 'Assesses sprint risk, delivery confidence, and mitigations.',
    payload: {
      sprint_name: 'Orion v4.2',
      team_size: 6,
      days_remaining: 8,
      total_tasks: 22,
      completed_tasks: 11,
      velocity_history: [18, 20, 15],
      external_dependencies: ['Vendor API cert renewal'],
      capacity_notes: 'Two engineers at 80% load due to on-call rotation',
      delay_cost_per_week_usd: 75000,
    },
  },
  'agent-resource-alloc': {
    id: 'agent-resource-alloc',
    name: 'ResourceAllocationAgent',
    domain: 'PROJECT_DELIVERY',
    shortDomain: 'Project Management',
    description: 'Optimizes task-to-person assignment across skills and capacity.',
    payload: {
      tasks: [
        { id: 'API-42', skill: 'backend', estimate_hours: 18, priority: 'HIGH' },
        { id: 'UI-19', skill: 'frontend', estimate_hours: 14, priority: 'HIGH' },
        { id: 'QA-07', skill: 'quality', estimate_hours: 10, priority: 'NORMAL' },
        { id: 'SEC-11', skill: 'security', estimate_hours: 12, priority: 'HIGH' },
      ],
      team_members: [
        { name: 'Asha', skills: ['backend', 'security'], load_pct: 80 },
        { name: 'Mateo', skills: ['frontend', 'quality'], load_pct: 55 },
        { name: 'Lina', skills: ['backend', 'quality'], load_pct: 70 },
      ],
      sprint_weeks: 2,
      avg_task_hours: 12,
      hourly_rate: 140,
    },
  },
  'agent-delivery-forecast': {
    id: 'agent-delivery-forecast',
    name: 'DeliveryForecastAgent',
    domain: 'PROJECT_DELIVERY',
    shortDomain: 'Project Management',
    description: 'Forecasts milestone confidence and delivery-linked revenue exposure.',
    payload: {
      milestone_name: 'Orion v4.2 customer launch',
      committed_revenue_usd: 820000,
      target_date: '2026-07-15',
      current_date: '2026-06-06',
      backlog_count: 31,
      avg_velocity: 16,
      sprint_length_days: 14,
      blockers: ['Vendor API certificate renewal', 'Security review queue'],
      capacity_changes: 'Two engineers on partial on-call rotation',
    },
  },
  'agent-project-planning': {
    id: 'agent-project-planning',
    name: 'ProjectPlanningAgent',
    domain: 'PROJECT_DELIVERY',
    shortDomain: 'Project Management',
    description: 'Runs the 5-node planning workflow from instruction to full plan.',
    payload: {
      instruction:
        'Create a recovery plan for Orion v4.2 launch readiness, including epics, risks, owners, and executive summary.',
      team_members: [
        { name: 'Asha', skills: ['backend', 'security'], availability_pct: 80 },
        { name: 'Mateo', skills: ['frontend', 'quality'], availability_pct: 90 },
        { name: 'Lina', skills: ['backend', 'data'], availability_pct: 75 },
      ],
      timeline_weeks: 6,
      committed_revenue_usd: 620000,
    },
  },
  'agent-renewal-risk': {
    id: 'agent-renewal-risk',
    name: 'RenewalRiskAgent',
    domain: 'REVENUE_OPS',
    shortDomain: 'Revenue Management',
    description: 'Scores account renewal risk and recommends save actions.',
    payload: {
      account_name: 'Acme Financial',
      account_arr: 900000,
      contract_end_date: '2026-09-30',
      days_to_renewal: 116,
      login_frequency_30d: 18,
      feature_adoption_score: 5.7,
      support_tickets_90d: 14,
      nps_score: 4,
      last_csm_touchpoint: '2026-05-08',
      upsell_conversations: 0,
      historical_save_rate: 0.42,
    },
  },
  'agent-churn-signal': {
    id: 'agent-churn-signal',
    name: 'ChurnSignalAgent',
    domain: 'REVENUE_OPS',
    shortDomain: 'Revenue Management',
    description: 'Detects early churn signals and intervention value.',
    payload: {
      account_name: 'Northstar Retail',
      account_arr: 480000,
      contract_end_date: '2026-08-31',
      days_to_renewal: 86,
      login_trend: 'down 38% over 30 days',
      adoption_trend: 'core workflow usage flat, analytics usage down',
      ticket_sentiment: 'negative',
      exec_engagement: 'sponsor has missed two QBRs',
      competitor_mentions: 3,
      contract_downloads: 2,
      early_intervention_value: 0.45,
    },
  },
  'agent-pipeline-forecast': {
    id: 'agent-pipeline-forecast',
    name: 'PipelineForecastAgent',
    domain: 'REVENUE_OPS',
    shortDomain: 'Revenue Management',
    description: 'Forecasts quota attainment and recoverable pipeline gaps.',
    payload: {
      rep_name: 'Jordan Lee',
      quota_target: 1800000,
      quarter_close_date: '2026-06-30',
      days_remaining: 24,
      historical_close_rate: 0.31,
      avg_sales_cycle_days: 52,
      pipeline_deals: [
        { account: 'Helio Manufacturing', arr: 520000, crm_probability: 0.62, stage: 'legal' },
        { account: 'Beacon Health', arr: 410000, crm_probability: 0.44, stage: 'security' },
        { account: 'Koru Energy', arr: 360000, crm_probability: 0.35, stage: 'business case' },
      ],
    },
  },
}

const scopeAgentIds: Record<RunScope, AgentKey[]> = {
  platform: [...projectAgents, ...revenueAgents],
  project: projectAgents,
  revenue: revenueAgents,
}

const projectScenarios: DemoScenario[] = [
  {
    id: 'orion-launch',
    domain: 'project',
    title: 'Orion v4.2 launch recovery',
    summary: 'Vendor dependency, security queue, and partial on-call capacity put launch readiness at risk.',
    payloads: {
      'agent-sprint-risk': agentCatalog['agent-sprint-risk'].payload,
      'agent-resource-alloc': agentCatalog['agent-resource-alloc'].payload,
      'agent-delivery-forecast': agentCatalog['agent-delivery-forecast'].payload,
      'agent-project-planning': agentCatalog['agent-project-planning'].payload,
    },
  },
  {
    id: 'cpq-stabilization',
    domain: 'project',
    title: 'CPQ stabilization sprint',
    summary: 'Production pricing defects and integration fixes need a controlled delivery recovery plan.',
    payloads: {
      'agent-sprint-risk': {
        sprint_name: 'CPQ Stabilization 6.1',
        team_size: 5,
        days_remaining: 6,
        total_tasks: 18,
        completed_tasks: 7,
        velocity_history: [12, 10, 9],
        external_dependencies: ['ERP tax service regression sign-off'],
        capacity_notes: 'Pricing architect is split across two escalations',
        delay_cost_per_week_usd: 110000,
      },
      'agent-resource-alloc': {
        tasks: [
          { id: 'CPQ-118', skill: 'pricing', estimate_hours: 22, priority: 'HIGH' },
          { id: 'ERP-44', skill: 'integration', estimate_hours: 18, priority: 'HIGH' },
          { id: 'QA-91', skill: 'quality', estimate_hours: 16, priority: 'HIGH' },
          { id: 'DOC-12', skill: 'enablement', estimate_hours: 8, priority: 'NORMAL' },
        ],
        team_members: [
          { name: 'Priya', skills: ['pricing', 'backend'], load_pct: 85 },
          { name: 'Noah', skills: ['integration', 'quality'], load_pct: 60 },
          { name: 'Elena', skills: ['quality', 'enablement'], load_pct: 45 },
        ],
        sprint_weeks: 2,
        avg_task_hours: 16,
        hourly_rate: 150,
      },
      'agent-delivery-forecast': {
        milestone_name: 'CPQ production defect burn-down',
        committed_revenue_usd: 540000,
        target_date: '2026-07-02',
        current_date: '2026-06-06',
        backlog_count: 24,
        avg_velocity: 10,
        sprint_length_days: 14,
        blockers: ['ERP tax service validation', 'Regression test environment instability'],
        capacity_changes: 'Pricing architect at 60% due to escalation load',
      },
      'agent-project-planning': {
        instruction:
          'Create a CPQ stabilization recovery plan with epics for pricing fixes, ERP validation, regression testing, owners, and executive summary.',
        team_members: [
          { name: 'Priya', skills: ['pricing', 'backend'], availability_pct: 70 },
          { name: 'Noah', skills: ['integration', 'quality'], availability_pct: 85 },
          { name: 'Elena', skills: ['quality', 'enablement'], availability_pct: 90 },
        ],
        timeline_weeks: 4,
        committed_revenue_usd: 540000,
      },
    },
  },
  {
    id: 'atlas-migration',
    domain: 'project',
    title: 'Atlas cloud migration',
    summary: 'Migration cutover has capacity pressure, platform dependencies, and customer launch exposure.',
    payloads: {
      'agent-sprint-risk': {
        sprint_name: 'Atlas Migration Cutover',
        team_size: 7,
        days_remaining: 10,
        total_tasks: 30,
        completed_tasks: 12,
        velocity_history: [20, 17, 14],
        external_dependencies: ['Network allowlist approval', 'Database replication window'],
        capacity_notes: 'Two platform engineers are on incident rotation',
        delay_cost_per_week_usd: 135000,
      },
      'agent-resource-alloc': {
        tasks: [
          { id: 'NET-31', skill: 'network', estimate_hours: 20, priority: 'HIGH' },
          { id: 'DB-82', skill: 'database', estimate_hours: 24, priority: 'HIGH' },
          { id: 'CUT-17', skill: 'platform', estimate_hours: 18, priority: 'HIGH' },
          { id: 'OBS-09', skill: 'observability', estimate_hours: 12, priority: 'NORMAL' },
        ],
        team_members: [
          { name: 'Ravi', skills: ['platform', 'observability'], load_pct: 75 },
          { name: 'Mina', skills: ['database', 'backend'], load_pct: 65 },
          { name: 'Omar', skills: ['network', 'platform'], load_pct: 80 },
        ],
        sprint_weeks: 3,
        avg_task_hours: 18,
        hourly_rate: 155,
      },
      'agent-delivery-forecast': {
        milestone_name: 'Atlas migration customer cutover',
        committed_revenue_usd: 760000,
        target_date: '2026-07-26',
        current_date: '2026-06-06',
        backlog_count: 38,
        avg_velocity: 16,
        sprint_length_days: 14,
        blockers: ['Network allowlist approval', 'Database replication dry run'],
        capacity_changes: 'Platform team has two engineers on incident rotation',
      },
      'agent-project-planning': {
        instruction:
          'Build an Atlas migration cutover plan with epics for network readiness, data migration, platform validation, rollback plan, and executive decision points.',
        team_members: [
          { name: 'Ravi', skills: ['platform', 'observability'], availability_pct: 80 },
          { name: 'Mina', skills: ['database', 'backend'], availability_pct: 85 },
          { name: 'Omar', skills: ['network', 'platform'], availability_pct: 70 },
        ],
        timeline_weeks: 7,
        committed_revenue_usd: 760000,
      },
    },
  },
]

const revenueScenarios: DemoScenario[] = [
  {
    id: 'acme-northstar-q2',
    domain: 'revenue',
    title: 'Q2 revenue save motion',
    summary: 'Renewal, churn, and late-quarter pipeline signals are consolidated for sales leadership.',
    payloads: {
      'agent-renewal-risk': agentCatalog['agent-renewal-risk'].payload,
      'agent-churn-signal': agentCatalog['agent-churn-signal'].payload,
      'agent-pipeline-forecast': agentCatalog['agent-pipeline-forecast'].payload,
    },
  },
  {
    id: 'meridian-fortis-renewals',
    domain: 'revenue',
    title: 'Meridian and Fortis renewal risk',
    summary: 'Healthcare renewal is stable, logistics account is showing declining adoption and ticket pressure.',
    payloads: {
      'agent-renewal-risk': {
        account_name: 'Meridian Healthcare',
        account_arr: 840000,
        contract_end_date: '2026-09-30',
        days_to_renewal: 117,
        login_frequency_30d: 42,
        feature_adoption_score: 7.8,
        support_tickets_90d: 3,
        nps_score: 72,
        last_csm_touchpoint: '2026-05-15',
        upsell_conversations: 1,
        historical_save_rate: 0.38,
      },
      'agent-churn-signal': {
        account_name: 'Fortis Logistics',
        account_arr: 360000,
        contract_end_date: '2026-08-15',
        days_to_renewal: 71,
        login_trend: 'declining 62% over 60 days',
        adoption_trend: 'stalled - no new features activated in 45 days',
        ticket_sentiment: 'negative',
        exec_engagement: 'economic buyer has not attended the last two check-ins',
        competitor_mentions: 2,
        contract_downloads: 1,
        early_intervention_value: 0.5,
      },
      'agent-pipeline-forecast': {
        rep_name: 'Sarah Chen',
        quota_target: 500000,
        quarter_close_date: '2026-06-30',
        days_remaining: 26,
        historical_close_rate: 0.62,
        avg_sales_cycle_days: 45,
        pipeline_deals: [
          { account: 'Meridian Healthcare', arr: 84000, crm_probability: 0.85, stage: 'Negotiation' },
          { account: 'Fortis Logistics', arr: 62000, crm_probability: 0.45, stage: 'Proposal Sent' },
        ],
      },
    },
  },
  {
    id: 'enterprise-west-pipeline',
    domain: 'revenue',
    title: 'Enterprise West pipeline recovery',
    summary: 'Large expansion and renewal motions need focus before quarter close.',
    payloads: {
      'agent-renewal-risk': {
        account_name: 'Apex Industrial',
        account_arr: 1250000,
        contract_end_date: '2026-10-15',
        days_to_renewal: 131,
        login_frequency_30d: 21,
        feature_adoption_score: 5.1,
        support_tickets_90d: 9,
        nps_score: 28,
        last_csm_touchpoint: '2026-04-29',
        upsell_conversations: 0,
        historical_save_rate: 0.44,
      },
      'agent-churn-signal': {
        account_name: 'Beacon Health',
        account_arr: 640000,
        contract_end_date: '2026-09-18',
        days_to_renewal: 104,
        login_trend: 'down 41% in admin users over 30 days',
        adoption_trend: 'automation usage down, reporting exports increasing',
        ticket_sentiment: 'mixed',
        exec_engagement: 'new sponsor has not accepted QBR invite',
        competitor_mentions: 4,
        contract_downloads: 3,
        early_intervention_value: 0.48,
      },
      'agent-pipeline-forecast': {
        rep_name: 'Maya Singh',
        quota_target: 2200000,
        quarter_close_date: '2026-06-30',
        days_remaining: 24,
        historical_close_rate: 0.28,
        avg_sales_cycle_days: 58,
        pipeline_deals: [
          { account: 'Apex Industrial', arr: 720000, crm_probability: 0.52, stage: 'legal' },
          { account: 'Beacon Health', arr: 640000, crm_probability: 0.39, stage: 'security' },
          { account: 'Lumina Retail', arr: 380000, crm_probability: 0.31, stage: 'business case' },
        ],
      },
    },
  },
]

const scopeCopy: Record<
  RunScope,
  {
    label: string
    title: string
    impact: string
    impactSubtext: string
    story: string
    savedTitle: string
    savedCopy: string
    nextTitle: string
    nextCopy: string
    runTitle: string
    runCopy: string
    demoCopy: string
    breakdown: [string, string][]
  }
> = {
  platform: {
    label: 'Complete Platform',
    title: 'Complete platform run converted delivery and revenue risk into $1.42M protected value',
    impact: '$1.42M',
    impactSubtext: 'protected value',
    story:
      'The run found one project delivery exposure, two renewal risks, and late-quarter pipeline gaps. AgentOps grouped the evidence into a CFO-readable outcome ledger with owners, mitigations, and next actions.',
    savedTitle: '$1.42M protected',
    savedCopy:
      'Savings are stored in the outcome ledger by domain, agent, run, confidence score, and source evidence.',
    nextTitle: 'Approve cross-domain recovery plan',
    nextCopy:
      'Business users see the summary and owners. Technical users can inspect trace, quality, prompt, response, and cost detail.',
    runTitle: 'Run complete platform',
    runCopy: 'Runs all 7 business agents and produces the cross-domain outcome story.',
    demoCopy:
      'Starts with a complete platform run, then walks through value protected, domain breakdown, run evidence, quality score, and trace replay.',
    breakdown: [
      ['Project risk avoided', '$340K'],
      ['Renewal ARR protected', '$620K'],
      ['Pipeline recovery focus', '$460K'],
    ],
  },
  project: {
    label: 'Project Management',
    title: '$340K delivery exposure moved into an owned recovery plan',
    impact: '$340K',
    impactSubtext: 'delivery exposure reduced',
    story:
      'The Project Management run identified sprint risk, capacity imbalance, milestone confidence gaps, and plan readiness issues for Orion v4.2.',
    savedTitle: '$340K delivery risk reduced',
    savedCopy:
      'The outcome ledger links delivery confidence and mitigation actions back to Project Management agents and run evidence.',
    nextTitle: 'Approve delivery recovery plan',
    nextCopy:
      'Business users get the executive plan. Technical users inspect the ProjectPlanning parent run and five node traces.',
    runTitle: 'Run Project Management',
    runCopy:
      'Runs the 4 delivery and planning agents for delivery risk, capacity, forecast, and plan output.',
    demoCopy:
      'Starts with delivery risk, capacity reallocation, milestone confidence, plan output, and workflow trace.',
    breakdown: [
      ['Launch slip exposure', '$260K'],
      ['Capacity reallocation gain', '$55K'],
      ['Escalation value', '$25K'],
    ],
  },
  revenue: {
    label: 'Revenue Management',
    title: '$1.08M revenue exposure prioritized into save and pipeline actions',
    impact: '$1.08M',
    impactSubtext: 'revenue protected',
    story:
      'The Revenue Management run identified renewal risk, churn signals, and recoverable pipeline gaps for the revenue leadership team.',
    savedTitle: '$1.08M revenue protected',
    savedCopy:
      'The outcome ledger separates renewal protection, churn intervention, and pipeline recovery by agent and confidence score.',
    nextTitle: 'Launch revenue save motion',
    nextCopy:
      'Business users get the account action plan. Technical users inspect payloads, model responses, quality scores, and costs.',
    runTitle: 'Run Revenue Management',
    runCopy: 'Runs the 3 revenue agents for renewal risk, churn signal, and pipeline forecast.',
    demoCopy:
      'Starts with protected ARR, churn intervention, pipeline gap recovery, account actions, and run evidence.',
    breakdown: [
      ['Renewal ARR protected', '$620K'],
      ['Pipeline gap recovery', '$340K'],
      ['Churn intervention value', '$120K'],
    ],
  },
}

const views: Array<{ id: ViewId; label: string; group: string; icon: LucideIcon }> = [
  { id: 'business', label: 'Business View', group: 'Business', icon: DollarSign },
  { id: 'outcomes', label: 'Outcomes', group: 'Business', icon: BarChart3 },
  { id: 'operations', label: 'Operations', group: 'Technical', icon: Activity },
  { id: 'architecture', label: 'Architecture', group: 'Technical', icon: Layers3 },
  { id: 'settings', label: 'Settings', group: 'Control', icon: Settings },
]

function money(value: number) {
  return `$${Math.round(value).toLocaleString()}`
}

function costMoney(value: number) {
  if (value === 0) return '$0.0000'
  if (Math.abs(value) < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

function unitCostMoney(value: number) {
  return `$${value.toFixed(value < 0.01 ? 4 : 2)}`
}

function qualityLabel(runs: AgentRun[]) {
  const scores = runs
    .map((run) => run.quality_score)
    .filter((score): score is number => typeof score === 'number')
  if (!scores.length) return 'pending'
  const avg = scores.reduce((sum, score) => sum + score, 0) / scores.length
  return avg.toFixed(2)
}

function recentRuns(runs: AgentRun[]) {
  return [...runs].reverse().slice(0, 8)
}

function billableRuns(runs: AgentRun[]) {
  return runs.filter((run) => run.run_type === 'SINGLE_SHOT' || run.run_type === 'WORKFLOW_PARENT')
}

function pricingForRuns(runs: AgentRun[], pricing: ModelPricing[]) {
  const pricedRun = runs.find((run) => run.model_used)
  const fallback = pricing.find((item) => item.model_name === 'llama3.2:latest')
    ?? pricing.find((item) => item.model_name === 'llama3.2:3b')
  if (!pricedRun) return fallback
  return pricing.find((item) => item.model_name === pricedRun.model_used && item.effective_to === null)
    ?? fallback
}

function tokenCostDetail(
  pricing: ModelPricing | undefined,
  promptTokens: number,
  completionTokens: number,
) {
  const inputRate = pricing ? unitCostMoney(pricing.input_cost_per_1k) : 'pending'
  const outputRate = pricing ? unitCostMoney(pricing.output_cost_per_1k) : 'pending'
  const tokenDetail = promptTokens + completionTokens > 0
    ? `${promptTokens.toLocaleString()} in / ${completionTokens.toLocaleString()} out`
    : 'no priced tokens yet'
  return `${tokenDetail} - ${inputRate}/1K in, ${outputRate}/1K out`
}

function agentConfigsFor(agentIds: AgentKey[]) {
  return agentIds.map((agentId) => agentCatalog[agentId])
}

function terminalRunFor(taskId: string, runs: AgentRun[]) {
  return runs.find(
    (run) =>
      run.task_id === taskId &&
      (run.run_type === 'SINGLE_SHOT' || run.run_type === 'WORKFLOW_PARENT') &&
      (run.status === 'COMPLETE' || run.status === 'FAILED'),
  )
}

function runningRunFor(taskId: string, runs: AgentRun[]) {
  return runs.find((run) => run.task_id === taskId && run.status === 'RUNNING')
}

function progressFor(active: ActiveRun | null, runs: AgentRun[]): RunProgress | null {
  if (!active) return null

  // Keep the button and run console honest while background tasks update through SSE/polling.
  const statuses = active.agentIds.map((agentId, index) => {
    const taskId = active.taskIds[index]
    const terminal = terminalRunFor(taskId, runs)
    const running = runningRunFor(taskId, runs)
    const status = terminal?.status ?? (running ? 'RUNNING' : 'QUEUED')
    return {
      agent: agentCatalog[agentId],
      status: status as AgentRunStatus,
    }
  })
  const complete = statuses.filter((item) => item.status === 'COMPLETE').length
  const failed = statuses.filter((item) => item.status === 'FAILED').length
  const running = statuses.filter((item) => item.status === 'RUNNING').length
  const total = statuses.length
  const done = complete + failed
  const percent = total === 0 ? 0 : Math.max(done === 0 ? 8 : 0, Math.round((done / total) * 100))

  return {
    active,
    complete,
    failed,
    percent,
    running,
    statuses,
    terminal: total > 0 && done === total,
    total,
  }
}

function projectPlanningInputFrom(payload: Record<string, unknown>): ProjectPlanningInput {
  const teamMembers = payload.team_members
  return {
    instruction: String(payload.instruction ?? ''),
    timeline_weeks: Number(payload.timeline_weeks ?? 6),
    committed_revenue_usd: Number(payload.committed_revenue_usd ?? 0),
    team_members: Array.isArray(teamMembers)
      ? (teamMembers as Array<Record<string, unknown>>)
      : [],
  }
}

function projectPlanningPayloadFrom(input: ProjectPlanningInput): Record<string, unknown> {
  return {
    instruction: input.instruction,
    team_members: input.team_members,
    timeline_weeks: input.timeline_weeks,
    committed_revenue_usd: input.committed_revenue_usd,
  }
}

function projectScenarioFor(index: number) {
  return projectScenarios[index % projectScenarios.length]
}

function revenueScenarioFor(index: number) {
  return revenueScenarios[index % revenueScenarios.length]
}

function visibleScenariosFor(
  scope: RunScope,
  projectScenario: DemoScenario,
  revenueScenario: DemoScenario,
) {
  if (scope === 'project') return [projectScenario]
  if (scope === 'revenue') return [revenueScenario]
  return [projectScenario, revenueScenario]
}

export default function App() {
  const [view, setView] = useState<ViewId>('business')
  const [persona, setPersona] = useState<Persona>('business')
  const [scope, setScope] = useState<RunScope>('platform')
  const [selectedAgent, setSelectedAgent] = useState<AgentKey>('agent-sprint-risk')
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [outcomes, setOutcomes] = useState<BusinessOutcome[]>([])
  const [pricing, setPricing] = useState<ModelPricing[]>([])
  const [statusMessage, setStatusMessage] = useState('Ready to run the locked demo flow.')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeRun, setActiveRun] = useState<ActiveRun | null>(null)
  const [projectScenarioIndex, setProjectScenarioIndex] = useState(0)
  const [revenueScenarioIndex, setRevenueScenarioIndex] = useState(0)
  const [projectPlanningInput, setProjectPlanningInput] = useState<ProjectPlanningInput>(() =>
    projectPlanningInputFrom(projectScenarioFor(0).payloads['agent-project-planning'] ?? {}),
  )
  const { session, create } = useSession()

  const copy = scopeCopy[scope]
  const currentProjectScenario = projectScenarioFor(projectScenarioIndex)
  const currentRevenueScenario = revenueScenarioFor(revenueScenarioIndex)
  const visibleScenarios = visibleScenariosFor(scope, currentProjectScenario, currentRevenueScenario)
  const availableAgentIds = scopeAgentIds[scope]
  const activeSelectedAgent = availableAgentIds.includes(selectedAgent)
    ? selectedAgent
    : availableAgentIds[0]
  const selectedAgentConfig = agentCatalog[activeSelectedAgent]
  const availableAgentConfigs = useMemo(
    () => agentConfigsFor(availableAgentIds),
    [availableAgentIds],
  )
  const billableRunList = useMemo(() => billableRuns(runs), [runs])

  const sessionImpact = useMemo(
    () => outcomes.reduce((sum, outcome) => sum + outcome.financial_impact_usd, 0),
    [outcomes],
  )
  const sessionCost = useMemo(
    () => billableRunList.reduce((sum, run) => sum + run.cost_usd, 0),
    [billableRunList],
  )
  const sessionPromptTokens = useMemo(
    () => billableRunList.reduce((sum, run) => sum + run.prompt_tokens, 0),
    [billableRunList],
  )
  const sessionCompletionTokens = useMemo(
    () => billableRunList.reduce((sum, run) => sum + run.completion_tokens, 0),
    [billableRunList],
  )
  const activePricing = useMemo(
    () => pricingForRuns(billableRunList, pricing),
    [billableRunList, pricing],
  )
  const tokenDetail = useMemo(
    () => tokenCostDetail(activePricing, sessionPromptTokens, sessionCompletionTokens),
    [activePricing, sessionPromptTokens, sessionCompletionTokens],
  )
  const activeProgress = useMemo(() => progressFor(activeRun, runs), [activeRun, runs])
  const hasRunningWork = Boolean(activeProgress && !activeProgress.terminal)

  const refresh = useCallback(
    async (activeSession?: Session | null) => {
      const targetSession = activeSession ?? session
      const nextRuns = await api.runs.list(
        targetSession ? { session_id: targetSession.id } : undefined,
      )
      setRuns(nextRuns)
      if (targetSession) {
        const nextOutcomes = await api.outcomes.session(targetSession.id)
        setOutcomes(nextOutcomes.outcomes)
      }
    },
    [session],
  )

  useEffect(() => {
    void refresh().catch(() => undefined)
  }, [refresh])

  useEffect(() => {
    void api.pricing.list().then(setPricing).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!availableAgentIds.includes(selectedAgent)) {
      setSelectedAgent(availableAgentIds[0])
    }
  }, [availableAgentIds, selectedAgent])

  useEffect(() => {
    setProjectPlanningInput(
      projectPlanningInputFrom(
        currentProjectScenario.payloads['agent-project-planning'] ?? {},
      ),
    )
  }, [currentProjectScenario])

  useEffect(() => {
    if (!activeProgress || activeProgress.terminal) return undefined
    const timer = window.setInterval(() => {
      void refresh().catch(() => undefined)
    }, 2500)
    return () => window.clearInterval(timer)
  }, [activeProgress, refresh])

  useEffect(() => {
    if (!activeProgress?.terminal) return
    const outcome =
      activeProgress.failed > 0
        ? `${activeProgress.active.label} finished with ${activeProgress.failed} failed agent${activeProgress.failed === 1 ? '' : 's'}.`
        : `${activeProgress.active.label} completed successfully.`
    setStatusMessage(outcome)
  }, [activeProgress])

  useSSE(
    useCallback(() => {
      void refresh().catch(() => undefined)
    }, [refresh]),
  )

  async function ensureSession() {
    return session ?? create()
  }

  function payloadForAgent(agentId: AgentKey): Record<string, unknown> {
    // ProjectPlanningAgent has editable user input; all other agents use the rotating demo scenario.
    if (agentId === 'agent-project-planning') {
      return projectPlanningPayloadFrom(projectPlanningInput)
    }
    const scenario =
      agentCatalog[agentId].domain === 'PROJECT_DELIVERY'
        ? currentProjectScenario
        : currentRevenueScenario
    return scenario.payloads[agentId] ?? agentCatalog[agentId].payload
  }

  function advanceScenarios(agentIds: AgentKey[]) {
    if (agentIds.some((agentId) => agentCatalog[agentId].domain === 'PROJECT_DELIVERY')) {
      setProjectScenarioIndex((index) => index + 1)
    }
    if (agentIds.some((agentId) => agentCatalog[agentId].domain === 'REVENUE_OPS')) {
      setRevenueScenarioIndex((index) => index + 1)
    }
  }

  async function submitAgents(agentIds: AgentKey[], runLabel: string, nextMessage: string) {
    // One UI run becomes a batch of backend tasks sharing the same session and active scenario.
    setIsSubmitting(true)
    const agentNames = agentIds.map((agentId) => agentCatalog[agentId].name)
    setStatusMessage(`Submitting ${runLabel}: ${agentNames.join(', ')}.`)
    try {
      const activeSession = await ensureSession()
      const tasks: TaskSubmit[] = agentIds.map((agentId) => ({
        agent_id: agentId,
        session_id: activeSession.id,
        input_payload: payloadForAgent(agentId),
        priority: 'HIGH',
      }))
      const submittedTasks = await api.tasks.batch({ tasks })
      setActiveRun({
        id: `${Date.now()}`,
        label: runLabel,
        agentIds,
        taskIds: submittedTasks.map((task) => task.id),
        startedAt: Date.now(),
      })
      setStatusMessage(nextMessage.replace('submitted', 'running'))
      advanceScenarios(agentIds)
      await refresh(activeSession)
    } catch (error) {
      setActiveRun(null)
      setStatusMessage(
        error instanceof Error
          ? `Run submission failed: ${error.message}`
          : 'Run submission failed. Confirm the backend API is running on port 8000.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function runSelectedScope() {
    const scenarioLabel = visibleScenarios.map((scenario) => scenario.title).join(' + ')
    await submitAgents(
      scopeAgentIds[scope],
      scopeCopy[scope].label,
      `${scopeCopy[scope].label} run submitted for ${scenarioLabel} with ${scopeAgentIds[scope].length} agents.`,
    )
  }

  async function runSelectedAgent() {
    const scenario =
      agentCatalog[activeSelectedAgent].domain === 'PROJECT_DELIVERY'
        ? currentProjectScenario
        : currentRevenueScenario
    await submitAgents(
      [activeSelectedAgent],
      agentCatalog[activeSelectedAgent].shortDomain,
      `${agentCatalog[activeSelectedAgent].name} submitted for ${scenario.title}.`,
    )
  }

  const completeRuns = runs.filter((run) => run.status === 'COMPLETE').length
  const failedRuns = runs.filter((run) => run.status === 'FAILED').length
  const runProgressLabel =
    activeProgress && hasRunningWork
      ? `Running ${activeProgress.active.label} ${activeProgress.complete + activeProgress.failed}/${activeProgress.total}`
      : copy.runTitle
  const RunButtonIcon = hasRunningWork || isSubmitting ? LoaderCircle : Play

  return (
    <div className={`app-shell ${persona}-lens`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">OC</div>
          <div>
            <h1>AgentOps Control Plane</h1>
            <p>Author: {AUTHOR}</p>
          </div>
        </div>

        <div className="segmented" aria-label="View lens">
          <button
            className={persona === 'business' ? 'active' : ''}
            type="button"
            onClick={() => setPersona('business')}
          >
            Business
          </button>
          <button
            className={persona === 'technical' ? 'active' : ''}
            type="button"
            onClick={() => setPersona('technical')}
          >
            Technical
          </button>
        </div>

        <div className="scope-selector" aria-label="Run scope">
          <strong>Run Scope</strong>
          {(Object.keys(scopeCopy) as RunScope[]).map((item) => (
            <button
              className={scope === item ? 'active' : ''}
              type="button"
              key={item}
              onClick={() => setScope(item)}
            >
              <span>{scopeCopy[item].label}</span>
              <small>{scopeAgentIds[item].length} business agents</small>
            </button>
          ))}
        </div>

        <nav className="nav">
          {['Business', 'Technical', 'Control'].map((group) => (
            <div className="nav-group" key={group}>
              <span>{group}</span>
              {views
                .filter((item) => item.group === group)
                .map((item) => {
                  const Icon = item.icon
                  return (
                    <button
                      className={view === item.id ? 'active' : ''}
                      type="button"
                      key={item.id}
                      onClick={() => setView(item.id)}
                    >
                      <Icon size={16} />
                      {item.label}
                    </button>
                  )
                })}
            </div>
          ))}
        </nav>

        <div className="runtime-card">
          <strong>Runtime</strong>
          <div><span>Provider</span><b>Ollama</b></div>
          <div><span>Session</span><b>{session?.status ?? 'Starting'}</b></div>
          <div><span>SSE</span><b>Connected</b></div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <h2>{persona === 'business' ? 'Business View' : 'Technical View'}</h2>
            <p>
              {persona === 'business'
                ? 'Story-led view of what was solved, what value was protected, and what action is next.'
                : 'Evidence-led view of which agents ran, what was captured, and whether the result can be trusted.'}
            </p>
          </div>
          <div className="top-actions">
            <button className="btn" type="button" onClick={() => setView('outcomes')}>
              <FileText size={16} /> Outcome ledger
            </button>
            <button className="btn" type="button" onClick={() => setView('operations')}>
              <Workflow size={16} /> Inspect trace
            </button>
            <button
              className="btn primary"
              type="button"
              disabled={isSubmitting || hasRunningWork}
              onClick={() => void runSelectedScope()}
            >
              <RunButtonIcon className={hasRunningWork || isSubmitting ? 'spin-icon' : ''} size={16} />
              {isSubmitting ? 'Submitting...' : runProgressLabel}
            </button>
          </div>
        </header>

        {view === 'business' && (
          <BusinessView
            completeRuns={completeRuns}
            copy={copy}
            failedRuns={failedRuns}
            isSubmitting={isSubmitting}
            activeProgress={activeProgress}
            currentProjectScenario={currentProjectScenario}
            onRunScope={() => void runSelectedScope()}
            onRunAgent={() => void runSelectedAgent()}
            onViewChange={setView}
            outcomes={outcomes}
            persona={persona}
            quality={qualityLabel(runs)}
            scope={scope}
            selectedAgent={selectedAgent}
            selectedAgentConfig={selectedAgentConfig}
            sessionImpact={sessionImpact}
            sessionCost={sessionCost}
            tokenDetail={tokenDetail}
            runs={runs}
            setPersona={setPersona}
            setProjectPlanningInput={setProjectPlanningInput}
            setSelectedAgent={setSelectedAgent}
            statusMessage={statusMessage}
            totalRuns={runs.length}
            availableAgentConfigs={availableAgentConfigs}
            availableAgentIds={availableAgentIds}
            projectPlanningInput={projectPlanningInput}
            visibleScenarios={visibleScenarios}
          />
        )}
        {view === 'outcomes' && <OutcomesView outcomes={outcomes} sessionImpact={sessionImpact} />}
        {view === 'operations' && (
          <OperationsView runs={runs} statusMessage={statusMessage} onRefresh={() => void refresh()} />
        )}
        {view === 'architecture' && (
          <ArchitectureView
            activeProgress={activeProgress}
            onViewChange={setView}
            runs={runs}
            scope={scope}
            sessionImpact={sessionImpact}
          />
        )}
        {view === 'settings' && (
          <SettingsView
            availableAgentIds={availableAgentIds}
            scope={scope}
            selectedAgent={activeSelectedAgent}
            setSelectedAgent={setSelectedAgent}
          />
        )}
      </main>
    </div>
  )
}

function BusinessView({
  activeProgress,
  completeRuns,
  copy,
  currentProjectScenario,
  failedRuns,
  isSubmitting,
  onRunAgent,
  onRunScope,
  onViewChange,
  outcomes,
  persona,
  projectPlanningInput,
  quality,
  runs,
  scope,
  selectedAgent,
  selectedAgentConfig,
  sessionCost,
  sessionImpact,
  setPersona,
  setProjectPlanningInput,
  setSelectedAgent,
  statusMessage,
  tokenDetail,
  totalRuns,
  availableAgentConfigs,
  availableAgentIds,
  visibleScenarios,
}: {
  activeProgress: RunProgress | null
  completeRuns: number
  copy: (typeof scopeCopy)[RunScope]
  currentProjectScenario: DemoScenario
  failedRuns: number
  isSubmitting: boolean
  onRunAgent: () => void
  onRunScope: () => void
  onViewChange: (view: ViewId) => void
  outcomes: BusinessOutcome[]
  persona: Persona
  projectPlanningInput: ProjectPlanningInput
  quality: string
  scope: RunScope
  selectedAgent: AgentKey
  selectedAgentConfig: AgentConfig
  sessionCost: number
  sessionImpact: number
  runs: AgentRun[]
  setPersona: (persona: Persona) => void
  setProjectPlanningInput: (input: ProjectPlanningInput) => void
  setSelectedAgent: (agent: AgentKey) => void
  statusMessage: string
  tokenDetail: string
  totalRuns: number
  availableAgentConfigs: AgentConfig[]
  availableAgentIds: AgentKey[]
  visibleScenarios: DemoScenario[]
}) {
  const runIsActive = Boolean(activeProgress && !activeProgress.terminal)
  return (
    <div className="page-stack">
      <section className="kpi-grid" aria-label="Business summary">
        <Kpi label="Active scope" value={scopeCopy[scope].label} detail={`${scopeAgentIds[scope].length} agents`} />
        <Kpi label="Agent runs" value={String(totalRuns)} detail={`${completeRuns} complete, ${failedRuns} failed`} />
        <Kpi label="Quality" value={quality} detail="async judge score" />
        <Kpi
          label="Financial impact"
          value={sessionImpact > 0 ? money(sessionImpact) : copy.impact}
          detail={sessionImpact > 0 ? 'live outcome ledger' : copy.impactSubtext}
        />
        <Kpi
          label="Token cost"
          value={costMoney(sessionCost)}
          detail={tokenDetail}
        />
      </section>

      <section className="story-board">
        <div className="story-lead">
          <span className="pill">{persona === 'business' ? 'Business lens' : 'Technical lens'} - {copy.label}</span>
          <h3>{copy.title}</h3>
          <p>{copy.story}</p>
          <div className="story-path">
            <StoryStep index="01" title="Signal" copy="Delivery and revenue data enters a governed session." />
            <StoryStep index="02" title="Analysis" copy="Domain agents assess risk, forecast exposure, and create actions." />
            <StoryStep index="03" title="Evidence" copy="Trace, tokens, cost, model, and quality are captured." />
            <StoryStep index="04" title="Decision" copy="Leaders see the action path and operators can inspect evidence." />
            <StoryStep index="05" title="Outcome" copy="Risk becomes saved value in the outcome ledger." emphasis />
          </div>
        </div>

        <aside className="value-panel">
          <span>Business value protected</span>
          <strong>{sessionImpact > 0 ? money(sessionImpact) : copy.impact}</strong>
          <p>{sessionImpact > 0 ? 'Live value from completed agent outcomes in this session.' : copy.savedCopy}</p>
          <div className="breakdown-list">
            {copy.breakdown.map(([label, value]) => (
              <div key={label}><span>{label}</span><b>{value}</b></div>
            ))}
          </div>
        </aside>
      </section>

      <section className="solved-grid">
        <InfoCard tone="good" label="Solved" title="Hidden risk became owned work" copy={copy.story} />
        <InfoCard tone="good" label="Saved" title={copy.savedTitle} copy={copy.savedCopy} />
        <InfoCard tone="warn" label="Next action" title={copy.nextTitle} copy={copy.nextCopy} />
      </section>

      <section className="section">
        <SectionHeader
          icon={<Play size={18} />}
          label={copy.label}
          title="Run and Demo Console"
          subtitle="Execute the selected scope, launch a guided demo, or run one agent for validation."
        />
        <div className="run-console">
          <div className="run-console-main">
            <div className="scenario-strip">
              {visibleScenarios.map((scenario) => (
                <ScenarioCard scenario={scenario} key={scenario.id} />
              ))}
            </div>
            {(scope === 'project' || scope === 'platform') && (
              <ProjectPlanningInputCard
                input={projectPlanningInput}
                scenario={currentProjectScenario}
                setInput={setProjectPlanningInput}
              />
            )}
            <div className="run-command-grid">
              <button
                className={`run-command active ${runIsActive ? 'running' : ''}`}
                type="button"
                disabled={isSubmitting || runIsActive}
                onClick={onRunScope}
              >
                <span>Selected scope</span>
                <strong>
                  {isSubmitting
                    ? 'Submitting request'
                    : runIsActive && activeProgress
                      ? `Running ${activeProgress.active.label}`
                      : copy.runTitle}
                </strong>
                <p>{copy.runCopy}</p>
              </button>
              <button className="run-command" type="button" onClick={() => onViewChange('outcomes')}>
                <span>Guided demo</span>
                <strong>Start walkthrough</strong>
                <p>{copy.demoCopy}</p>
              </button>
              <button
                className="run-command"
                type="button"
                disabled={isSubmitting || runIsActive}
                onClick={onRunAgent}
              >
                <span>Single agent</span>
                <strong>Run selected agent</strong>
                <p>{selectedAgentConfig.description}</p>
              </button>
            </div>
          </div>

          <aside className="demo-panel">
            <span className="pill">Run target</span>
            <h4>{copy.label}</h4>
            <p className={statusMessage.startsWith('Run submission failed') ? 'run-status error' : 'run-status'}>
              {statusMessage}
            </p>
            <div className="domain-agent-list" aria-label={`${copy.label} agents`}>
              <span>{copy.label} agents</span>
              <div>
                {availableAgentConfigs.map((agent) => (
                  <b key={agent.id}>{agent.name}</b>
                ))}
              </div>
            </div>
            <div className="selected-agent-summary">
              <span>Single-agent target</span>
              <strong>{selectedAgentConfig.name}</strong>
              <small>{selectedAgentConfig.description}</small>
            </div>
            <label htmlFor="single-agent">{copy.label} single-agent run</label>
            <AgentSelect
              id="single-agent"
              agentIds={availableAgentIds}
              value={selectedAgent}
              onChange={(event) => setSelectedAgent(event.target.value as AgentKey)}
            />
            <div className="button-row">
              <button className="btn" type="button" onClick={() => onViewChange('settings')}>Preview payload</button>
              <button className="btn" type="button" onClick={() => onViewChange('operations')}>Replay last run</button>
              <button
                className="btn primary"
                type="button"
                onClick={onRunScope}
                disabled={isSubmitting || runIsActive}
              >
                {(isSubmitting || runIsActive) && <LoaderCircle className="spin-icon" size={16} />}
                {isSubmitting
                  ? 'Submitting...'
                  : runIsActive && activeProgress
                    ? `Running ${activeProgress.complete + activeProgress.failed}/${activeProgress.total}`
                    : copy.runTitle}
              </button>
            </div>
            {activeProgress && <RunProgressPanel progress={activeProgress} />}
          </aside>
        </div>
      </section>

      <section className="section">
        <SectionHeader
          icon={persona === 'business' ? <DollarSign size={18} /> : <Cpu size={18} />}
          label={`${persona} lens active`}
          title={persona === 'business' ? 'Business View: what changes' : 'Technical View: what changes'}
          subtitle={
            persona === 'business'
              ? 'Business users get the outcome narrative first, with evidence available when needed.'
              : 'Technical users get the execution evidence first, with business impact still linked.'
          }
        />
        <div className="lens-change-grid">
          {(persona === 'business'
            ? [
                ['Opening question', 'What was solved?', 'What changed, what risk was reduced, and how much value was protected.'],
                ['Main surface', 'Outcome story', 'Executive story, outcome ledger, KPI rollup, and owner action plan.'],
                ['Grouping', 'Platform to domain to value', 'Grouped by run scope, domain, financial outcome, confidence, and owner.'],
                ['Primary action', 'Approve the plan', 'Approve mitigation, launch the save motion, or export the CFO summary.'],
              ]
            : [
                ['Opening question', 'Can we trust the run?', 'Which agents ran, what model calls happened, and what can be replayed.'],
                ['Main surface', 'Execution evidence', 'Run ledger, workflow trace, prompt response record, cost, and quality dimensions.'],
                ['Grouping', 'Session to task to run', 'Grouped by session, task, agent run, workflow node, model, metric, and retry lineage.'],
                ['Primary action', 'Operate the platform', 'Inspect traces, retry failures, validate readiness, and export audit evidence.'],
              ]).map(([label, title, body]) => (
            <div className="lens-card" key={label}>
              <span>{label}</span>
              <strong>{title}</strong>
              <p>{body}</p>
            </div>
          ))}
        </div>
        <div className="lens-toggle-row">
          <button
            className={`btn ${persona === 'business' ? 'primary' : ''}`}
            type="button"
            onClick={() => setPersona('business')}
          >
            Business View
          </button>
          <button
            className={`btn ${persona === 'technical' ? 'primary' : ''}`}
            type="button"
            onClick={() => setPersona('technical')}
          >
            Technical View
          </button>
        </div>
      </section>

      {persona === 'technical' && (
        <>
          <RunScopeModel />
          <TechnicalEvidence runs={recentRuns(runs)} />
        </>
      )}
    </div>
  )
}

function RunScopeModel() {
  return (
    <section className="section technical-block">
      <SectionHeader
        icon={<Boxes size={18} />}
        label="scope first"
        title="Run Scope Model"
        subtitle="Run scope controls agent dispatch. The lens only changes how the same evidence is surfaced."
      />
      <div className="scope-model-grid">
        {(Object.keys(scopeCopy) as RunScope[]).map((item) => (
          <article className="scope-model-card" key={item}>
            <span>{scopeAgentIds[item].length} agents</span>
            <strong>{scopeCopy[item].label}</strong>
            <p>{scopeCopy[item].runCopy}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

function TechnicalEvidence({ runs }: { runs: AgentRun[] }) {
  return (
    <section className="section technical-block">
        <SectionHeader
          icon={<ShieldCheck size={18} />}
          label="Pattern 3"
          title="Governed Run Flow"
          subtitle="Every AI work item follows the same governed path from request to financial outcome."
        />
      <div className="workflow-grid">
        {[
          ['Business request', 'Scoped project or revenue data enters a session.'],
          ['Task record', 'FastAPI creates queued tasks with domain and priority.'],
          ['Agent execution', 'Registry dispatches single-shot or workflow agents.'],
          ['Provider call', 'LLMClient normalizes provider responses.'],
          ['Trace ledger', 'Prompt, response, tokens, cost, and status are written.'],
          ['Quality queue', 'Async judge scores relevance, faithfulness, completeness, and actionability.'],
          ['Outcome', 'Completed work maps to risk reduction, protected revenue, or quota impact.'],
        ].map(([title, body], index) => (
          <article className="workflow-step" key={title}>
            <span>{String(index + 1).padStart(2, '0')}</span>
            <strong>{title}</strong>
            <p>{body}</p>
          </article>
        ))}
      </div>
      {runs.length > 0 && (
        <div className="run-list compact">
          {runs.map((run) => (
            <RunRow run={run} key={run.id} />
          ))}
        </div>
      )}
    </section>
  )
}

function OutcomesView({
  outcomes,
  sessionImpact,
}: {
  outcomes: BusinessOutcome[]
  sessionImpact: number
}) {
  return (
    <div className="page-stack">
      <section className="section">
        <SectionHeader
          icon={<BarChart3 size={18} />}
          label={money(sessionImpact)}
          title="Outcome Ledger"
          subtitle="Financial outcomes by domain, metric, confidence, and agent run."
        />
        {outcomes.length === 0 ? (
          <EmptyState text="Run a platform or domain demo to populate financial outcomes." />
        ) : (
          <div className="outcome-table">
            <table>
              <thead>
                <tr><th>Domain</th><th>Metric</th><th>Impact</th><th>Confidence</th></tr>
              </thead>
              <tbody>
                {outcomes.map((outcome) => (
                  <tr key={outcome.id}>
                    <td>{outcome.domain}</td>
                    <td>{outcome.metric_name}</td>
                    <td>{money(outcome.financial_impact_usd)}</td>
                    <td>{outcome.confidence_score.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

function OperationsView({
  runs,
  statusMessage,
  onRefresh,
}: {
  runs: AgentRun[]
  statusMessage: string
  onRefresh: () => void
}) {
  return (
    <div className="page-stack">
      <section className="section">
        <SectionHeader
          icon={<Activity size={18} />}
          label="live evidence"
          title="Run Ledger"
          subtitle={statusMessage}
          action={<button className="btn" type="button" onClick={onRefresh}><RefreshCcw size={16} />Refresh</button>}
        />
        {runs.length === 0 ? (
          <EmptyState text="No run evidence yet. Start a demo from Business View." />
        ) : (
          <div className="run-list">
            {recentRuns(runs).map((run) => (
              <RunRow run={run} key={run.id} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

type ArchitectureLayerId =
  | 'experience'
  | 'api'
  | 'orchestration'
  | 'control'
  | 'provider'
  | 'data'
  | 'quality'

type ArchitectureLayer = {
  id: ArchitectureLayerId
  eyebrow: string
  title: string
  summary: string
  input: string
  output: string
  runtime: string
  files: string[]
  responsibilities: string[]
}

const architectureLayers: ArchitectureLayer[] = [
  {
    id: 'experience',
    eyebrow: 'Experience',
    title: 'React control surface',
    summary: 'Business and technical users run platform, domain, or single-agent demos from one shell.',
    input: 'Selected scope, active persona, scenario payload, ProjectPlanning input',
    output: 'Task batch request, live progress state, outcome and trace views',
    runtime: 'Vite React app with CSS-variable theming and SSE/polling refresh',
    files: ['frontend/src/App.tsx', 'frontend/src/api/client.ts', 'frontend/src/hooks/useSSE.ts'],
    responsibilities: [
      'Groups actions by Business View and Technical View.',
      'Rotates Project Management and Revenue Ops demo scenarios after each run.',
      'Shows progress while background tasks execute.',
    ],
  },
  {
    id: 'api',
    eyebrow: 'API Layer',
    title: 'FastAPI task boundary',
    summary: 'Routers validate user requests, create tasks, expose run evidence, and stream run events.',
    input: 'Session ID, agent ID, priority, input payload',
    output: 'Queued Task rows, run ledger responses, outcome summaries, SSE messages',
    runtime: 'FastAPI routers with async SQLAlchemy sessions',
    files: ['backend/app/main.py', 'backend/app/routers/tasks.py', 'backend/app/routers/runs.py'],
    responsibilities: [
      'Creates one task for a single agent or a batch for a domain/platform run.',
      'Resolves active model pricing before the task starts.',
      'Keeps UI-facing endpoints separate from agent implementation details.',
    ],
  },
  {
    id: 'orchestration',
    eyebrow: 'Orchestration',
    title: 'Agent registry and workflow dispatch',
    summary: 'The registry maps persisted agent IDs to executable single-shot agents and the ProjectPlanning workflow.',
    input: 'Queued Task with agent_id and input_payload',
    output: 'Agent output payload and token accounting inside RunContext',
    runtime: 'In-process agent registry plus LangGraph-style workflow nodes',
    files: ['backend/app/agents/registry.py', 'backend/app/agents/base.py', 'backend/app/agents/workflow/project_planning.py'],
    responsibilities: [
      'Dispatches six single-shot agents and one multi-node planning workflow.',
      'Keeps agent IDs stable for UI, API, seed data, and persistence.',
      'Lets workflow nodes create child run evidence under a parent run.',
    ],
  },
  {
    id: 'control',
    eyebrow: 'Control Plane',
    title: 'AgentOps run boundary',
    summary: 'Every agent run passes through the same boundary for trace, metrics, cost, outcomes, and quality enqueueing.',
    input: 'Agent execution context, model pricing ID, prompt and response data',
    output: 'AgentRun, Metric, BusinessOutcome, SSE event, quality job',
    runtime: 'AgentOpsManager.run_context() wraps successful and failed executions',
    files: ['backend/app/agentops/manager.py', 'backend/app/agentops/context.py', 'backend/app/agentops/sse_emitter.py'],
    responsibilities: [
      'Owns status transitions from queued to running to complete or failed.',
      'Persists raw prompt, raw response, structured output, latency, tokens, and cost.',
      'Writes business outcomes only for completed runs with usable output.',
    ],
  },
  {
    id: 'provider',
    eyebrow: 'Provider Layer',
    title: 'LLM provider abstraction',
    summary: 'LLMClient normalizes provider selection and model naming while agents stay provider-agnostic.',
    input: 'Prompt, optional model override, max token target',
    output: 'Normalized LLMResponse with prompt tokens, completion tokens, and raw text',
    runtime: 'Ollama default with Groq and Gemini adapters available',
    files: ['backend/app/llm/client.py', 'backend/app/llm/ollama.py', 'backend/app/core/config.py'],
    responsibilities: [
      'Resolves the active provider and model from runtime settings.',
      'Keeps local Ollama runs priced and visible like cloud runs.',
      'Returns one adapter contract to every agent.',
    ],
  },
  {
    id: 'data',
    eyebrow: 'Data',
    title: 'Run ledger and outcome model',
    summary: 'SQLAlchemy models store the durable evidence needed for replay, audit, and business reporting.',
    input: 'Task state, run context, metrics, pricing, quality score, business impact',
    output: 'Queryable sessions, tasks, runs, outcomes, metrics, and model pricing',
    runtime: 'SQLite locally, async SQLAlchemy model boundaries',
    files: ['backend/app/models/agent_run.py', 'backend/app/models/task.py', 'backend/app/models/business_outcome.py'],
    responsibilities: [
      'Separates requested work from execution evidence.',
      'Stores outcome ledger rows by run, domain, metric, and confidence.',
      'Supports later replacement of metrics storage with a time-series database.',
    ],
  },
  {
    id: 'quality',
    eyebrow: 'Quality',
    title: 'Async judge and trust signal',
    summary: 'Completed outputs are scored after the run so business users see value and technical users see trust evidence.',
    input: 'Completed RunContext and agent quality rubric',
    output: 'Quality score written back to the AgentRun record',
    runtime: 'Background QualityQueue with QualityJudgeAgent',
    files: ['backend/app/agentops/quality_queue.py', 'backend/app/agents/platform/quality_judge.py'],
    responsibilities: [
      'Scores relevance, faithfulness, completeness, and actionability.',
      'Keeps judging asynchronous so the original run can complete quickly.',
      'Feeds quality drift and run trust surfaces.',
    ],
  },
]

const architectureRunSteps = [
  ['01', 'Select scope', 'UI chooses platform, Project Management, Revenue Management, or one agent.'],
  ['02', 'Submit tasks', 'FastAPI writes queued tasks and starts background execution.'],
  ['03', 'Dispatch agent', 'Registry loads the executable agent for each task.'],
  ['04', 'Call provider', 'LLMClient resolves the active model and provider adapter.'],
  ['05', 'Capture run', 'AgentOpsManager writes trace, tokens, latency, cost, and status.'],
  ['06', 'Write value', 'Outcome calculator maps completed output to financial impact.'],
  ['07', 'Judge quality', 'Quality queue scores the output asynchronously.'],
  ['08', 'Refresh UI', 'SSE and polling update progress, trace, outcomes, and architecture evidence.'],
] as const

function ArchitectureView({
  activeProgress,
  onViewChange,
  runs,
  scope,
  sessionImpact,
}: {
  activeProgress: RunProgress | null
  onViewChange: (view: ViewId) => void
  runs: AgentRun[]
  scope: RunScope
  sessionImpact: number
}) {
  const [selectedLayerId, setSelectedLayerId] = useState<ArchitectureLayerId>('control')
  const selectedLayer =
    architectureLayers.find((layer) => layer.id === selectedLayerId) ?? architectureLayers[0]
  const completeRuns = runs.filter((run) => run.status === 'COMPLETE').length
  const failedRuns = runs.filter((run) => run.status === 'FAILED').length
  const recentArchitectureRuns = recentRuns(runs).slice(0, 4)
  const runningLabel =
    activeProgress && !activeProgress.terminal
      ? `${activeProgress.complete + activeProgress.failed}/${activeProgress.total} finished`
      : activeProgress?.terminal
        ? 'Last run complete'
        : 'No active run'

  return (
    <div className="page-stack">
      <section className="section">
        <SectionHeader
          icon={<Layers3 size={18} />}
          label="interactive architecture"
          title="Control Plane Architecture"
          subtitle="Follow a run from UI request to agent execution, evidence capture, outcome ledger, and quality scoring."
          action={
            <div className="button-row">
              <button className="btn" type="button" onClick={() => onViewChange('operations')}>
                <Workflow size={16} /> Inspect trace
              </button>
              <button className="btn" type="button" onClick={() => onViewChange('outcomes')}>
                <FileText size={16} /> Outcome ledger
              </button>
            </div>
          }
        />
        <div className="architecture-overview">
          <article className="architecture-metric">
            <span>Active scope</span>
            <strong>{scopeCopy[scope].label}</strong>
            <p>{scopeAgentIds[scope].length} agents in this run mode</p>
          </article>
          <article className="architecture-metric">
            <span>Run evidence</span>
            <strong>{runs.length}</strong>
            <p>{completeRuns} complete, {failedRuns} failed</p>
          </article>
          <article className="architecture-metric">
            <span>Quality signal</span>
            <strong>{qualityLabel(runs)}</strong>
            <p>async judge score</p>
          </article>
          <article className="architecture-metric">
            <span>Outcome value</span>
            <strong>{sessionImpact > 0 ? money(sessionImpact) : '$0'}</strong>
            <p>from completed business outcomes</p>
          </article>
          <article className="architecture-metric">
            <span>Runtime state</span>
            <strong>{runningLabel}</strong>
            <p>shown from live task/run telemetry</p>
          </article>
        </div>

        <div className="architecture-workspace">
          <div className="architecture-flow-canvas" aria-label="Architecture layers">
            {architectureLayers.map((layer, index) => (
              <button
                className={`architecture-flow-node ${selectedLayer.id === layer.id ? 'active' : ''}`}
                type="button"
                key={layer.id}
                onClick={() => setSelectedLayerId(layer.id)}
              >
                <span>{String(index + 1).padStart(2, '0')}</span>
                <strong>{layer.eyebrow}</strong>
                <small>{layer.title}</small>
                {index < architectureLayers.length - 1 && <em aria-hidden="true">-&gt;</em>}
              </button>
            ))}
          </div>

          <aside className="architecture-detail-panel">
            <span>{selectedLayer.eyebrow}</span>
            <h3>{selectedLayer.title}</h3>
            <p>{selectedLayer.summary}</p>
            <dl>
              <div><dt>Input</dt><dd>{selectedLayer.input}</dd></div>
              <div><dt>Output</dt><dd>{selectedLayer.output}</dd></div>
              <div><dt>Runtime</dt><dd>{selectedLayer.runtime}</dd></div>
            </dl>
            <div className="architecture-responsibilities">
              <strong>What this layer owns</strong>
              <ul>
                {selectedLayer.responsibilities.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="architecture-file-list">
              <strong>Primary files</strong>
              <div>
                {selectedLayer.files.map((file) => (
                  <code key={file}>{file}</code>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="section">
        <SectionHeader
          icon={<ShieldCheck size={18} />}
          label="runtime contract"
          title="How a Run Moves Through the Platform"
          subtitle="This is the governed execution path used by platform, domain, and single-agent runs."
        />
        <div className="architecture-run-path">
          {architectureRunSteps.map(([index, title, body]) => (
            <article className="architecture-run-step" key={index}>
              <span>{index}</span>
              <strong>{title}</strong>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section">
        <SectionHeader
          icon={<Activity size={18} />}
          label="live evidence"
          title="Architecture Connected to This Session"
          subtitle="Recent runs prove the architecture path: task, agent, provider, trace, quality, and outcome evidence."
          action={
            <button className="btn" type="button" onClick={() => onViewChange('operations')}>
              <RefreshCcw size={16} />Open runs
            </button>
          }
        />
        {activeProgress && <RunProgressPanel progress={activeProgress} />}
        {recentArchitectureRuns.length === 0 ? (
          <EmptyState text="No run evidence yet. Start a run to connect the architecture diagram to live data." />
        ) : (
          <div className="architecture-live-list">
            {recentArchitectureRuns.map((run) => (
              <article className="architecture-live-run" key={run.id}>
                <div>
                  <strong>{run.agent_id}</strong>
                  <span>{run.run_type} - {run.model_used}</span>
                </div>
                <b className={`status-pill ${run.status === 'FAILED' ? 'bad' : run.status === 'COMPLETE' ? 'good' : 'warn'}`}>{run.status}</b>
                <dl>
                  <div><dt>Tokens</dt><dd>{run.total_tokens}</dd></div>
                  <div><dt>Latency</dt><dd>{run.latency_ms} ms</dd></div>
                  <div><dt>Quality</dt><dd>{run.quality_score?.toFixed(2) ?? 'pending'}</dd></div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function SettingsView({
  availableAgentIds,
  scope,
  selectedAgent,
  setSelectedAgent,
}: {
  availableAgentIds: AgentKey[]
  scope: RunScope
  selectedAgent: AgentKey
  setSelectedAgent: (agent: AgentKey) => void
}) {
  return (
    <div className="page-stack">
      <section className="section">
        <SectionHeader
          icon={<Settings size={18} />}
          label="configuration"
          title="Settings"
          subtitle="CSS variables control the color scheme. Runtime settings are grouped by operator decision."
        />
        <div className="settings-grid">
          <SettingPanel title="Run Defaults">
            <div><span>Default scope</span><b>{scopeCopy[scope].label}</b></div>
            <div><span>Demo mode</span><b>Enterprise walkthrough</b></div>
            <div><span>Max concurrent agents</span><b>7</b></div>
          </SettingPanel>
          <SettingPanel title="Provider and Quality">
            <div><span>Provider</span><b>Ollama</b></div>
            <div><span>Model</span><b>llama3.2:latest</b></div>
            <div><span>Quality judge</span><b>async</b></div>
          </SettingPanel>
          <SettingPanel title="Single Agent">
            <label htmlFor="settings-agent">{scopeCopy[scope].label} agent</label>
            <AgentSelect
              id="settings-agent"
              agentIds={availableAgentIds}
              value={selectedAgent}
              onChange={(event) => setSelectedAgent(event.target.value as AgentKey)}
            />
          </SettingPanel>
        </div>
      </section>
    </div>
  )
}

function AgentSelect({
  agentIds,
  id,
  onChange,
  value,
}: {
  agentIds: AgentKey[]
  id: string
  onChange: ChangeEventHandler<HTMLSelectElement>
  value: AgentKey
}) {
  const projectOptions = agentIds.filter((agentId) => agentCatalog[agentId].domain === 'PROJECT_DELIVERY')
  const revenueOptions = agentIds.filter((agentId) => agentCatalog[agentId].domain === 'REVENUE_OPS')

  if (projectOptions.length > 0 && revenueOptions.length > 0) {
    return (
      <select id={id} value={value} onChange={onChange}>
        <optgroup label="Project Management">
          {projectOptions.map((agentId) => (
            <option value={agentId} key={agentId}>
              {agentCatalog[agentId].name}
            </option>
          ))}
        </optgroup>
        <optgroup label="Revenue Management">
          {revenueOptions.map((agentId) => (
            <option value={agentId} key={agentId}>
              {agentCatalog[agentId].name}
            </option>
          ))}
        </optgroup>
      </select>
    )
  }

  return (
    <select id={id} value={value} onChange={onChange}>
      {agentIds.map((agentId) => (
        <option value={agentId} key={agentId}>
          {agentCatalog[agentId].name}
        </option>
      ))}
    </select>
  )
}

function RunProgressPanel({ progress }: { progress: RunProgress }) {
  const elapsedSeconds = Math.max(0, Math.round((Date.now() - progress.active.startedAt) / 1000))
  const runningLabel = progress.terminal
    ? progress.failed > 0
      ? 'Finished with failures'
      : 'Complete'
    : progress.running > 0
      ? `${progress.running} running`
      : 'Queued'

  return (
    <div className={`run-progress-panel ${progress.terminal ? 'terminal' : 'active'}`}>
      <div className="run-progress-head">
        <span>{runningLabel}</span>
        <strong>{progress.active.label}</strong>
        <em>{elapsedSeconds}s elapsed</em>
      </div>
      <div className="run-progress-bar" aria-label={`${progress.percent}% complete`}>
        <i style={{ width: `${progress.percent}%` }} />
      </div>
      <div className="run-progress-summary">
        <span>{progress.complete} complete</span>
        <span>{progress.failed} failed</span>
        <span>{progress.total - progress.complete - progress.failed} in flight</span>
      </div>
      <div className="agent-status-list">
        {progress.statuses.map(({ agent, status }) => (
          <div className={`agent-status ${status.toLowerCase()}`} key={agent.id}>
            <span>{agent.name}</span>
            <b>{status.toLowerCase()}</b>
          </div>
        ))}
      </div>
    </div>
  )
}

function ScenarioCard({ scenario }: { scenario: DemoScenario }) {
  return (
    <article className="scenario-card">
      <span>{scenario.domain === 'project' ? 'Project Management input' : 'Revenue Ops input'}</span>
      <strong>{scenario.title}</strong>
      <p>{scenario.summary}</p>
    </article>
  )
}

function ProjectPlanningInputCard({
  input,
  scenario,
  setInput,
}: {
  input: ProjectPlanningInput
  scenario: DemoScenario
  setInput: (input: ProjectPlanningInput) => void
}) {
  const update = (patch: Partial<ProjectPlanningInput>) => setInput({ ...input, ...patch })
  return (
    <article className="project-input-card">
      <div className="project-input-head">
        <span>ProjectPlanningAgent input</span>
        <strong>{scenario.title}</strong>
      </div>
      <label htmlFor="project-instruction">Project instruction</label>
      <textarea
        id="project-instruction"
        value={input.instruction}
        onChange={(event) => update({ instruction: event.target.value })}
      />
      <div className="project-input-grid">
        <label htmlFor="project-timeline">
          Timeline weeks
          <input
            id="project-timeline"
            min={1}
            type="number"
            value={input.timeline_weeks}
            onChange={(event) => update({ timeline_weeks: Number(event.target.value) })}
          />
        </label>
        <label htmlFor="project-revenue">
          Committed revenue
          <input
            id="project-revenue"
            min={0}
            step={10000}
            type="number"
            value={input.committed_revenue_usd}
            onChange={(event) => update({ committed_revenue_usd: Number(event.target.value) })}
          />
        </label>
      </div>
      <div className="project-team-list">
        <span>Team context</span>
        <div>
          {input.team_members.map((member, index) => (
            <b key={`${String(member.name ?? 'member')}-${index}`}>
              {String(member.name ?? `Member ${index + 1}`)}
            </b>
          ))}
        </div>
      </div>
    </article>
  )
}

function Kpi({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="kpi">
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{detail}</em>
    </article>
  )
}

function StoryStep({
  copy,
  emphasis = false,
  index,
  title,
}: {
  copy: string
  emphasis?: boolean
  index: string
  title: string
}) {
  return (
    <article className={`story-step ${emphasis ? 'emphasis' : ''}`}>
      <span>{index}</span>
      <strong>{title}</strong>
      <p>{copy}</p>
    </article>
  )
}

function InfoCard({
  copy,
  label,
  title,
  tone,
}: {
  copy: string
  label: string
  title: string
  tone: 'good' | 'warn'
}) {
  return (
    <article className="info-card">
      <span className={`status-pill ${tone}`}>{label}</span>
      <strong>{title}</strong>
      <p>{copy}</p>
    </article>
  )
}

function SectionHeader({
  action,
  icon,
  label,
  subtitle,
  title,
}: {
  action?: ReactNode
  icon: ReactNode
  label: string
  subtitle: string
  title: string
}) {
  return (
    <div className="section-header">
      <div className="section-title">
        <span className="section-icon">{icon}</span>
        <div>
          <span>{label}</span>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
      </div>
      {action}
    </div>
  )
}

function RunRow({ run }: { run: AgentRun }) {
  const statusTone = run.status === 'FAILED' ? 'bad' : run.status === 'COMPLETE' ? 'good' : 'warn'
  return (
    <article className="run-row">
      <div>
        <strong>{run.agent_id}</strong>
        <span>{run.run_type} - {run.model_used}</span>
      </div>
      <span className={`status-pill ${statusTone}`}>{run.status}</span>
      <dl>
        <div><dt>Latency</dt><dd>{run.latency_ms} ms</dd></div>
        <div><dt>Tokens</dt><dd>{run.total_tokens}</dd></div>
        <div><dt>Quality</dt><dd>{run.quality_score?.toFixed(2) ?? 'pending'}</dd></div>
      </dl>
      {run.error_message && <p className="run-error">{run.error_message}</p>}
    </article>
  )
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>
}

function SettingPanel({ children, title }: { children: ReactNode; title: string }) {
  return (
    <article className="setting-panel">
      <h4>{title}</h4>
      {children}
    </article>
  )
}
