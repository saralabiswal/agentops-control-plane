import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ChangeEventHandler, ReactNode } from 'react'
import {
  Activity,
  BarChart3,
  Boxes,
  Cpu,
  Database,
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
import type {
  AgentRun,
  BusinessOutcome,
  ModelPricing,
  Persona,
  RuntimeSettings,
  RuntimeProvider,
  Session,
  TaskSubmit,
} from './api/types'
import { useSSE } from './hooks/useSSE'
import { useSession } from './hooks/useSession'

const AUTHOR = 'Sarala Biswal'
const API_CALLS_PER_AGENT_RUN = 4
const COMPUTE_VCPU_PER_AGENT_RUN = 1
const COMPUTE_MEMORY_GIB_PER_AGENT_RUN = 0.5

type RunScope = 'platform' | 'project' | 'revenue'
type ViewId = 'story' | 'outcomes' | 'data' | 'run' | 'evidence' | 'architecture' | 'settings'
type ProviderKey = 'ollama' | 'groq' | 'gemini'

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
  payloads: Partial<Record<AgentKey, Record<string, unknown>>>
  scenarioTitles: Partial<Record<AgentConfig['domain'], string>>
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

type EvidenceDomain = 'PROJECT_DELIVERY' | 'REVENUE_OPS' | 'PLATFORM'

type EvidenceRunGroup =
  | {
      kind: 'run'
      run: AgentRun
    }
  | {
      kind: 'workflow'
      parent: AgentRun
      nodes: AgentRun[]
    }

type EvidenceGroup = {
  kind: 'domain'
  domain: EvidenceDomain
  label: string
  items: EvidenceRunGroup[]
}

type PayloadPreviewGroup = {
  domain: AgentConfig['domain']
  label: string
  scenarioTitle: string
  items: Array<{
    agent: AgentConfig
    payload: Record<string, unknown>
  }>
}

type ProviderConfig = {
  id: ProviderKey
  label: string
  description: string
  nextAction: string
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

const providerCatalog: Record<ProviderKey, ProviderConfig> = {
  ollama: {
    id: 'ollama',
    label: 'Ollama',
    description: 'Local default provider for the demo and development runtime.',
    nextAction: 'Run a platform or domain demo locally with priced token accounting.',
  },
  groq: {
    id: 'groq',
    label: 'Groq',
    description: 'Cloud provider adapter available when AGENTOPS_GROQ_API_KEY is configured.',
    nextAction: 'Add the Groq API key in backend/.env before using this provider for live runs.',
  },
  gemini: {
    id: 'gemini',
    label: 'Gemini',
    description: 'Google Gemini adapter available when AGENTOPS_GEMINI_API_KEY is configured.',
    nextAction: 'Add the Gemini API key in backend/.env before using this provider for live runs.',
  },
}

const providerOrder: ProviderKey[] = ['ollama', 'groq', 'gemini']

const fallbackModelsByProvider: Record<ProviderKey, string[]> = {
  ollama: ['llama3.2:3b', 'llama3.2:latest', 'llama3.1:8b', 'llama3.1:latest'],
  groq: ['llama-3.3-70b-versatile'],
  gemini: ['gemini-2.0-flash'],
}

const agentCatalog: Record<AgentKey, AgentConfig> = {
  'agent-sprint-risk': {
    id: 'agent-sprint-risk',
    name: 'SprintRiskAgent',
    domain: 'PROJECT_DELIVERY',
    shortDomain: 'Project Management',
    description: 'Assesses sprint risk, delivery confidence, and mitigations.',
    payload: {
      sprint_name: 'Northstar Portal Phase 1',
      customer: 'Harbor Retail Group',
      business_context: 'Customer portal launch supports a $520K services commitment before the summer retail peak.',
      team_size: 4,
      days_remaining: 10,
      total_tasks: 18,
      completed_tasks: 7,
      velocity_history: [12, 10, 8],
      remaining_engineering_hours: 238,
      remaining_story_points: 34,
      available_engineering_hours: 192,
      external_dependencies: [
        'Customer SSO metadata approval',
        'Claims export file from operations',
      ],
      capacity_notes: 'Frontend engineer is 80% available; QA is shared with production release support.',
      delay_cost_per_week_usd: 62000,
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
        { id: 'AUTH-41', skill: 'identity', estimate_hours: 22, priority: 'HIGH' },
        { id: 'PORTAL-87', skill: 'frontend', estimate_hours: 30, priority: 'HIGH' },
        { id: 'CLAIMS-54', skill: 'backend', estimate_hours: 28, priority: 'HIGH' },
        { id: 'QA-218', skill: 'quality', estimate_hours: 24, priority: 'HIGH' },
        { id: 'OPS-33', skill: 'enablement', estimate_hours: 14, priority: 'NORMAL' },
        { id: 'OBS-18', skill: 'observability', estimate_hours: 16, priority: 'NORMAL' },
        { id: 'UAT-12', skill: 'customer-success', estimate_hours: 18, priority: 'HIGH' },
        { id: 'REL-47', skill: 'release', estimate_hours: 12, priority: 'NORMAL' },
      ],
      team_members: [
        { name: 'Iris Chen', role: 'Full-stack Lead', skills: ['identity', 'backend', 'frontend'], load_pct: 74, availability_pct: 80 },
        { name: 'Samir Gupta', role: 'Frontend Engineer', skills: ['frontend', 'release'], load_pct: 68, availability_pct: 80 },
        { name: 'Marta Silva', role: 'QA Analyst', skills: ['quality', 'customer-success'], load_pct: 72, availability_pct: 50 },
        { name: 'Theo Martin', role: 'Backend Engineer', skills: ['backend', 'observability', 'enablement'], load_pct: 61, availability_pct: 90 },
      ],
      sprint_weeks: 2,
      remaining_engineering_hours: 238,
      available_engineering_hours: 192,
      avg_task_hours: 22,
      hourly_rate: 145,
    },
  },
  'agent-delivery-forecast': {
    id: 'agent-delivery-forecast',
    name: 'DeliveryForecastAgent',
    domain: 'PROJECT_DELIVERY',
    shortDomain: 'Project Management',
    description: 'Forecasts milestone confidence and delivery-linked revenue exposure.',
    payload: {
      milestone_name: 'Northstar phase-1 customer portal go-live',
      committed_revenue_usd: 520000,
      target_date: '2026-07-08',
      current_date: '2026-06-09',
      backlog_count: 23,
      avg_velocity: 9,
      sprint_length_days: 14,
      blockers: [
        'SSO metadata has not been approved by customer IT',
        'Claims export sample is missing production edge cases',
      ],
      capacity_changes: 'QA analyst is available 50% until June 17 due to release support.',
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
        'Create a recovery plan for Northstar portal phase 1 with epics for SSO, claims export, customer UAT, release readiness, named owners, risk tradeoffs, and executive decision points.',
      team_members: [
        { name: 'Iris Chen', role: 'Full-stack Lead', skills: ['identity', 'backend', 'frontend'], availability_pct: 80 },
        { name: 'Samir Gupta', role: 'Frontend Engineer', skills: ['frontend', 'release'], availability_pct: 80 },
        { name: 'Marta Silva', role: 'QA Analyst', skills: ['quality', 'customer-success'], availability_pct: 50 },
        { name: 'Theo Martin', role: 'Backend Engineer', skills: ['backend', 'observability', 'enablement'], availability_pct: 90 },
      ],
      timeline_weeks: 4,
      committed_revenue_usd: 520000,
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
      renewal_arr_usd: 900000,
      expansion_arr_usd: 260000,
      segment: 'Enterprise Financial Services',
      contract_end_date: '2026-09-30',
      days_to_renewal: 113,
      login_frequency_30d: 18,
      feature_adoption_score: 5.7,
      support_tickets_90d: 14,
      nps_score: 4,
      last_csm_touchpoint: '2026-05-08',
      upsell_conversations: 0,
      historical_save_rate: 0.42,
      account_owner: 'Jordan Lee',
      csm_owner: 'Rhea Morgan',
      exec_sponsor: 'Daniel Kim',
    },
  },
  'agent-churn-signal': {
    id: 'agent-churn-signal',
    name: 'ChurnSignalAgent',
    domain: 'REVENUE_OPS',
    shortDomain: 'Revenue Management',
    description: 'Detects early churn signals and intervention value.',
    payload: {
      account_name: 'Acme Financial',
      account_arr: 900000,
      contract_end_date: '2026-09-30',
      days_to_renewal: 113,
      login_trend: 'finance admin usage down 38% over 30 days',
      adoption_trend: 'invoice automation flat, reporting exports increasing',
      ticket_sentiment: 'negative',
      exec_engagement: 'economic buyer missed two QBRs and delegated renewal call',
      competitor_mentions: 3,
      contract_downloads: 2,
      early_intervention_value: 0.45,
      account_owner: 'Jordan Lee',
      csm_owner: 'Rhea Morgan',
      exec_sponsor: 'Daniel Kim',
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
      closed_to_date_usd: 620000,
      commit_pipeline_usd: 430000,
      best_case_pipeline_usd: 1060000,
      quarter_close_date: '2026-06-30',
      days_remaining: 21,
      historical_close_rate: 0.31,
      avg_sales_cycle_days: 52,
      pipeline_deals: [
        {
          account: 'Helio Manufacturing',
          arr: 520000,
          crm_probability: 0.62,
          stage: 'Legal review',
          close_plan: 'redline turnaround due Friday',
          risk: 'procurement owner on PTO',
          next_step: 'VP Sales to confirm signing authority',
        },
        {
          account: 'Beacon Health',
          arr: 410000,
          crm_probability: 0.44,
          stage: 'Security review',
          close_plan: 'security questionnaire pending',
          risk: 'SOC2 exception requested',
          next_step: 'Security lead to join customer call',
        },
        {
          account: 'Koru Energy',
          arr: 360000,
          crm_probability: 0.35,
          stage: 'Business case',
          close_plan: 'ROI case not signed by CFO',
          risk: 'budget approval moved to July',
          next_step: 'RevOps to rebuild value case with usage data',
        },
        {
          account: 'Northport Insurance',
          arr: 280000,
          crm_probability: 0.28,
          stage: 'Solution validation',
          close_plan: 'claims automation pilot results due next week',
          risk: 'pilot sponsor has not confirmed success criteria',
          next_step: 'AE and SE to complete pilot scorecard',
        },
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
    id: 'northstar-portal',
    domain: 'project',
    title: 'Northstar $520K portal launch',
    summary:
      'Harbor Retail portal launch has SSO, claims export, and QA capacity risk against $520K in booked services value.',
    payloads: {
      'agent-sprint-risk': agentCatalog['agent-sprint-risk'].payload,
      'agent-resource-alloc': agentCatalog['agent-resource-alloc'].payload,
      'agent-delivery-forecast': agentCatalog['agent-delivery-forecast'].payload,
      'agent-project-planning': agentCatalog['agent-project-planning'].payload,
    },
  },
  {
    id: 'orion-launch',
    domain: 'project',
    title: 'Orion v4.2 $1.25M bank launch',
    summary:
      'FirstWest Bank launch has identity, fraud-service, mobile, and security evidence risk against $1.25M in booked delivery value.',
    payloads: {
      'agent-sprint-risk': {
        sprint_name: 'Orion v4.2 Launch Readiness',
        team_size: 7,
        days_remaining: 12,
        total_tasks: 52,
        completed_tasks: 23,
        velocity_history: [24, 21, 18],
        remaining_engineering_hours: 612,
        remaining_story_points: 91,
        available_engineering_hours: 470,
        external_dependencies: [
          'Identity provider production certificate',
          'Fraud-service rate limit approval',
          'Security exception sign-off',
        ],
        capacity_notes: 'Tech lead is at 60% due to Sev-2 support; QA lead is split with release audit.',
        delay_cost_per_week_usd: 185000,
      },
      'agent-resource-alloc': {
        tasks: [
          { id: 'OIDC-214', skill: 'identity', estimate_hours: 28, priority: 'HIGH' },
          { id: 'OIDC-219', skill: 'identity', estimate_hours: 18, priority: 'HIGH' },
          { id: 'FRAUD-88', skill: 'backend', estimate_hours: 36, priority: 'HIGH' },
          { id: 'FRAUD-91', skill: 'backend', estimate_hours: 30, priority: 'HIGH' },
          { id: 'SEC-72', skill: 'security', estimate_hours: 24, priority: 'HIGH' },
          { id: 'SEC-76', skill: 'security', estimate_hours: 18, priority: 'HIGH' },
          { id: 'QA-140', skill: 'quality', estimate_hours: 34, priority: 'HIGH' },
          { id: 'QA-143', skill: 'automation', estimate_hours: 26, priority: 'HIGH' },
          { id: 'MOB-302', skill: 'mobile', estimate_hours: 32, priority: 'HIGH' },
          { id: 'REL-31', skill: 'release', estimate_hours: 16, priority: 'NORMAL' },
          { id: 'OBS-44', skill: 'observability', estimate_hours: 20, priority: 'NORMAL' },
          { id: 'UAT-27', skill: 'customer-success', estimate_hours: 18, priority: 'NORMAL' },
        ],
        team_members: [
          { name: 'Asha Rao', role: 'Tech Lead', skills: ['identity', 'backend', 'security'], load_pct: 82, availability_pct: 60 },
          { name: 'Mateo Cruz', role: 'Senior Backend Engineer', skills: ['backend', 'release'], load_pct: 68, availability_pct: 85 },
          { name: 'Lina Park', role: 'QA Lead', skills: ['quality', 'automation', 'security'], load_pct: 76, availability_pct: 70 },
          { name: 'Devon Shah', role: 'Platform Engineer', skills: ['release', 'observability', 'backend'], load_pct: 55, availability_pct: 90 },
          { name: 'Camila Torres', role: 'Mobile Engineer', skills: ['mobile', 'frontend', 'quality'], load_pct: 63, availability_pct: 85 },
          { name: 'Ben Wallace', role: 'Security Engineer', skills: ['security', 'identity'], load_pct: 70, availability_pct: 75 },
          { name: 'Rina Okafor', role: 'Implementation Manager', skills: ['customer-success', 'release', 'enablement'], load_pct: 64, availability_pct: 80 },
        ],
        sprint_weeks: 3,
        remaining_engineering_hours: 612,
        available_engineering_hours: 470,
        avg_task_hours: 24,
        hourly_rate: 165,
      },
      'agent-delivery-forecast': {
        milestone_name: 'Orion v4.2 FirstWest Bank launch',
        committed_revenue_usd: 1250000,
        target_date: '2026-07-18',
        current_date: '2026-06-09',
        backlog_count: 58,
        avg_velocity: 20,
        sprint_length_days: 14,
        blockers: [
          'Fraud-service performance test has not passed at target volume',
          'Final SOC2 evidence package is missing two controls',
          'Mobile app release candidate is waiting on bank branding approval',
        ],
        capacity_changes: 'Two engineers are covering production support until June 14.',
      },
      'agent-project-planning': {
        instruction:
          'Create a recovery plan for Orion v4.2 launch readiness with epics for identity, fraud-service readiness, security evidence, mobile release, QA automation, owners, risk tradeoffs, and executive decision points.',
        team_members: [
          { name: 'Asha Rao', role: 'Tech Lead', skills: ['identity', 'backend', 'security'], availability_pct: 60 },
          { name: 'Mateo Cruz', role: 'Senior Backend Engineer', skills: ['backend', 'release'], availability_pct: 85 },
          { name: 'Lina Park', role: 'QA Lead', skills: ['quality', 'automation', 'security'], availability_pct: 70 },
          { name: 'Devon Shah', role: 'Platform Engineer', skills: ['release', 'observability', 'backend'], availability_pct: 90 },
          { name: 'Camila Torres', role: 'Mobile Engineer', skills: ['mobile', 'frontend', 'quality'], availability_pct: 85 },
          { name: 'Ben Wallace', role: 'Security Engineer', skills: ['security', 'identity'], availability_pct: 75 },
          { name: 'Rina Okafor', role: 'Implementation Manager', skills: ['customer-success', 'release', 'enablement'], availability_pct: 80 },
        ],
        timeline_weeks: 6,
        committed_revenue_usd: 1250000,
      },
    },
  },
  {
    id: 'atlas-migration',
    domain: 'project',
    title: 'Summit Energy cloud cutover',
    summary:
      'Atlas migration cutover has replication, DR, security, and platform capacity pressure against $2.4M in contracted launch value.',
    payloads: {
      'agent-sprint-risk': {
        sprint_name: 'Atlas Migration Cutover',
        team_size: 10,
        days_remaining: 15,
        total_tasks: 76,
        completed_tasks: 31,
        velocity_history: [31, 28, 23],
        remaining_engineering_hours: 1118,
        remaining_story_points: 168,
        available_engineering_hours: 860,
        external_dependencies: [
          'Network allowlist approval',
          'Database replication freeze window',
          'Customer DR test window',
          'Security architecture review',
        ],
        capacity_notes: 'Two platform engineers are on incident rotation',
        delay_cost_per_week_usd: 320000,
      },
      'agent-resource-alloc': {
        tasks: [
          { id: 'NET-31', skill: 'network', estimate_hours: 26, priority: 'HIGH' },
          { id: 'NET-37', skill: 'network', estimate_hours: 22, priority: 'HIGH' },
          { id: 'DB-82', skill: 'database', estimate_hours: 42, priority: 'HIGH' },
          { id: 'DB-91', skill: 'database', estimate_hours: 38, priority: 'HIGH' },
          { id: 'CUT-17', skill: 'platform', estimate_hours: 34, priority: 'HIGH' },
          { id: 'CUT-23', skill: 'platform', estimate_hours: 32, priority: 'HIGH' },
          { id: 'DR-22', skill: 'reliability', estimate_hours: 36, priority: 'HIGH' },
          { id: 'DR-28', skill: 'reliability', estimate_hours: 30, priority: 'HIGH' },
          { id: 'SEC-118', skill: 'security', estimate_hours: 28, priority: 'HIGH' },
          { id: 'OBS-09', skill: 'observability', estimate_hours: 20, priority: 'NORMAL' },
          { id: 'REL-62', skill: 'release', estimate_hours: 18, priority: 'NORMAL' },
          { id: 'DATA-44', skill: 'analytics', estimate_hours: 24, priority: 'NORMAL' },
          { id: 'RUN-19', skill: 'enablement', estimate_hours: 16, priority: 'NORMAL' },
          { id: 'UAT-33', skill: 'customer-success', estimate_hours: 18, priority: 'NORMAL' },
        ],
        team_members: [
          { name: 'Ravi Iyer', role: 'Platform Lead', skills: ['platform', 'observability', 'reliability'], load_pct: 78, availability_pct: 65 },
          { name: 'Mina Chen', role: 'Database Engineer', skills: ['database', 'backend'], load_pct: 66, availability_pct: 85 },
          { name: 'Omar Haddad', role: 'Network Engineer', skills: ['network', 'platform'], load_pct: 82, availability_pct: 70 },
          { name: 'Grace Lee', role: 'Reliability Engineer', skills: ['reliability', 'observability'], load_pct: 58, availability_pct: 90 },
          { name: 'Sofia Kim', role: 'Security Architect', skills: ['security', 'network'], load_pct: 74, availability_pct: 75 },
          { name: 'Jonas Weber', role: 'Data Platform Engineer', skills: ['analytics', 'database', 'platform'], load_pct: 67, availability_pct: 85 },
          { name: 'Maya Brooks', role: 'Release Manager', skills: ['release', 'enablement'], load_pct: 60, availability_pct: 80 },
          { name: 'Ethan Price', role: 'Implementation Lead', skills: ['customer-success', 'release'], load_pct: 58, availability_pct: 85 },
          { name: 'Leah Stone', role: 'Backend Engineer', skills: ['backend', 'platform'], load_pct: 64, availability_pct: 90 },
          { name: 'Akira Sato', role: 'SRE', skills: ['reliability', 'observability', 'platform'], load_pct: 72, availability_pct: 70 },
        ],
        sprint_weeks: 4,
        remaining_engineering_hours: 1118,
        available_engineering_hours: 860,
        avg_task_hours: 28,
        hourly_rate: 175,
      },
      'agent-delivery-forecast': {
        milestone_name: 'Summit Energy Atlas migration cutover',
        committed_revenue_usd: 2400000,
        target_date: '2026-07-26',
        current_date: '2026-06-09',
        backlog_count: 88,
        avg_velocity: 26,
        sprint_length_days: 14,
        blockers: [
          'Database replication dry run has not met RPO',
          'Customer DR test window is not confirmed',
          'Network allowlist request is waiting on customer security review',
        ],
        capacity_changes: 'Platform team has two engineers on incident rotation',
      },
      'agent-project-planning': {
        instruction:
          'Build an Atlas migration cutover plan with epics for network readiness, database replication, DR validation, observability, rollback criteria, owners, and executive decision points.',
        team_members: [
          { name: 'Ravi Iyer', role: 'Platform Lead', skills: ['platform', 'observability', 'reliability'], availability_pct: 65 },
          { name: 'Mina Chen', role: 'Database Engineer', skills: ['database', 'backend'], availability_pct: 85 },
          { name: 'Omar Haddad', role: 'Network Engineer', skills: ['network', 'platform'], availability_pct: 70 },
          { name: 'Grace Lee', role: 'Reliability Engineer', skills: ['reliability', 'observability'], availability_pct: 90 },
          { name: 'Sofia Kim', role: 'Security Architect', skills: ['security', 'network'], availability_pct: 75 },
          { name: 'Jonas Weber', role: 'Data Platform Engineer', skills: ['analytics', 'database', 'platform'], availability_pct: 85 },
          { name: 'Maya Brooks', role: 'Release Manager', skills: ['release', 'enablement'], availability_pct: 80 },
          { name: 'Ethan Price', role: 'Implementation Lead', skills: ['customer-success', 'release'], availability_pct: 85 },
          { name: 'Leah Stone', role: 'Backend Engineer', skills: ['backend', 'platform'], availability_pct: 90 },
          { name: 'Akira Sato', role: 'SRE', skills: ['reliability', 'observability', 'platform'], availability_pct: 70 },
        ],
        timeline_weeks: 8,
        committed_revenue_usd: 2400000,
      },
    },
  },
  {
    id: 'helios-consent-platform',
    domain: 'project',
    title: 'Helios $690K consent platform',
    summary:
      'Northlake Health needs consent capture, audit exports, and security review completed before a regulatory reporting deadline.',
    payloads: {
      'agent-sprint-risk': {
        sprint_name: 'Helios Consent Platform Release',
        team_size: 5,
        days_remaining: 9,
        total_tasks: 29,
        completed_tasks: 11,
        velocity_history: [15, 13, 11],
        remaining_engineering_hours: 356,
        remaining_story_points: 53,
        available_engineering_hours: 280,
        external_dependencies: [
          'HIPAA audit export approval',
          'Customer legal review for consent language',
          'EHR sandbox access renewal',
        ],
        capacity_notes: 'Security engineer is shared with a compliance audit; QA has one tester out for two days.',
        delay_cost_per_week_usd: 88000,
      },
      'agent-resource-alloc': {
        tasks: [
          { id: 'CONSENT-74', skill: 'frontend', estimate_hours: 26, priority: 'HIGH' },
          { id: 'CONSENT-81', skill: 'backend', estimate_hours: 32, priority: 'HIGH' },
          { id: 'AUDIT-22', skill: 'compliance', estimate_hours: 28, priority: 'HIGH' },
          { id: 'EHR-47', skill: 'integration', estimate_hours: 30, priority: 'HIGH' },
          { id: 'SEC-144', skill: 'security', estimate_hours: 22, priority: 'HIGH' },
          { id: 'QA-231', skill: 'quality', estimate_hours: 26, priority: 'HIGH' },
          { id: 'DOC-64', skill: 'enablement', estimate_hours: 12, priority: 'NORMAL' },
          { id: 'REL-88', skill: 'release', estimate_hours: 14, priority: 'NORMAL' },
          { id: 'OBS-71', skill: 'observability', estimate_hours: 16, priority: 'NORMAL' },
        ],
        team_members: [
          { name: 'Nora Ali', role: 'Product Engineer', skills: ['frontend', 'backend'], load_pct: 70, availability_pct: 80 },
          { name: 'Julian Reed', role: 'Integration Engineer', skills: ['integration', 'backend'], load_pct: 73, availability_pct: 85 },
          { name: 'Mei Lin', role: 'Compliance Analyst', skills: ['compliance', 'enablement'], load_pct: 78, availability_pct: 75 },
          { name: 'Hector Diaz', role: 'Security Engineer', skills: ['security', 'observability'], load_pct: 80, availability_pct: 60 },
          { name: 'Tara Evans', role: 'QA Engineer', skills: ['quality', 'release'], load_pct: 66, availability_pct: 70 },
        ],
        sprint_weeks: 3,
        remaining_engineering_hours: 356,
        available_engineering_hours: 280,
        avg_task_hours: 22,
        hourly_rate: 158,
      },
      'agent-delivery-forecast': {
        milestone_name: 'Northlake Health Helios consent go-live',
        committed_revenue_usd: 690000,
        target_date: '2026-07-12',
        current_date: '2026-06-09',
        backlog_count: 34,
        avg_velocity: 13,
        sprint_length_days: 14,
        blockers: [
          'EHR sandbox access expires before final regression',
          'Consent language is still under customer legal review',
          'Security test evidence is missing audit export coverage',
        ],
        capacity_changes: 'Security capacity is 60% until the compliance audit is closed.',
      },
      'agent-project-planning': {
        instruction:
          'Create a recovery plan for Helios consent platform with epics for consent UX, EHR integration, audit exports, security evidence, QA regression, owners, and executive decision points.',
        team_members: [
          { name: 'Nora Ali', role: 'Product Engineer', skills: ['frontend', 'backend'], availability_pct: 80 },
          { name: 'Julian Reed', role: 'Integration Engineer', skills: ['integration', 'backend'], availability_pct: 85 },
          { name: 'Mei Lin', role: 'Compliance Analyst', skills: ['compliance', 'enablement'], availability_pct: 75 },
          { name: 'Hector Diaz', role: 'Security Engineer', skills: ['security', 'observability'], availability_pct: 60 },
          { name: 'Tara Evans', role: 'QA Engineer', skills: ['quality', 'release'], availability_pct: 70 },
        ],
        timeline_weeks: 5,
        committed_revenue_usd: 690000,
      },
    },
  },
  {
    id: 'argus-warehouse-rollout',
    domain: 'project',
    title: 'Argus $1.75M warehouse rollout',
    summary:
      'OmniMart rollout depends on scanner integration, inventory reconciliation, and regional training before peak season.',
    payloads: {
      'agent-sprint-risk': {
        sprint_name: 'Argus Warehouse Automation Wave 2',
        team_size: 8,
        days_remaining: 14,
        total_tasks: 61,
        completed_tasks: 25,
        velocity_history: [27, 24, 20],
        remaining_engineering_hours: 820,
        remaining_story_points: 122,
        available_engineering_hours: 650,
        external_dependencies: [
          'Scanner firmware certification',
          'Warehouse operations UAT schedule',
          'ERP inventory feed approval',
        ],
        capacity_notes: 'Two engineers are traveling for site pilots; training lead is split across three regions.',
        delay_cost_per_week_usd: 240000,
      },
      'agent-resource-alloc': {
        tasks: [
          { id: 'SCAN-118', skill: 'integration', estimate_hours: 36, priority: 'HIGH' },
          { id: 'SCAN-126', skill: 'device', estimate_hours: 30, priority: 'HIGH' },
          { id: 'INV-204', skill: 'backend', estimate_hours: 40, priority: 'HIGH' },
          { id: 'ERP-98', skill: 'integration', estimate_hours: 34, priority: 'HIGH' },
          { id: 'OPS-77', skill: 'enablement', estimate_hours: 24, priority: 'HIGH' },
          { id: 'QA-264', skill: 'quality', estimate_hours: 32, priority: 'HIGH' },
          { id: 'REL-105', skill: 'release', estimate_hours: 18, priority: 'NORMAL' },
          { id: 'OBS-93', skill: 'observability', estimate_hours: 22, priority: 'NORMAL' },
          { id: 'DATA-72', skill: 'analytics', estimate_hours: 26, priority: 'NORMAL' },
          { id: 'UAT-58', skill: 'customer-success', estimate_hours: 20, priority: 'NORMAL' },
        ],
        team_members: [
          { name: 'Olivia Grant', role: 'Program Tech Lead', skills: ['backend', 'release'], load_pct: 76, availability_pct: 75 },
          { name: 'Darius King', role: 'Device Integration Engineer', skills: ['device', 'integration'], load_pct: 82, availability_pct: 70 },
          { name: 'Priya Mehta', role: 'ERP Engineer', skills: ['integration', 'backend'], load_pct: 70, availability_pct: 85 },
          { name: 'Leo Novak', role: 'QA Automation Engineer', skills: ['quality', 'observability'], load_pct: 64, availability_pct: 90 },
          { name: 'Hannah Cho', role: 'Data Engineer', skills: ['analytics', 'backend'], load_pct: 66, availability_pct: 85 },
          { name: 'Marcus Hill', role: 'Release Manager', skills: ['release', 'enablement'], load_pct: 61, availability_pct: 80 },
          { name: 'Amina Yusuf', role: 'Training Lead', skills: ['enablement', 'customer-success'], load_pct: 78, availability_pct: 65 },
          { name: 'Vikram Sen', role: 'SRE', skills: ['observability', 'release'], load_pct: 58, availability_pct: 90 },
        ],
        sprint_weeks: 4,
        remaining_engineering_hours: 820,
        available_engineering_hours: 650,
        avg_task_hours: 26,
        hourly_rate: 168,
      },
      'agent-delivery-forecast': {
        milestone_name: 'OmniMart Argus warehouse wave-2 rollout',
        committed_revenue_usd: 1750000,
        target_date: '2026-07-29',
        current_date: '2026-06-09',
        backlog_count: 71,
        avg_velocity: 22,
        sprint_length_days: 14,
        blockers: [
          'Scanner firmware certification is not complete',
          'Warehouse UAT schedule conflicts with inventory freeze',
          'ERP feed approval is waiting on regional operations',
        ],
        capacity_changes: 'Site pilot travel reduces engineering capacity for the next two weeks.',
      },
      'agent-project-planning': {
        instruction:
          'Build an Argus warehouse rollout plan with epics for scanner firmware, ERP inventory feed, reconciliation, regional UAT, training, observability, owners, and executive decision points.',
        team_members: [
          { name: 'Olivia Grant', role: 'Program Tech Lead', skills: ['backend', 'release'], availability_pct: 75 },
          { name: 'Darius King', role: 'Device Integration Engineer', skills: ['device', 'integration'], availability_pct: 70 },
          { name: 'Priya Mehta', role: 'ERP Engineer', skills: ['integration', 'backend'], availability_pct: 85 },
          { name: 'Leo Novak', role: 'QA Automation Engineer', skills: ['quality', 'observability'], availability_pct: 90 },
          { name: 'Hannah Cho', role: 'Data Engineer', skills: ['analytics', 'backend'], availability_pct: 85 },
          { name: 'Marcus Hill', role: 'Release Manager', skills: ['release', 'enablement'], availability_pct: 80 },
          { name: 'Amina Yusuf', role: 'Training Lead', skills: ['enablement', 'customer-success'], availability_pct: 65 },
          { name: 'Vikram Sen', role: 'SRE', skills: ['observability', 'release'], availability_pct: 90 },
        ],
        timeline_weeks: 7,
        committed_revenue_usd: 1750000,
      },
    },
  },
]

const revenueScenarios: DemoScenario[] = [
  {
    id: 'acme-q2-save-motion',
    domain: 'revenue',
    title: 'Q2 revenue save motion',
    summary:
      'Acme renewal risk, early churn behavior, and late-quarter pipeline are consolidated for the CRO forecast call.',
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
    summary:
      'Stable healthcare renewal can be protected while logistics churn risk needs an executive save play.',
    payloads: {
      'agent-renewal-risk': {
        account_name: 'Meridian Healthcare',
        account_arr: 840000,
        renewal_arr_usd: 840000,
        expansion_arr_usd: 180000,
        segment: 'Enterprise Healthcare',
        contract_end_date: '2026-09-30',
        days_to_renewal: 113,
        login_frequency_30d: 42,
        feature_adoption_score: 7.8,
        support_tickets_90d: 3,
        nps_score: 72,
        last_csm_touchpoint: '2026-05-15',
        upsell_conversations: 1,
        historical_save_rate: 0.38,
        account_owner: 'Sarah Chen',
        csm_owner: 'Luis Ortega',
        exec_sponsor: 'Priya Shah',
      },
      'agent-churn-signal': {
        account_name: 'Fortis Logistics',
        account_arr: 360000,
        contract_end_date: '2026-08-15',
        days_to_renewal: 71,
        login_trend: 'declining 62% over 60 days',
        adoption_trend: 'dispatch automation stalled; no new features activated in 45 days',
        ticket_sentiment: 'negative',
        exec_engagement: 'economic buyer has not attended the last two check-ins',
        competitor_mentions: 2,
        contract_downloads: 1,
        early_intervention_value: 0.5,
        account_owner: 'Sarah Chen',
        csm_owner: 'Luis Ortega',
        exec_sponsor: 'Priya Shah',
      },
      'agent-pipeline-forecast': {
        rep_name: 'Sarah Chen',
        quota_target: 1250000,
        closed_to_date_usd: 390000,
        commit_pipeline_usd: 640000,
        best_case_pipeline_usd: 920000,
        quarter_close_date: '2026-06-30',
        days_remaining: 21,
        historical_close_rate: 0.54,
        avg_sales_cycle_days: 45,
        pipeline_deals: [
          {
            account: 'Meridian Healthcare',
            arr: 640000,
            crm_probability: 0.82,
            stage: 'Negotiation',
            close_plan: 'legal addendum with customer counsel',
            risk: 'data processing addendum open',
            next_step: 'legal team to complete DPA edits',
          },
          {
            account: 'Fortis Logistics',
            arr: 310000,
            crm_probability: 0.42,
            stage: 'Proposal sent',
            close_plan: 'revised pricing proposal requested',
            risk: 'buyer is comparing logistics workflow competitor',
            next_step: 'CSM and AE to run adoption recovery workshop',
          },
          {
            account: 'UrbanCare Clinics',
            arr: 280000,
            crm_probability: 0.48,
            stage: 'Business case',
            close_plan: 'clinical ROI case due next week',
            risk: 'CFO has not approved implementation budget',
            next_step: 'RevOps to provide benchmark ROI model',
          },
        ],
      },
    },
  },
  {
    id: 'enterprise-west-pipeline',
    domain: 'revenue',
    title: 'Enterprise West pipeline recovery',
    summary:
      'Large expansion and renewal motions need account-level focus before quarter close.',
    payloads: {
      'agent-renewal-risk': {
        account_name: 'Apex Industrial',
        account_arr: 1250000,
        renewal_arr_usd: 1250000,
        expansion_arr_usd: 520000,
        segment: 'Enterprise Manufacturing',
        contract_end_date: '2026-10-15',
        days_to_renewal: 128,
        login_frequency_30d: 21,
        feature_adoption_score: 5.1,
        support_tickets_90d: 9,
        nps_score: 28,
        last_csm_touchpoint: '2026-04-29',
        upsell_conversations: 0,
        historical_save_rate: 0.44,
        account_owner: 'Maya Singh',
        csm_owner: 'Anika Rao',
        exec_sponsor: 'Daniel Kim',
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
        account_owner: 'Maya Singh',
        csm_owner: 'Anika Rao',
        exec_sponsor: 'Daniel Kim',
      },
      'agent-pipeline-forecast': {
        rep_name: 'Maya Singh',
        quota_target: 2200000,
        closed_to_date_usd: 510000,
        commit_pipeline_usd: 720000,
        best_case_pipeline_usd: 1360000,
        quarter_close_date: '2026-06-30',
        days_remaining: 21,
        historical_close_rate: 0.28,
        avg_sales_cycle_days: 58,
        pipeline_deals: [
          {
            account: 'Apex Industrial',
            arr: 720000,
            crm_probability: 0.52,
            stage: 'Legal review',
            close_plan: 'master services agreement in redlines',
            risk: 'indemnity clause blocked by legal',
            next_step: 'CRO to approve fallback liability position',
          },
          {
            account: 'Beacon Health',
            arr: 640000,
            crm_probability: 0.39,
            stage: 'Security review',
            close_plan: 'security evidence package requested',
            risk: 'customer CISO asked for pen-test evidence',
            next_step: 'Security team to join executive sponsor call',
          },
          {
            account: 'Lumina Retail',
            arr: 380000,
            crm_probability: 0.31,
            stage: 'Business case',
            close_plan: 'store operations ROI review',
            risk: 'rollout budget shifted to next quarter',
            next_step: 'AE to narrow scope to top 40 stores',
          },
          {
            account: 'Cascadia Foods',
            arr: 260000,
            crm_probability: 0.24,
            stage: 'Technical validation',
            close_plan: 'integration architecture review not scheduled',
            risk: 'customer technical sponsor changed roles',
            next_step: 'SE manager to secure new technical sponsor',
          },
        ],
      },
    },
  },
  {
    id: 'public-sector-renewal',
    domain: 'revenue',
    title: 'Public sector renewal and expansion',
    summary:
      'A state agency renewal is stable, but expansion depends on procurement timing and executive sponsor coverage.',
    payloads: {
      'agent-renewal-risk': {
        account_name: 'StateWorks Digital',
        account_arr: 720000,
        renewal_arr_usd: 720000,
        expansion_arr_usd: 310000,
        segment: 'Public Sector',
        contract_end_date: '2026-09-20',
        days_to_renewal: 103,
        login_frequency_30d: 55,
        feature_adoption_score: 8.1,
        support_tickets_90d: 4,
        nps_score: 64,
        last_csm_touchpoint: '2026-05-22',
        upsell_conversations: 2,
        historical_save_rate: 0.52,
        account_owner: 'Elliot Park',
        csm_owner: 'Mina Joseph',
        exec_sponsor: 'Priya Shah',
      },
      'agent-churn-signal': {
        account_name: 'Metro Transit Authority',
        account_arr: 480000,
        contract_end_date: '2026-08-28',
        days_to_renewal: 80,
        login_trend: 'dispatcher usage down 33% over 45 days',
        adoption_trend: 'mobile incident workflow stalled after pilot',
        ticket_sentiment: 'mixed',
        exec_engagement: 'operations sponsor changed roles and replacement is not onboarded',
        competitor_mentions: 1,
        contract_downloads: 2,
        early_intervention_value: 0.42,
        account_owner: 'Elliot Park',
        csm_owner: 'Mina Joseph',
        exec_sponsor: 'Priya Shah',
      },
      'agent-pipeline-forecast': {
        rep_name: 'Elliot Park',
        quota_target: 1600000,
        closed_to_date_usd: 540000,
        commit_pipeline_usd: 520000,
        best_case_pipeline_usd: 980000,
        quarter_close_date: '2026-06-30',
        days_remaining: 21,
        historical_close_rate: 0.46,
        avg_sales_cycle_days: 61,
        pipeline_deals: [
          {
            account: 'StateWorks Digital',
            arr: 510000,
            crm_probability: 0.74,
            stage: 'Procurement',
            close_plan: 'final purchase order routed to agency finance',
            risk: 'procurement committee meets only twice before quarter close',
            next_step: 'VP Public Sector to confirm committee agenda',
          },
          {
            account: 'Metro Transit Authority',
            arr: 380000,
            crm_probability: 0.36,
            stage: 'Pilot review',
            close_plan: 'incident workflow pilot scorecard under review',
            risk: 'new operations sponsor has not accepted success criteria',
            next_step: 'CSM to run sponsor onboarding with pilot results',
          },
          {
            account: 'Civic Water District',
            arr: 260000,
            crm_probability: 0.43,
            stage: 'Security review',
            close_plan: 'security packet returned with open encryption question',
            risk: 'security review may slip to July',
            next_step: 'Security lead to answer encryption exception by Thursday',
          },
          {
            account: 'County Health Network',
            arr: 220000,
            crm_probability: 0.31,
            stage: 'Business case',
            close_plan: 'grant-funded business case awaiting CFO sign-off',
            risk: 'grant approval is outside seller control',
            next_step: 'RevOps to split grant-dependent scope from base purchase',
          },
        ],
      },
    },
  },
  {
    id: 'growth-accounts-risk',
    domain: 'revenue',
    title: 'Growth accounts churn and commit risk',
    summary:
      'High-growth accounts carry strong expansion upside, but support friction and sponsor gaps threaten forecast commit.',
    payloads: {
      'agent-renewal-risk': {
        account_name: 'NovaPay',
        account_arr: 680000,
        renewal_arr_usd: 680000,
        expansion_arr_usd: 420000,
        segment: 'Growth Fintech',
        contract_end_date: '2026-09-10',
        days_to_renewal: 93,
        login_frequency_30d: 29,
        feature_adoption_score: 6.2,
        support_tickets_90d: 11,
        nps_score: 18,
        last_csm_touchpoint: '2026-05-02',
        upsell_conversations: 1,
        historical_save_rate: 0.36,
        account_owner: 'Lena Ortiz',
        csm_owner: 'Marco Bell',
        exec_sponsor: 'Daniel Kim',
      },
      'agent-churn-signal': {
        account_name: 'QuickCart',
        account_arr: 520000,
        contract_end_date: '2026-08-20',
        days_to_renewal: 72,
        login_trend: 'admin and API usage down 47% over 30 days',
        adoption_trend: 'checkout automation disabled in two regions',
        ticket_sentiment: 'negative',
        exec_engagement: 'new VP Operations has not attended onboarding or QBR',
        competitor_mentions: 5,
        contract_downloads: 4,
        early_intervention_value: 0.55,
        account_owner: 'Lena Ortiz',
        csm_owner: 'Marco Bell',
        exec_sponsor: 'Daniel Kim',
      },
      'agent-pipeline-forecast': {
        rep_name: 'Lena Ortiz',
        quota_target: 1900000,
        closed_to_date_usd: 460000,
        commit_pipeline_usd: 610000,
        best_case_pipeline_usd: 1420000,
        quarter_close_date: '2026-06-30',
        days_remaining: 21,
        historical_close_rate: 0.34,
        avg_sales_cycle_days: 49,
        pipeline_deals: [
          {
            account: 'NovaPay',
            arr: 620000,
            crm_probability: 0.57,
            stage: 'Legal review',
            close_plan: 'data residency clause under legal redlines',
            risk: 'buyer requested termination rights expansion',
            next_step: 'CRO to approve fallback data residency language',
          },
          {
            account: 'QuickCart',
            arr: 430000,
            crm_probability: 0.33,
            stage: 'Commercial negotiation',
            close_plan: 'discount request awaiting VP approval',
            risk: 'support escalations are blocking expansion signature',
            next_step: 'Support leader and CSM to close top two escalations',
          },
          {
            account: 'BrightFleet',
            arr: 370000,
            crm_probability: 0.48,
            stage: 'Security review',
            close_plan: 'CISO review scheduled but pen-test evidence pending',
            risk: 'security evidence may miss quarter close',
            next_step: 'Security team to pre-brief CISO before review',
          },
          {
            account: 'MarketLane',
            arr: 310000,
            crm_probability: 0.29,
            stage: 'Business case',
            close_plan: 'regional rollout ROI not approved by CFO',
            risk: 'budget owner is prioritizing retention programs',
            next_step: 'AE to narrow proposal to retention-critical workflows',
          },
        ],
      },
    },
  },
]

const scopeCopy: Record<
  RunScope,
  {
    label: string
    runTitle: string
    runCopy: string
    demoCopy: string
  }
> = {
  platform: {
    label: 'Complete Platform',
    runTitle: 'Run complete platform',
    runCopy: 'Runs all 7 business agents and produces the cross-domain outcome story.',
    demoCopy:
      'Starts with a complete platform run, then walks through value protected, domain breakdown, run evidence, quality score, and trace replay.',
  },
  project: {
    label: 'Project Management',
    runTitle: 'Run Project Management',
    runCopy:
      'Runs the 4 delivery and planning agents for delivery risk, capacity, forecast, and plan output.',
    demoCopy:
      'Starts with delivery risk, capacity reallocation, milestone confidence, plan output, and workflow trace.',
  },
  revenue: {
    label: 'Revenue Management',
    runTitle: 'Run Revenue Management',
    runCopy: 'Runs the 3 revenue agents for renewal risk, churn signal, and pipeline forecast.',
    demoCopy:
      'Starts with protected ARR, churn intervention, pipeline gap recovery, account actions, and run evidence.',
  },
}

type StoryDomainKey = 'project' | 'revenue'

type DomainStorySummary = {
  key: StoryDomainKey
  label: string
  agentCount: number
  impact: number
  cost: number
  runCount: number
  completeRuns: number
  failedRuns: number
  outcomeCount: number
  confidence: string
  primaryMetric: string
  metrics: Array<[string, string]>
}

type BusinessStorySummary = {
  title: string
  story: string
  impact: number
  cost: number
  quality: string
  qualityDetail: string
  agentCount: number
  runCount: number
  completeRuns: number
  failedRuns: number
  outcomeCount: number
  savedTitle: string
  savedCopy: string
  nextTitle: string
  nextCopy: string
  costDetail: string
  domains: DomainStorySummary[]
}

const storyDomainConfig: Record<
  StoryDomainKey,
  { label: string; domain: 'PROJECT_DELIVERY' | 'REVENUE_OPS'; agentIds: AgentKey[] }
> = {
  project: {
    label: 'Project Management',
    domain: 'PROJECT_DELIVERY',
    agentIds: projectAgents,
  },
  revenue: {
    label: 'Revenue Management',
    domain: 'REVENUE_OPS',
    agentIds: revenueAgents,
  },
}

const metricLabels: Record<string, string> = {
  delivery_risk_mitigated_usd: 'Delivery risk mitigated',
  engineering_hours_saved_usd: 'Engineering efficiency saved',
  pipeline_confidence_gap_usd: 'Delivery confidence gap',
  renewal_pipeline_protected_usd: 'Renewal pipeline protected',
  churn_early_flag_value_usd: 'Churn intervention value',
  recoverable_quota_gap_usd: 'Recoverable quota gap',
}

const outcomeMetricMetadata: Record<
  string,
  { owner: string; action: string; narrative: string }
> = {
  delivery_risk_mitigated_usd: {
    owner: 'Delivery executive',
    action: 'Approve mitigation plan and fund blocked dependency removal.',
    narrative: 'Delivery exposure that can be reduced by acting on sprint risk and mitigation signals.',
  },
  engineering_hours_saved_usd: {
    owner: 'PMO lead',
    action: 'Approve resource reallocation and protect delivery capacity.',
    narrative: 'Engineering efficiency opportunity from better assignment and capacity matching.',
  },
  pipeline_confidence_gap_usd: {
    owner: 'Program sponsor',
    action: 'Review recovery plan and decide whether to escalate launch risk.',
    narrative: 'Committed revenue at risk because delivery confidence is below target.',
  },
  renewal_pipeline_protected_usd: {
    owner: 'Revenue leadership',
    action: 'Launch renewal save motion with CSM and account executive owners.',
    narrative: 'Renewal ARR that can be protected through proactive save actions.',
  },
  churn_early_flag_value_usd: {
    owner: 'Customer success director',
    action: 'Start executive outreach and adoption recovery plan.',
    narrative: 'Value at risk from early churn signals and declining engagement.',
  },
  recoverable_quota_gap_usd: {
    owner: 'Sales VP',
    action: 'Prioritize the recoverable deals and inspect negative gaps before forecast commit.',
    narrative: 'Pipeline gap that can be recovered or must be de-risked in forecast review.',
  },
}

function metricLabel(metricName: string) {
  return metricLabels[metricName] ?? metricName.replace(/_/g, ' ')
}

function outcomeMetadata(metricName: string) {
  return outcomeMetricMetadata[metricName] ?? {
    owner: 'Business owner',
    action: 'Review evidence and assign an owner before approving value.',
    narrative: 'Business outcome produced by completed agent output.',
  }
}

function storyDomainsFor(scope: RunScope): StoryDomainKey[] {
  if (scope === 'project') return ['project']
  if (scope === 'revenue') return ['revenue']
  return ['project', 'revenue']
}

function agentConfigForRun(run: AgentRun) {
  return (agentCatalog as Record<string, AgentConfig | undefined>)[run.agent_id]
}

function runBelongsToStoryDomain(run: AgentRun, domainKey: StoryDomainKey) {
  const agent = agentConfigForRun(run)
  return agent?.domain === storyDomainConfig[domainKey].domain
}

function outcomeBelongsToStoryDomain(outcome: BusinessOutcome, domainKey: StoryDomainKey) {
  return outcome.domain === storyDomainConfig[domainKey].domain
}

function summarizeStoryDomain(
  domainKey: StoryDomainKey,
  outcomes: BusinessOutcome[],
  runs: AgentRun[],
): DomainStorySummary {
  const config = storyDomainConfig[domainKey]
  const domainOutcomes = outcomes.filter((outcome) =>
    outcomeBelongsToStoryDomain(outcome, domainKey),
  )
  const domainRuns = billableRuns(runs).filter((run) =>
    runBelongsToStoryDomain(run, domainKey),
  )
  const impact = domainOutcomes.reduce(
    (sum, outcome) => sum + outcome.financial_impact_usd,
    0,
  )
  const cost = domainRuns.reduce((sum, run) => sum + run.cost_usd, 0)
  const confidenceScores = domainOutcomes.map((outcome) => outcome.confidence_score)
  const averageConfidence = confidenceScores.length
    ? confidenceScores.reduce((sum, score) => sum + score, 0) / confidenceScores.length
    : null
  const metrics = [...domainOutcomes]
    .sort((left, right) => right.financial_impact_usd - left.financial_impact_usd)
    .slice(0, 3)
    .map((outcome): [string, string] => [
      metricLabel(outcome.metric_name),
      money(outcome.financial_impact_usd),
    ])

  return {
    key: domainKey,
    label: config.label,
    agentCount: config.agentIds.length,
    impact,
    cost,
    runCount: domainRuns.length,
    completeRuns: domainRuns.filter((run) => run.status === 'COMPLETE').length,
    failedRuns: domainRuns.filter((run) => run.status === 'FAILED').length,
    outcomeCount: domainOutcomes.length,
    confidence: averageConfidence === null ? 'pending' : averageConfidence.toFixed(2),
    primaryMetric: metrics[0]?.[0] ?? 'No live financial outcome yet',
    metrics,
  }
}

function decisionReadiness(score: number | null): { value: string; detail: string } {
  if (score === null) {
    return { value: 'Pending', detail: 'awaiting completed outcome evidence' }
  }
  const percent = `${Math.round(score * 100)}%`
  if (score >= 0.8) return { value: 'Ready', detail: `${percent} evidence confidence` }
  if (score >= 0.65) return { value: 'Review', detail: `${percent} evidence confidence` }
  if (score >= 0.5) return { value: 'Needs review', detail: `${percent} evidence confidence` }
  return { value: 'At risk', detail: `${percent} evidence confidence` }
}

function hasJudgeInfrastructureFailure(run: AgentRun) {
  const trace = run.quality_dimensions?.reasoning_trace
  return typeof trace === 'string' && trace.toLowerCase().includes('judge failed')
}

function buildBusinessStorySummary(
  scope: RunScope,
  outcomes: BusinessOutcome[],
  runs: AgentRun[],
): BusinessStorySummary {
  const domainKeys = storyDomainsFor(scope)
  const domains = domainKeys.map((domain) =>
    summarizeStoryDomain(domain, outcomes, runs),
  )
  const scopedRuns = billableRuns(runs).filter((run) =>
    domainKeys.some((domain) => runBelongsToStoryDomain(run, domain)),
  )
  const outcomeRunIds = new Set(
    outcomes
      .filter((outcome) => domainKeys.some((domain) => outcomeBelongsToStoryDomain(outcome, domain)))
      .map((outcome) => outcome.agent_run_id),
  )
  const qualityScores = scopedRuns
    .filter(
      (run) =>
        run.status === 'COMPLETE' &&
        outcomeRunIds.has(run.id) &&
        !hasJudgeInfrastructureFailure(run),
    )
    .map((run) => run.quality_score)
    .filter((score): score is number => typeof score === 'number')
  const impact = domains.reduce((sum, domain) => sum + domain.impact, 0)
  const cost = domains.reduce((sum, domain) => sum + domain.cost, 0)
  const averageQuality = qualityScores.length
    ? qualityScores.reduce((sum, score) => sum + score, 0) / qualityScores.length
    : null
  const qualitySignal = decisionReadiness(averageQuality)
  const agentCount = domains.reduce((sum, domain) => sum + domain.agentCount, 0)
  const runCount = domains.reduce((sum, domain) => sum + domain.runCount, 0)
  const completeRuns = domains.reduce((sum, domain) => sum + domain.completeRuns, 0)
  const failedRuns = domains.reduce((sum, domain) => sum + domain.failedRuns, 0)
  const outcomeCount = domains.reduce((sum, domain) => sum + domain.outcomeCount, 0)
  const scopeLabel = scopeCopy[scope].label
  const domainDetail = domains
    .map((domain) => `${domain.label}: ${money(domain.impact)} value, ${costMoney(domain.cost)} cost`)
    .join('; ')
  const hasOutcomes = outcomeCount > 0
  const hasRuns = runCount > 0

  if (!hasRuns) {
    return {
      title: `${scopeLabel} is ready for a live run`,
      story: `No ${scopeLabel} run has completed in this session yet. Start the selected scope to generate live Project Management and Revenue Management outcomes, evidence, and cost.`,
      impact,
      cost,
      quality: qualitySignal.value,
      qualityDetail: qualitySignal.detail,
      agentCount,
      runCount,
      completeRuns,
      failedRuns,
      outcomeCount,
      savedTitle: '$0 protected yet',
      savedCopy: 'The value will come from completed agent outputs written to the outcome ledger.',
      nextTitle: `Run ${scopeLabel}`,
      nextCopy: 'Start the run, watch progress move to the foreground, then review domain outcomes and cost.',
      costDetail: 'No scoped run cost yet',
      domains,
    }
  }

  if (!hasOutcomes) {
    return {
      title: `${scopeLabel} captured run evidence; financial outcomes are pending`,
      story: `${scopeLabel} has ${runCount} billable run${runCount === 1 ? '' : 's'} captured at ${costMoney(cost)} total cost. No financial outcome rows were produced yet, so inspect trace and failed runs before approving a business result.`,
      impact,
      cost,
      quality: qualitySignal.value,
      qualityDetail: qualitySignal.detail,
      agentCount,
      runCount,
      completeRuns,
      failedRuns,
      outcomeCount,
      savedTitle: '$0 protected yet',
      savedCopy: 'Run evidence exists, but no completed business outcome has been written for this scope.',
      nextTitle: failedRuns > 0 ? 'Inspect failed runs' : 'Review trace evidence',
      nextCopy:
        failedRuns > 0
          ? 'Open Evidence, inspect failed agent output, then retry the selected scope.'
          : 'Open Evidence to confirm the run output and why no financial outcome was recorded.',
      costDetail: `${runCount} billable run${runCount === 1 ? '' : 's'} - ${costMoney(cost)} total cost`,
      domains,
    }
  }

  return {
    title: `${scopeLabel} protected ${money(impact)} across ${outcomeCount} live outcome${outcomeCount === 1 ? '' : 's'}`,
    story: `${scopeLabel} converted completed agent outputs into live outcome-ledger value. ${domainDetail}. Total run cost for this scope is ${costMoney(cost)}, including token, API-call, and compute charges.`,
    impact,
    cost,
    quality: qualitySignal.value,
    qualityDetail: qualitySignal.detail,
    agentCount,
    runCount,
    completeRuns,
    failedRuns,
    outcomeCount,
    savedTitle: `${money(impact)} protected`,
    savedCopy: `${outcomeCount} outcome${outcomeCount === 1 ? '' : 's'} linked to ${runCount} billable run${runCount === 1 ? '' : 's'} with ${costMoney(cost)} total run cost.`,
    nextTitle: failedRuns > 0 ? 'Approve value and inspect failures' : 'Approve domain action plan',
    nextCopy:
      failedRuns > 0
        ? 'Use the outcome ledger for completed value, then inspect failed runs before closing the session.'
        : 'Review the outcome ledger, validate trace evidence, and approve the next owner action.',
    costDetail: `${runCount} billable run${runCount === 1 ? '' : 's'} - ${costMoney(cost)} total cost`,
    domains,
  }
}

const views: Array<{ id: ViewId; label: string; group: string; icon: LucideIcon; index: string }> = [
  { id: 'story', label: 'Story View', group: 'Business', icon: DollarSign, index: '01' },
  { id: 'outcomes', label: 'Outcome Ledger', group: 'Business', icon: BarChart3, index: '02' },
  { id: 'data', label: 'Demo Data', group: 'Business', icon: Database, index: '03' },
  { id: 'run', label: 'Run Console', group: 'Run', icon: Play, index: '04' },
  { id: 'evidence', label: 'Evidence', group: 'Technical', icon: Activity, index: '05' },
  { id: 'architecture', label: 'Architecture', group: 'Technical', icon: Layers3, index: '06' },
  { id: 'settings', label: 'Settings', group: 'Control', icon: Settings, index: '07' },
]

const viewCopy: Record<ViewId, { title: string; subtitle: string }> = {
  story: {
    title: 'Story View',
    subtitle: 'Outcome-first story of what was solved, what value was protected, and what action is next.',
  },
  outcomes: {
    title: 'Outcome Ledger',
    subtitle: 'Financial value by business domain, source agent, confidence, and action owner.',
  },
  data: {
    title: 'Demo Data',
    subtitle: 'Business scenario assumptions and technical payloads used by this demo.',
  },
  run: {
    title: 'Run Console',
    subtitle: 'Scope-first execution surface for platform, domain, and single-agent runs.',
  },
  evidence: {
    title: 'Evidence',
    subtitle: 'Trace, cost, tokens, model, status, quality, and replay context.',
  },
  architecture: {
    title: 'Architecture',
    subtitle: 'Interactive system map from UI request to governed run evidence.',
  },
  settings: {
    title: 'Settings',
    subtitle: 'Provider, model, token pricing, and run defaults for the next demo execution.',
  },
}

function money(value: number) {
  const formatted = Math.round(Math.abs(value)).toLocaleString()
  return value < 0 ? `-$${formatted}` : `$${formatted}`
}

function costMoney(value: number) {
  if (value === 0) return '$0.0000'
  if (Math.abs(value) < 0.0001) return `$${value.toFixed(7)}`
  if (Math.abs(value) < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

function unitCostMoney(value: number) {
  if (Math.abs(value) < 0.0001) return `$${value.toFixed(7)}`
  return `$${value.toFixed(value < 0.01 ? 4 : 2)}`
}

function providerLabel(provider: string) {
  return providerCatalog[provider as ProviderKey]?.label ?? provider
}

function providerModels(pricing: ModelPricing[], provider: ProviderKey) {
  const pricedModels = pricing
    .filter((item) => item.provider === provider && item.effective_to === null)
    .map((item) => item.model_name)
  return pricedModels.length > 0 ? pricedModels : fallbackModelsByProvider[provider]
}

function pricingForProviderModel(
  pricing: ModelPricing[],
  provider: ProviderKey,
  modelName: string,
) {
  return pricing.find(
    (item) =>
      item.provider === provider &&
      item.model_name === modelName &&
      item.effective_to === null,
  )
}

function providerNextAction(provider: ProviderKey) {
  return providerCatalog[provider].nextAction
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

const workflowNodeOrder: Record<string, number> = {
  node_decompose: 1,
  node_capacity_check: 2,
  node_risk_assess: 3,
  node_assign: 4,
  node_synthesize: 5,
}

const evidenceDomainOrder: EvidenceDomain[] = ['PROJECT_DELIVERY', 'REVENUE_OPS', 'PLATFORM']

const evidenceDomainLabels: Record<EvidenceDomain, string> = {
  PROJECT_DELIVERY: 'Project Management',
  REVENUE_OPS: 'Revenue Management',
  PLATFORM: 'Platform',
}

function evidenceGroups(runs: AgentRun[]): EvidenceGroup[] {
  const newestFirst = [...runs].reverse()
  const nodesByParent = new Map<string, AgentRun[]>()
  for (const run of runs) {
    if (run.run_type === 'WORKFLOW_NODE' && run.parent_run_id) {
      const nodes = nodesByParent.get(run.parent_run_id) ?? []
      nodes.push(run)
      nodesByParent.set(run.parent_run_id, nodes)
    }
  }

  const groups: EvidenceRunGroup[] = []
  for (const run of newestFirst) {
    if (run.run_type === 'WORKFLOW_NODE') continue
    if (run.run_type === 'WORKFLOW_PARENT') {
      const nodes = [...(nodesByParent.get(run.id) ?? [])].sort(
        (left, right) =>
          (workflowNodeOrder[left.agent_id] ?? 99) - (workflowNodeOrder[right.agent_id] ?? 99),
      )
      groups.push({ kind: 'workflow', parent: run, nodes })
    } else {
      groups.push({ kind: 'run', run })
    }
  }

  const groupsByDomain = new Map<EvidenceDomain, EvidenceRunGroup[]>()
  for (const group of groups) {
    const domain = evidenceRunGroupDomain(group)
    const domainGroups = groupsByDomain.get(domain) ?? []
    domainGroups.push(group)
    groupsByDomain.set(domain, domainGroups)
  }

  return evidenceDomainOrder
    .map((domain) => ({
      kind: 'domain' as const,
      domain,
      label: evidenceDomainLabels[domain],
      items: groupsByDomain.get(domain) ?? [],
    }))
    .filter((group) => group.items.length > 0)
}

function evidenceRunGroupDomain(group: EvidenceRunGroup): EvidenceDomain {
  const run = group.kind === 'workflow' ? group.parent : group.run
  const agent = agentCatalog[run.agent_id as AgentKey]
  if (agent?.domain === 'PROJECT_DELIVERY') return 'PROJECT_DELIVERY'
  if (agent?.domain === 'REVENUE_OPS') return 'REVENUE_OPS'
  return 'PLATFORM'
}

function evidenceRunGroupStatus(group: EvidenceRunGroup) {
  return group.kind === 'workflow' ? group.parent.status : group.run.status
}

function evidenceRunGroupKey(group: EvidenceRunGroup) {
  return group.kind === 'workflow' ? group.parent.id : group.run.id
}

function billableRuns(runs: AgentRun[]) {
  return runs.filter((run) => run.run_type === 'SINGLE_SHOT' || run.run_type === 'WORKFLOW_PARENT')
}

function computeCostPerSecond(pricing: ModelPricing) {
  return (
    COMPUTE_VCPU_PER_AGENT_RUN * pricing.compute_vcpu_cost_per_second +
    COMPUTE_MEMORY_GIB_PER_AGENT_RUN * pricing.compute_memory_gib_cost_per_second
  )
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
  const [view, setView] = useState<ViewId>('story')
  const [persona, setPersona] = useState<Persona>('business')
  const [scope, setScope] = useState<RunScope>('platform')
  const [selectedAgent, setSelectedAgent] = useState<AgentKey>('agent-sprint-risk')
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [outcomes, setOutcomes] = useState<BusinessOutcome[]>([])
  const [pricing, setPricing] = useState<ModelPricing[]>([])
  const [statusMessage, setStatusMessage] = useState('Ready to run the locked demo flow.')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeRun, setActiveRun] = useState<ActiveRun | null>(null)
  const [payloadPreviewOpen, setPayloadPreviewOpen] = useState(false)
  const [settingsProvider, setSettingsProvider] = useState<ProviderKey>('ollama')
  const [settingsModel, setSettingsModel] = useState('llama3.2:3b')
  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSettings | null>(null)
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
  const sessionImpact = useMemo(
    () => outcomes.reduce((sum, outcome) => sum + outcome.financial_impact_usd, 0),
    [outcomes],
  )
  const settingsModels = useMemo(
    () => providerModels(pricing, settingsProvider),
    [pricing, settingsProvider],
  )
  const settingsModelPricing = useMemo(
    () => pricingForProviderModel(pricing, settingsProvider, settingsModel),
    [pricing, settingsModel, settingsProvider],
  )
  const settingsRuntimeProvider = useMemo(
    () =>
      runtimeSettings?.providers.find(
        (item) => item.provider === settingsProvider,
      ),
    [runtimeSettings, settingsProvider],
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
    void api.settings.runtime()
      .then((runtime) => {
        setRuntimeSettings(runtime)
        setSettingsProvider(runtime.active_provider)
        setSettingsModel(runtime.active_model)
      })
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!settingsModels.includes(settingsModel)) {
      setSettingsModel(settingsModels[0] ?? '')
    }
  }, [settingsModel, settingsModels])

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

  function payloadPreviewGroupsFor(
    agentIds: AgentKey[],
    payloads?: Partial<Record<AgentKey, Record<string, unknown>>>,
    scenarioTitles?: Partial<Record<AgentConfig['domain'], string>>,
  ): PayloadPreviewGroup[] {
    return [
      {
        domain: 'PROJECT_DELIVERY' as const,
        label: 'Project Management',
        scenarioTitle: scenarioTitles?.PROJECT_DELIVERY ?? currentProjectScenario.title,
      },
      {
        domain: 'REVENUE_OPS' as const,
        label: 'Revenue Management',
        scenarioTitle: scenarioTitles?.REVENUE_OPS ?? currentRevenueScenario.title,
      },
    ]
      .map((group) => ({
        ...group,
        items: agentIds
          .filter((agentId) => agentCatalog[agentId].domain === group.domain)
          .map((agentId) => ({
            agent: agentCatalog[agentId],
            payload: payloads?.[agentId] ?? payloadForAgent(agentId),
          })),
      }))
      .filter((group) => group.items.length > 0)
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
      const payloadsByAgent = Object.fromEntries(
        agentIds.map((agentId) => [agentId, payloadForAgent(agentId)]),
      ) as Partial<Record<AgentKey, Record<string, unknown>>>
      const scenarioTitles: Partial<Record<AgentConfig['domain'], string>> = {}
      if (agentIds.some((agentId) => agentCatalog[agentId].domain === 'PROJECT_DELIVERY')) {
        scenarioTitles.PROJECT_DELIVERY = currentProjectScenario.title
      }
      if (agentIds.some((agentId) => agentCatalog[agentId].domain === 'REVENUE_OPS')) {
        scenarioTitles.REVENUE_OPS = currentRevenueScenario.title
      }
      const tasks: TaskSubmit[] = agentIds.map((agentId) => ({
        agent_id: agentId,
        session_id: activeSession.id,
        input_payload: payloadsByAgent[agentId] ?? payloadForAgent(agentId),
        priority: 'HIGH',
      }))
      const submittedTasks = await api.tasks.batch({ tasks })
      setActiveRun({
        id: `${Date.now()}`,
        label: runLabel,
        agentIds,
        taskIds: submittedTasks.map((task) => task.id),
        payloads: payloadsByAgent,
        scenarioTitles,
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

  async function applyProviderSelection() {
    const pricingMessage = settingsModelPricing
      ? `${unitCostMoney(settingsModelPricing.input_cost_per_1k)}/1K input, ${unitCostMoney(settingsModelPricing.output_cost_per_1k)}/1K output, ${unitCostMoney(settingsModelPricing.api_call_cost_per_1k)}/1K API, and ${unitCostMoney(computeCostPerSecond(settingsModelPricing))}/sec compute.`
      : 'No active pricing row is available for this model yet.'
    setStatusMessage(`Applying ${providerLabel(settingsProvider)} ${settingsModel}.`)
    try {
      const runtime = await api.settings.updateRuntime({
        active_provider: settingsProvider,
        model_name: settingsModel,
      })
      setRuntimeSettings(runtime)
      setSettingsProvider(runtime.active_provider)
      setSettingsModel(runtime.active_model)
      setStatusMessage(
        `${providerLabel(runtime.active_provider)} ${runtime.active_model} applied for live runs: ${pricingMessage} Next: run ${copy.label}.`,
      )
    } catch (error) {
      setStatusMessage(
        error instanceof Error
          ? `Provider not applied: ${error.message}. Next: ${providerNextAction(settingsProvider)}`
          : `Provider not applied. Next: ${providerNextAction(settingsProvider)}`,
      )
    }
  }

  function showPayloadPreview() {
    setPayloadPreviewOpen(true)
    setView('run')
    setStatusMessage(
      `Payload preview opened for ${copy.label}. Next: review Project Management and Revenue Management inputs, then run the selected scope.`,
    )
  }

  function startGuidedDemo() {
    setView('run')
    setStatusMessage(
      `Guided demo ready for ${copy.label}. Next: run the selected scope, then open Outcome ledger and Inspect trace.`,
    )
  }

  function openTraceReplay() {
    setView('evidence')
    setStatusMessage(
      runs.length > 0
        ? 'Trace replay opened. Next: inspect failed runs first, then review quality and total run cost.'
        : 'Trace replay has no runs yet. Next: run the selected scope from Run Console.',
    )
  }

  const runProgressLabel =
    activeProgress && hasRunningWork
      ? `Running ${activeProgress.active.label} ${activeProgress.complete + activeProgress.failed}/${activeProgress.total}`
      : copy.runTitle
  const RunButtonIcon = hasRunningWork || isSubmitting ? LoaderCircle : Play
  const currentViewCopy = viewCopy[view]
  const payloadPreviewAgentIds = activeRun && hasRunningWork ? activeRun.agentIds : scopeAgentIds[scope]
  const payloadPreviewGroups = payloadPreviewGroupsFor(
    payloadPreviewAgentIds,
    activeRun && hasRunningWork ? activeRun.payloads : undefined,
    activeRun && hasRunningWork ? activeRun.scenarioTitles : undefined,
  )

  function navBadge(targetView: ViewId) {
    if (targetView === 'story') return String(outcomes.length)
    if (targetView === 'outcomes') return sessionImpact > 0 ? money(sessionImpact) : '$0'
    if (targetView === 'data') return String(visibleScenarios.length)
    if (targetView === 'run') return String(runs.length)
    if (targetView === 'evidence') return String(Math.max(recentRuns(runs).length, 8))
    if (targetView === 'architecture') return String(architectureLayers.length)
    if (targetView === 'settings') return String(providerOrder.length)
    return ''
  }

  return (
    <div className={`app-shell ${persona}-lens`}>
      <aside className="sidebar">
        <div className="brand">
          <div>
            <h1>AgentOps Control Plane</h1>
            <span>AI Work Management Platform</span>
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
          {['Business', 'Run', 'Technical', 'Control'].map((group) => (
            <div className="nav-group" key={group}>
              <span>{group}</span>
              {views
                .filter((item) => item.group === group)
                .map((item) => {
                  return (
                    <button
                      className={view === item.id ? 'active' : ''}
                      type="button"
                      key={item.id}
                      onClick={() => setView(item.id)}
                    >
                      <span>{item.index}</span>
                      <span>{item.label}</span>
                      <b>{navBadge(item.id)}</b>
                    </button>
                  )
                })}
            </div>
          ))}
        </nav>

        <div className="runtime-card">
          <strong>Runtime</strong>
          <div><span>Provider</span><b>{providerLabel(settingsProvider)}</b></div>
          <div><span>Model</span><b>{settingsModel}</b></div>
          <div><span>Session</span><b>{session?.status ?? 'Starting'}</b></div>
          <div><span>SSE</span><b>Connected</b></div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <h2>{currentViewCopy.title}</h2>
            <p>{currentViewCopy.subtitle}</p>
          </div>
          <div className="top-actions">
            <button className="btn" type="button" onClick={() => setView('outcomes')}>
              <FileText size={16} /> Outcome ledger
            </button>
            <button className="btn" type="button" onClick={() => setView('evidence')}>
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

        {view === 'story' && (
          <BusinessView
            copy={copy}
            isSubmitting={isSubmitting}
            activeProgress={activeProgress}
            currentProjectScenario={currentProjectScenario}
            onRunScope={() => void runSelectedScope()}
            onRunAgent={() => void runSelectedAgent()}
            onGuidedDemo={startGuidedDemo}
            onPayloadPreview={showPayloadPreview}
            onTraceReplay={openTraceReplay}
            onViewChange={setView}
            outcomes={outcomes}
            persona={persona}
            scope={scope}
            selectedAgent={selectedAgent}
            selectedAgentConfig={selectedAgentConfig}
            runs={runs}
            setPersona={setPersona}
            setProjectPlanningInput={setProjectPlanningInput}
            setSelectedAgent={setSelectedAgent}
            statusMessage={statusMessage}
            availableAgentConfigs={availableAgentConfigs}
            availableAgentIds={availableAgentIds}
            projectPlanningInput={projectPlanningInput}
            visibleScenarios={visibleScenarios}
          />
        )}
        {view === 'run' && (
          <RunConsoleView
            activeProgress={activeProgress}
            availableAgentConfigs={availableAgentConfigs}
            availableAgentIds={availableAgentIds}
            copy={copy}
            currentProjectScenario={currentProjectScenario}
            isSubmitting={isSubmitting}
            onGuidedDemo={startGuidedDemo}
            onPayloadPreview={showPayloadPreview}
            onPayloadPreviewClose={() => setPayloadPreviewOpen(false)}
            onRunAgent={() => void runSelectedAgent()}
            onRunScope={() => void runSelectedScope()}
            onTraceReplay={openTraceReplay}
            payloadPreviewGroups={payloadPreviewGroups}
            payloadPreviewOpen={payloadPreviewOpen}
            projectPlanningInput={projectPlanningInput}
            projectScenarioIndex={projectScenarioIndex}
            revenueScenarioIndex={revenueScenarioIndex}
            scope={scope}
            selectedAgent={selectedAgent}
            selectedAgentConfig={selectedAgentConfig}
            setProjectPlanningInput={setProjectPlanningInput}
            setProjectScenarioIndex={setProjectScenarioIndex}
            setRevenueScenarioIndex={setRevenueScenarioIndex}
            setSelectedAgent={setSelectedAgent}
            statusMessage={statusMessage}
            visibleScenarios={visibleScenarios}
          />
        )}
        {view === 'outcomes' && (
          <OutcomesView outcomes={outcomes} runs={runs} sessionImpact={sessionImpact} />
        )}
        {view === 'data' && (
          <DemoDataView groups={payloadPreviewGroups} persona={persona} scenarios={visibleScenarios} />
        )}
        {view === 'evidence' && (
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
            modelPricing={settingsModelPricing}
            models={settingsModels}
            onApplyProvider={applyProviderSelection}
            onRunAgent={() => void runSelectedAgent()}
            onRunScope={() => void runSelectedScope()}
            onViewChange={setView}
            provider={settingsProvider}
            providers={providerOrder}
            runtimeProvider={settingsRuntimeProvider}
            scope={scope}
            selectedAgent={activeSelectedAgent}
            selectedModel={settingsModel}
            setSelectedAgent={setSelectedAgent}
            setSelectedModel={setSettingsModel}
            setProvider={setSettingsProvider}
          />
        )}
      </main>
    </div>
  )
}

function BusinessView({
  activeProgress,
  copy,
  currentProjectScenario,
  isSubmitting,
  onGuidedDemo,
  onPayloadPreview,
  onRunAgent,
  onRunScope,
  onTraceReplay,
  onViewChange,
  outcomes,
  persona,
  projectPlanningInput,
  runs,
  scope,
  selectedAgent,
  selectedAgentConfig,
  setPersona,
  setProjectPlanningInput,
  setSelectedAgent,
  statusMessage,
  availableAgentConfigs,
  availableAgentIds,
  visibleScenarios,
}: {
  activeProgress: RunProgress | null
  copy: (typeof scopeCopy)[RunScope]
  currentProjectScenario: DemoScenario
  isSubmitting: boolean
  onGuidedDemo: () => void
  onPayloadPreview: () => void
  onRunAgent: () => void
  onRunScope: () => void
  onTraceReplay: () => void
  onViewChange: (view: ViewId) => void
  outcomes: BusinessOutcome[]
  persona: Persona
  projectPlanningInput: ProjectPlanningInput
  scope: RunScope
  selectedAgent: AgentKey
  selectedAgentConfig: AgentConfig
  runs: AgentRun[]
  setPersona: (persona: Persona) => void
  setProjectPlanningInput: (input: ProjectPlanningInput) => void
  setSelectedAgent: (agent: AgentKey) => void
  statusMessage: string
  availableAgentConfigs: AgentConfig[]
  availableAgentIds: AgentKey[]
  visibleScenarios: DemoScenario[]
}) {
  const runIsActive = Boolean(activeProgress && !activeProgress.terminal)
  const storySummary = buildBusinessStorySummary(scope, outcomes, runs)
  if (runIsActive && activeProgress) {
    const resolvedRuns = activeProgress.complete + activeProgress.failed
    const inFlightRuns = Math.max(0, activeProgress.total - resolvedRuns)

    return (
      <div className="page-stack story-run-focus-page">
        <section className="section story-run-focus">
          <SectionHeader
            icon={<LoaderCircle className="spin-icon" size={18} />}
            label="run in progress"
            title={`Running ${activeProgress.active.label}`}
            subtitle={`Story content is collapsed while ${activeProgress.total} agents produce live evidence and outcomes.`}
            action={
              <div className="button-row">
                <button className="btn" type="button" onClick={onPayloadPreview}>
                  <FileText size={16} /> Preview payload
                </button>
                <button className="btn" type="button" onClick={onTraceReplay}>
                  <Workflow size={16} /> Inspect trace
                </button>
                <button className="btn primary" type="button" onClick={() => onViewChange('run')}>
                  <Play size={16} /> Open run console
                </button>
              </div>
            }
          />
          <div className="story-run-focus-grid">
            <article className="run-focus-summary">
              <span className="pill">Live run foreground</span>
              <h3>{activeProgress.active.label}</h3>
              <p className={statusMessage.startsWith('Run submission failed') ? 'run-status error' : 'run-status'}>
                {statusMessage}
              </p>
              <div className="run-focus-metrics">
                <div>
                  <span>Progress</span>
                  <strong>{resolvedRuns}/{activeProgress.total}</strong>
                  <em>agents resolved</em>
                </div>
                <div>
                  <span>In flight</span>
                  <strong>{inFlightRuns}</strong>
                  <em>running or queued</em>
                </div>
                <div>
                  <span>Scope</span>
                  <strong>{copy.label}</strong>
                  <em>{scopeAgentIds[scope].length} agents</em>
                </div>
                <div>
                  <span>Next best action</span>
                  <strong>Inspect trace</strong>
                  <em>review evidence as agents finish</em>
                </div>
              </div>
              <div className="domain-agent-list" aria-label={`${copy.label} agents running`}>
                <span>{copy.label} agents</span>
                <div>
                  {availableAgentConfigs.map((agent) => (
                    <b key={agent.id}>{agent.name}</b>
                  ))}
                </div>
              </div>
            </article>
            <RunProgressPanel progress={activeProgress} />
          </div>
        </section>

        <section className="section collapsed-story-summary">
          <SectionHeader
            icon={<DollarSign size={18} />}
            label="story collapsed"
            title={storySummary.title}
            subtitle="The business story, value protected, and next action return here when the run completes."
            action={
              <button className="btn" type="button" onClick={() => onViewChange('outcomes')}>
                <FileText size={16} /> Outcome ledger
              </button>
            }
          />
        </section>
      </div>
    )
  }

  return (
    <div className="page-stack">
      <section className="kpi-grid" aria-label="Business summary">
        <Kpi label="Active scope" value={scopeCopy[scope].label} detail={`${storySummary.agentCount} agents`} />
        <Kpi
          label="Agent runs"
          value={String(storySummary.runCount)}
          detail={`${storySummary.completeRuns} complete, ${storySummary.failedRuns} failed`}
        />
        <Kpi
          label="Decision readiness"
          value={storySummary.quality}
          detail={storySummary.qualityDetail}
        />
        <Kpi
          label="Financial impact"
          value={money(storySummary.impact)}
          detail={storySummary.outcomeCount > 0 ? 'live outcome ledger' : 'no live outcomes yet'}
        />
        <Kpi
          label="Total run cost"
          value={costMoney(storySummary.cost)}
          detail={storySummary.costDetail}
        />
      </section>

      <section className="story-board">
        <div className="story-lead">
          <span className="pill">{persona === 'business' ? 'Business lens' : 'Technical lens'} - {copy.label}</span>
          <h3>{storySummary.title}</h3>
          <p>{storySummary.story}</p>
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
          <strong>{money(storySummary.impact)}</strong>
          <p>{storySummary.savedCopy}</p>
          <div className="breakdown-list">
            {storySummary.domains.map((domain) => (
              <div key={domain.key}>
                <span>{domain.label}</span>
                <b>{money(domain.impact)} / {costMoney(domain.cost)} cost</b>
              </div>
            ))}
          </div>
        </aside>
      </section>

      <section className="domain-story-grid" aria-label="Domain run details">
        {storySummary.domains.map((domain) => (
          <article className="domain-story-card" key={domain.key}>
            <div className="domain-story-head">
              <span>{domain.label}</span>
              <strong>{money(domain.impact)}</strong>
              <em>{costMoney(domain.cost)} total run cost</em>
            </div>
            <div className="domain-story-stats">
              <div><span>Agents</span><b>{domain.agentCount}</b></div>
              <div><span>Runs</span><b>{domain.completeRuns}/{domain.runCount}</b></div>
              <div><span>Outcomes</span><b>{domain.outcomeCount}</b></div>
              <div><span>Confidence</span><b>{domain.confidence}</b></div>
            </div>
            <div className="domain-story-metrics">
              <span>Top value drivers</span>
              {domain.metrics.length > 0 ? (
                domain.metrics.map(([label, value]) => (
                  <div key={label}><span>{label}</span><b>{value}</b></div>
                ))
              ) : (
                <p>{domain.primaryMetric}. Run this domain to populate live business value.</p>
              )}
            </div>
          </article>
        ))}
      </section>

      <section className="solved-grid">
        <InfoCard tone="good" label="Solved" title="Live outcomes are grouped by domain" copy={storySummary.story} />
        <InfoCard tone="good" label="Saved" title={storySummary.savedTitle} copy={storySummary.savedCopy} />
        <InfoCard tone="warn" label="Next action" title={storySummary.nextTitle} copy={storySummary.nextCopy} />
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
              <button className="run-command" type="button" onClick={onGuidedDemo}>
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
              <button className="btn" type="button" onClick={onPayloadPreview}>Preview payload</button>
              <button className="btn" type="button" onClick={onTraceReplay}>Replay last run</button>
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

function RunConsoleView({
  activeProgress,
  availableAgentConfigs,
  availableAgentIds,
  copy,
  currentProjectScenario,
  isSubmitting,
  onGuidedDemo,
  onPayloadPreview,
  onPayloadPreviewClose,
  onRunAgent,
  onRunScope,
  onTraceReplay,
  payloadPreviewGroups,
  payloadPreviewOpen,
  projectPlanningInput,
  projectScenarioIndex,
  revenueScenarioIndex,
  scope,
  selectedAgent,
  selectedAgentConfig,
  setProjectPlanningInput,
  setProjectScenarioIndex,
  setRevenueScenarioIndex,
  setSelectedAgent,
  statusMessage,
  visibleScenarios,
}: {
  activeProgress: RunProgress | null
  availableAgentConfigs: AgentConfig[]
  availableAgentIds: AgentKey[]
  copy: (typeof scopeCopy)[RunScope]
  currentProjectScenario: DemoScenario
  isSubmitting: boolean
  onGuidedDemo: () => void
  onPayloadPreview: () => void
  onPayloadPreviewClose: () => void
  onRunAgent: () => void
  onRunScope: () => void
  onTraceReplay: () => void
  payloadPreviewGroups: PayloadPreviewGroup[]
  payloadPreviewOpen: boolean
  projectPlanningInput: ProjectPlanningInput
  projectScenarioIndex: number
  revenueScenarioIndex: number
  scope: RunScope
  selectedAgent: AgentKey
  selectedAgentConfig: AgentConfig
  setProjectPlanningInput: (input: ProjectPlanningInput) => void
  setProjectScenarioIndex: (index: number) => void
  setRevenueScenarioIndex: (index: number) => void
  setSelectedAgent: (agent: AgentKey) => void
  statusMessage: string
  visibleScenarios: DemoScenario[]
}) {
  const runIsActive = Boolean(activeProgress && !activeProgress.terminal)
  return (
    <div className="page-stack">
      {payloadPreviewOpen && (
        <PayloadPreviewPanel
          groups={payloadPreviewGroups}
          onClose={onPayloadPreviewClose}
          scopeLabel={copy.label}
        />
      )}
      <section className="section">
        <SectionHeader
          icon={<Play size={18} />}
          label={copy.label}
          title="Run and Demo Console"
          subtitle="Choose scope, review the active scenario, run one agent or the selected scope, and keep progress visible."
          action={
            <div className="button-row">
              <button
                className="btn"
                type="button"
                disabled={isSubmitting || runIsActive}
                onClick={onRunAgent}
              >
                Run single agent
              </button>
              <button
                className="btn primary"
                type="button"
                disabled={isSubmitting || runIsActive}
                onClick={onRunScope}
              >
                {(isSubmitting || runIsActive) && <LoaderCircle className="spin-icon" size={16} />}
                {isSubmitting
                  ? 'Submitting...'
                  : runIsActive && activeProgress
                    ? `Running ${activeProgress.complete + activeProgress.failed}/${activeProgress.total}`
                    : copy.runTitle}
              </button>
            </div>
          }
        />
        <div className="run-console">
          <div className="run-console-main">
            <ScenarioSelectorGrid
              disabled={isSubmitting || runIsActive}
              projectScenarioIndex={projectScenarioIndex}
              revenueScenarioIndex={revenueScenarioIndex}
              scope={scope}
              setProjectScenarioIndex={setProjectScenarioIndex}
              setRevenueScenarioIndex={setRevenueScenarioIndex}
            />
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
              <button className="run-command" type="button" onClick={onGuidedDemo}>
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
            <span className="pill">Run status</span>
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
            <label htmlFor="run-console-agent">{copy.label} single-agent run</label>
            <AgentSelect
              id="run-console-agent"
              agentIds={availableAgentIds}
              value={selectedAgent}
              onChange={(event) => setSelectedAgent(event.target.value as AgentKey)}
            />
            <div className="button-row">
              <button className="btn" type="button" onClick={onPayloadPreview}>Preview payload</button>
              <button className="btn" type="button" onClick={onTraceReplay}>Replay last run</button>
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
    </div>
  )
}

function ScenarioSelectorGrid({
  disabled,
  projectScenarioIndex,
  revenueScenarioIndex,
  scope,
  setProjectScenarioIndex,
  setRevenueScenarioIndex,
}: {
  disabled: boolean
  projectScenarioIndex: number
  revenueScenarioIndex: number
  scope: RunScope
  setProjectScenarioIndex: (index: number) => void
  setRevenueScenarioIndex: (index: number) => void
}) {
  const showProject = scope === 'platform' || scope === 'project'
  const showRevenue = scope === 'platform' || scope === 'revenue'

  return (
    <div className="scenario-selector-grid" aria-label="Scenario selection">
      {showProject && (
        <label className="scenario-select-card" htmlFor="project-scenario-select">
          <span>Project Management scenario</span>
          <select
            id="project-scenario-select"
            value={projectScenarioIndex % projectScenarios.length}
            disabled={disabled}
            onChange={(event) => setProjectScenarioIndex(Number(event.target.value))}
          >
            {projectScenarios.map((scenario, index) => (
              <option value={index} key={scenario.id}>
                {scenario.title}
              </option>
            ))}
          </select>
          <b>{projectScenarios.length} options</b>
        </label>
      )}
      {showRevenue && (
        <label className="scenario-select-card" htmlFor="revenue-scenario-select">
          <span>Revenue Ops scenario</span>
          <select
            id="revenue-scenario-select"
            value={revenueScenarioIndex % revenueScenarios.length}
            disabled={disabled}
            onChange={(event) => setRevenueScenarioIndex(Number(event.target.value))}
          >
            {revenueScenarios.map((scenario, index) => (
              <option value={index} key={scenario.id}>
                {scenario.title}
              </option>
            ))}
          </select>
          <b>{revenueScenarios.length} options</b>
        </label>
      )}
    </div>
  )
}

function payloadNumber(payload: Record<string, unknown> | undefined, key: string) {
  const value = payload?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function payloadArrayLength(payload: Record<string, unknown> | undefined, key: string) {
  const value = payload?.[key]
  return Array.isArray(value) ? value.length : 0
}

function weightedPipeline(payload: Record<string, unknown> | undefined) {
  const deals = payload?.pipeline_deals
  if (!Array.isArray(deals)) return 0
  return deals.reduce((sum, deal) => {
    if (!deal || typeof deal !== 'object') return sum
    const row = deal as Record<string, unknown>
    return sum + payloadNumber(row, 'arr') * payloadNumber(row, 'crm_probability')
  }, 0)
}

function scenarioDataFacts(scenario: DemoScenario) {
  if (scenario.domain === 'project') {
    const sprint = scenario.payloads['agent-sprint-risk']
    const allocation = scenario.payloads['agent-resource-alloc']
    const forecast = scenario.payloads['agent-delivery-forecast']
    const remainingTasks = Math.max(
      0,
      payloadNumber(sprint, 'total_tasks') - payloadNumber(sprint, 'completed_tasks'),
    )
    return {
      eyebrow: 'Project Management',
      business: [
        ['Committed revenue', money(payloadNumber(forecast, 'committed_revenue_usd'))],
        ['Weekly delay exposure', money(payloadNumber(sprint, 'delay_cost_per_week_usd'))],
        ['Remaining tasks', String(remainingTasks)],
        ['Remaining engineering hours', String(payloadNumber(sprint, 'remaining_engineering_hours'))],
      ],
      technical: [
        ['Team records', `${payloadArrayLength(allocation, 'team_members')} named people`],
        ['Critical task records', `${payloadArrayLength(allocation, 'tasks')} allocatable tasks`],
        ['Capacity model', `${payloadNumber(sprint, 'available_engineering_hours')} available hours`],
        ['Velocity history', `${payloadArrayLength(sprint, 'velocity_history')} sprints`],
      ],
    }
  }

  const renewal = scenario.payloads['agent-renewal-risk']
  const churn = scenario.payloads['agent-churn-signal']
  const pipeline = scenario.payloads['agent-pipeline-forecast']
  const weighted = weightedPipeline(pipeline)
  const quota = payloadNumber(pipeline, 'quota_target')
  const closed = payloadNumber(pipeline, 'closed_to_date_usd')
  return {
    eyebrow: 'Revenue Management',
    business: [
      ['Quota target', money(quota)],
      ['Closed to date', money(closed)],
      ['Weighted pipeline', money(weighted)],
      ['Open quota gap', money(Math.max(0, quota - closed - weighted))],
    ],
    technical: [
      ['Renewal account ARR', money(payloadNumber(renewal, 'account_arr'))],
      ['Churn exposure ARR', money(payloadNumber(churn, 'account_arr'))],
      ['Pipeline deal rows', `${payloadArrayLength(pipeline, 'pipeline_deals')} deals`],
      ['Forecast rollups', 'closed, commit, best case, weighted'],
    ],
  }
}

function DemoDataView({
  groups,
  persona,
  scenarios,
}: {
  groups: PayloadPreviewGroup[]
  persona: Persona
  scenarios: DemoScenario[]
}) {
  const payloadCount = groups.reduce((sum, group) => sum + group.items.length, 0)
  const projectRevenue = scenarios
    .filter((scenario) => scenario.domain === 'project')
    .reduce(
      (sum, scenario) =>
        sum + payloadNumber(scenario.payloads['agent-delivery-forecast'], 'committed_revenue_usd'),
      0,
    )
  const revenueQuota = scenarios
    .filter((scenario) => scenario.domain === 'revenue')
    .reduce(
      (sum, scenario) =>
        sum + payloadNumber(scenario.payloads['agent-pipeline-forecast'], 'quota_target'),
      0,
    )

  return (
    <div className="page-stack">
      <section className="kpi-grid" aria-label="Demo data summary">
        <Kpi label="Scenario scope" value={String(scenarios.length)} detail="active demo scenarios" />
        <Kpi label="Agent payloads" value={String(payloadCount)} detail="exact run inputs" />
        <Kpi label="Project value" value={money(projectRevenue)} detail="delivery-linked revenue" />
        <Kpi label="Revenue target" value={money(revenueQuota)} detail="quota in active revenue data" />
        <Kpi label="Lens" value={persona === 'business' ? 'Business' : 'Technical'} detail="same data, different framing" />
      </section>

      <section className="section">
        <SectionHeader
          icon={<Database size={18} />}
          label="business data"
          title="Scenario Assumptions"
          subtitle="The demo uses scaled project and revenue scenarios so team size, work volume, exposure, quota, and account risk move together."
        />
        <div className="data-scenario-grid">
          {scenarios.map((scenario) => {
            const facts = scenarioDataFacts(scenario)
            return (
              <article className="data-scenario-card" key={scenario.id}>
                <span>{facts.eyebrow}</span>
                <strong>{scenario.title}</strong>
                <p>{scenario.summary}</p>
                <div className="data-fact-grid">
                  {facts.business.map(([label, value]) => (
                    <div key={label}>
                      <span>{label}</span>
                      <b>{value}</b>
                    </div>
                  ))}
                </div>
              </article>
            )
          })}
        </div>
      </section>

      <section className="section">
        <SectionHeader
          icon={<Cpu size={18} />}
          label="technical data"
          title="Payload Contract"
          subtitle="These are the concrete app payloads sent to FastAPI for each selected business agent."
        />
        <div className="data-technical-grid">
          {scenarios.map((scenario) => {
            const facts = scenarioDataFacts(scenario)
            return (
              <article className="data-technical-card" key={scenario.id}>
                <span>{scenario.domain === 'project' ? 'Project payload shape' : 'Revenue payload shape'}</span>
                <strong>{scenario.title}</strong>
                {facts.technical.map(([label, value]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <b>{value}</b>
                  </div>
                ))}
              </article>
            )
          })}
        </div>
        <div className="payload-domain-list data-payload-list">
          {groups.map((group) => (
            <details className="payload-domain-group" key={group.domain}>
              <summary>
                <div>
                  <span>{group.label}</span>
                  <strong>{group.scenarioTitle}</strong>
                  <em>{group.items.length} payload{group.items.length === 1 ? '' : 's'} available for inspection</em>
                </div>
                <b>{group.items.length} agents</b>
              </summary>
              <div className="payload-agent-list">
                {group.items.map(({ agent, payload }) => (
                  <details className="payload-agent-card" key={agent.id}>
                    <summary>
                      <div>
                        <strong>{agent.name}</strong>
                        <span>{agent.description}</span>
                      </div>
                      <b>{Object.keys(payload).length} fields</b>
                    </summary>
                    <pre>{JSON.stringify(payload, null, 2)}</pre>
                  </details>
                ))}
              </div>
            </details>
          ))}
        </div>
      </section>
    </div>
  )
}

function PayloadPreviewPanel({
  groups,
  onClose,
  scopeLabel,
}: {
  groups: PayloadPreviewGroup[]
  onClose: () => void
  scopeLabel: string
}) {
  return (
    <section className="section payload-preview-section">
      <SectionHeader
        icon={<FileText size={18} />}
        label="payload preview"
        title={`${scopeLabel} Inputs`}
        subtitle="These are the exact app payloads used for the selected run scope. ProjectPlanningAgent reflects the editable project input."
        action={
          <button className="btn" type="button" onClick={onClose}>
            Hide preview
          </button>
        }
      />
      <div className="payload-domain-list">
        {groups.map((group) => (
          <details className="payload-domain-group" key={group.domain} open>
            <summary>
              <div>
                <span>{group.label}</span>
                <strong>{group.scenarioTitle}</strong>
                <em>{group.items.length} payload{group.items.length === 1 ? '' : 's'} in this domain</em>
              </div>
              <b>{group.items.length} agents</b>
            </summary>
            <div className="payload-agent-list">
              {group.items.map(({ agent, payload }) => (
                <details className="payload-agent-card" key={agent.id} open={group.items.length <= 4}>
                  <summary>
                    <div>
                      <strong>{agent.name}</strong>
                      <span>{agent.description}</span>
                    </div>
                    <b>{Object.keys(payload).length} fields</b>
                  </summary>
                  <pre>{JSON.stringify(payload, null, 2)}</pre>
                </details>
              ))}
            </div>
          </details>
        ))}
      </div>
    </section>
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
          {evidenceGroups(runs).map((group) => (
            <EvidenceGroupView group={group} key={group.domain} />
          ))}
        </div>
      )}
    </section>
  )
}

type OutcomeLedgerRow = {
  outcome: BusinessOutcome
  run: AgentRun | undefined
  agentName: string
  cost: number
  net: number
  roi: number | null
  owner: string
  action: string
  narrative: string
}

type OutcomeLedgerGroup = {
  domain: string
  label: string
  rows: OutcomeLedgerRow[]
  impact: number
  cost: number
  net: number
  roi: number | null
  confidence: number | null
  agentCount: number
}

function ledgerDomainLabel(domain: string) {
  if (domain === 'PROJECT_DELIVERY') return 'Project Management'
  if (domain === 'REVENUE_OPS') return 'Revenue Management'
  return domain.replace(/_/g, ' ')
}

function uniqueRunCost(rows: OutcomeLedgerRow[]) {
  const costs = new Map<string, number>()
  for (const row of rows) {
    if (row.run) costs.set(row.run.id, row.run.cost_usd)
  }
  return [...costs.values()].reduce((sum, value) => sum + value, 0)
}

function formatMultiple(value: number | null) {
  if (value === null || !Number.isFinite(value)) return 'n/a'
  return `${value.toFixed(value >= 10 ? 0 : 1)}x`
}

function formatConfidence(value: number | null) {
  return value === null ? 'pending' : value.toFixed(2)
}

function valueTone(value: number) {
  if (value < 0) return 'negative'
  if (value > 0) return 'positive'
  return 'neutral'
}

function buildOutcomeRows(outcomes: BusinessOutcome[], runs: AgentRun[]): OutcomeLedgerRow[] {
  const runById = new Map(runs.map((run) => [run.id, run]))
  return outcomes
    .map((outcome) => {
      const run = runById.get(outcome.agent_run_id)
      const metadata = outcomeMetadata(outcome.metric_name)
      const agentConfig = run ? agentConfigForRun(run) : undefined
      const cost = run?.cost_usd ?? 0
      return {
        outcome,
        run,
        agentName: agentConfig?.name ?? run?.agent_id ?? 'Unknown agent',
        cost,
        net: outcome.financial_impact_usd - cost,
        roi: cost > 0 ? outcome.financial_impact_usd / cost : null,
        owner: metadata.owner,
        action: metadata.action,
        narrative: metadata.narrative,
      }
    })
    .sort((left, right) => right.outcome.financial_impact_usd - left.outcome.financial_impact_usd)
}

function buildOutcomeGroups(rows: OutcomeLedgerRow[]): OutcomeLedgerGroup[] {
  const grouped = new Map<string, OutcomeLedgerRow[]>()
  for (const row of rows) {
    const groupRows = grouped.get(row.outcome.domain) ?? []
    groupRows.push(row)
    grouped.set(row.outcome.domain, groupRows)
  }
  return [...grouped.entries()]
    .map(([domain, groupRows]) => {
      const impact = groupRows.reduce(
        (sum, row) => sum + row.outcome.financial_impact_usd,
        0,
      )
      const cost = uniqueRunCost(groupRows)
      const confidenceScores = groupRows.map((row) => row.outcome.confidence_score)
      const confidence = confidenceScores.length
        ? confidenceScores.reduce((sum, score) => sum + score, 0) / confidenceScores.length
        : null
      const agents = new Set(groupRows.map((row) => row.agentName))
      return {
        domain,
        label: ledgerDomainLabel(domain),
        rows: groupRows,
        impact,
        cost,
        net: impact - cost,
        roi: cost > 0 ? impact / cost : null,
        confidence,
        agentCount: agents.size,
      }
    })
    .sort((left, right) => right.impact - left.impact)
}

function OutcomesView({
  outcomes,
  runs,
  sessionImpact,
}: {
  outcomes: BusinessOutcome[]
  runs: AgentRun[]
  sessionImpact: number
}) {
  const rows = useMemo(() => buildOutcomeRows(outcomes, runs), [outcomes, runs])
  const groups = useMemo(() => buildOutcomeGroups(rows), [rows])
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null)
  const [selectedOutcomeId, setSelectedOutcomeId] = useState<string | null>(null)
  const selectedGroup = groups.find((group) => group.domain === selectedDomain) ?? groups[0]
  const selectedRow =
    selectedGroup?.rows.find((row) => row.outcome.id === selectedOutcomeId) ??
    selectedGroup?.rows[0]
  const ledgerCost = uniqueRunCost(rows)
  const ledgerNet = sessionImpact - ledgerCost
  const ledgerRoi = ledgerCost > 0 ? sessionImpact / ledgerCost : null
  const ledgerConfidence = rows.length
    ? rows.reduce((sum, row) => sum + row.outcome.confidence_score, 0) / rows.length
    : null

  function selectGroup(group: OutcomeLedgerGroup) {
    setSelectedDomain(group.domain)
    setSelectedOutcomeId(null)
  }

  return (
    <div className="page-stack">
      <section className="section">
        <SectionHeader
          icon={<BarChart3 size={18} />}
          label={money(sessionImpact)}
          title="Outcome Ledger"
          subtitle="CFO view of protected value, run cost, confidence, source agent, owner, and next action."
        />
        {outcomes.length === 0 ? (
          <EmptyState text="Run a platform or domain demo to populate financial outcomes." />
        ) : (
          <>
            <div className="outcome-ledger-kpis" aria-label="Outcome ledger summary">
              <Kpi label="Protected value" value={money(sessionImpact)} detail={`${rows.length} outcomes`} />
              <Kpi label="Run cost" value={costMoney(ledgerCost)} detail="token, API, compute" />
              <Kpi
                label="Net value"
                value={money(ledgerNet)}
                detail={ledgerNet >= 0 ? 'after run cost' : 'cost exceeds value'}
              />
              <Kpi label="ROI" value={formatMultiple(ledgerRoi)} detail={`${formatConfidence(ledgerConfidence)} confidence`} />
            </div>

            <div className="outcome-domain-grid" aria-label="Outcome groups">
              {groups.map((group) => (
                <button
                  className={`outcome-domain-card ${selectedGroup?.domain === group.domain ? 'active' : ''}`}
                  type="button"
                  key={group.domain}
                  onClick={() => selectGroup(group)}
                >
                  <span>{group.label}</span>
                  <strong>{money(group.impact)}</strong>
                  <small>{group.rows.length} outcomes from {group.agentCount} agents</small>
                  <div>
                    <b>{costMoney(group.cost)} cost</b>
                    <b>{formatMultiple(group.roi)} ROI</b>
                    <b>{formatConfidence(group.confidence)} confidence</b>
                  </div>
                </button>
              ))}
            </div>

            {selectedGroup && (
              <div className="outcome-ledger-workspace">
                <section className="outcome-drilldown" aria-label={`${selectedGroup.label} outcomes`}>
                  <div className="outcome-drilldown-head">
                    <div>
                      <span>Selected group</span>
                      <h3>{selectedGroup.label}</h3>
                      <p>
                        {money(selectedGroup.impact)} protected value, {costMoney(selectedGroup.cost)} run cost, {money(selectedGroup.net)} net.
                      </p>
                    </div>
                    <strong>{formatMultiple(selectedGroup.roi)}</strong>
                  </div>
                  <div className="outcome-row-list">
                    {selectedGroup.rows.map((row) => (
                      <button
                        className={`outcome-row ${selectedRow?.outcome.id === row.outcome.id ? 'active' : ''}`}
                        type="button"
                        key={row.outcome.id}
                        onClick={() => setSelectedOutcomeId(row.outcome.id)}
                      >
                        <div>
                          <strong>{metricLabel(row.outcome.metric_name)}</strong>
                          <span>{row.agentName} - owner: {row.owner}</span>
                        </div>
                        <b className={valueTone(row.outcome.financial_impact_usd)}>
                          {money(row.outcome.financial_impact_usd)}
                        </b>
                        <em>{row.outcome.confidence_score.toFixed(2)}</em>
                      </button>
                    ))}
                  </div>
                </section>

                <aside className="outcome-detail-panel" aria-label="Outcome detail">
                  {selectedRow ? (
                    <>
                      <span>Outcome detail</span>
                      <h3>{metricLabel(selectedRow.outcome.metric_name)}</h3>
                      <p>{selectedRow.narrative}</p>
                      <dl>
                        <div><dt>Financial impact</dt><dd className={valueTone(selectedRow.outcome.financial_impact_usd)}>{money(selectedRow.outcome.financial_impact_usd)}</dd></div>
                        <div><dt>Run cost</dt><dd>{costMoney(selectedRow.cost)}</dd></div>
                        <div><dt>Net value</dt><dd className={valueTone(selectedRow.net)}>{money(selectedRow.net)}</dd></div>
                        <div><dt>ROI</dt><dd>{formatMultiple(selectedRow.roi)}</dd></div>
                        <div><dt>Confidence</dt><dd>{selectedRow.outcome.confidence_score.toFixed(2)}</dd></div>
                        <div><dt>Source agent</dt><dd>{selectedRow.agentName}</dd></div>
                        <div><dt>Model</dt><dd>{selectedRow.run?.model_used ?? 'not captured'}</dd></div>
                        <div><dt>Latency</dt><dd>{selectedRow.run ? `${selectedRow.run.latency_ms} ms` : 'not captured'}</dd></div>
                        <div><dt>Tokens</dt><dd>{selectedRow.run?.total_tokens ?? 0}</dd></div>
                        <div><dt>Metric basis</dt><dd>{selectedRow.outcome.metric_value.toLocaleString()} {selectedRow.outcome.metric_unit}</dd></div>
                        <div><dt>Action owner</dt><dd>{selectedRow.owner}</dd></div>
                      </dl>
                      <div className="outcome-next-action">
                        <strong>Next action</strong>
                        <p>{selectedRow.action}</p>
                      </div>
                    </>
                  ) : (
                    <EmptyState text="Select a domain outcome to inspect detail." />
                  )}
                </aside>
              </div>
            )}
          </>
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
          <EmptyState text="No run evidence yet. Start a demo from Run Console." />
        ) : (
          <div className="run-list">
            {evidenceGroups(runs).map((group) => (
              <EvidenceGroupView group={group} key={group.domain} />
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
              <button className="btn" type="button" onClick={() => onViewChange('evidence')}>
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
            <p>run trust evidence</p>
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
            <button className="btn" type="button" onClick={() => onViewChange('evidence')}>
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
  modelPricing,
  models,
  onApplyProvider,
  onRunAgent,
  onRunScope,
  onViewChange,
  provider,
  providers,
  runtimeProvider,
  scope,
  selectedAgent,
  selectedModel,
  setSelectedAgent,
  setSelectedModel,
  setProvider,
}: {
  availableAgentIds: AgentKey[]
  modelPricing: ModelPricing | undefined
  models: string[]
  onApplyProvider: () => void
  onRunAgent: () => void
  onRunScope: () => void
  onViewChange: (view: ViewId) => void
  provider: ProviderKey
  providers: ProviderKey[]
  runtimeProvider: RuntimeProvider | undefined
  scope: RunScope
  selectedAgent: AgentKey
  selectedModel: string
  setSelectedAgent: (agent: AgentKey) => void
  setSelectedModel: (model: string) => void
  setProvider: (provider: ProviderKey) => void
}) {
  const selectedProvider = providerCatalog[provider]
  const estimatedInputTokens = 10000
  const estimatedOutputTokens = 2500
  const estimatedRunSeconds = 30
  const estimatedTokenCost = modelPricing
    ? (estimatedInputTokens / 1000) * modelPricing.input_cost_per_1k +
      (estimatedOutputTokens / 1000) * modelPricing.output_cost_per_1k
    : 0
  const estimatedApiCost = modelPricing
    ? (API_CALLS_PER_AGENT_RUN / 1000) * modelPricing.api_call_cost_per_1k
    : 0
  const estimatedComputeCost = modelPricing
    ? estimatedRunSeconds * computeCostPerSecond(modelPricing)
    : 0
  const estimatedCost = modelPricing
    ? estimatedTokenCost + estimatedApiCost + estimatedComputeCost
    : 0

  return (
    <div className="page-stack">
      <section className="section">
        <SectionHeader
          icon={<Settings size={18} />}
          label="configuration"
          title="Settings"
          subtitle="Provider, model, token pricing, and run defaults for the next demo execution."
          action={
            <button className="btn primary" type="button" onClick={onApplyProvider}>
              Apply provider
            </button>
          }
        />
        <div className="settings-grid">
          <SettingPanel title="Provider">
            <label htmlFor="settings-provider">Provider</label>
            <select
              id="settings-provider"
              value={provider}
              onChange={(event) => setProvider(event.target.value as ProviderKey)}
            >
              {providers.map((item) => (
                <option value={item} key={item}>
                  {providerCatalog[item].label}
                </option>
              ))}
            </select>
            <p>{selectedProvider.description}</p>
            <div>
              <span>Runtime status</span>
              <b>
                {runtimeProvider
                  ? runtimeProvider.configured
                    ? 'Configured'
                    : 'Needs credentials'
                  : 'Checking'}
              </b>
            </div>
            <div><span>Next best action</span><b>{selectedProvider.nextAction}</b></div>
          </SettingPanel>

          <SettingPanel title="Model Pricing">
            <label htmlFor="settings-model">Model</label>
            <select
              id="settings-model"
              value={selectedModel}
              onChange={(event) => setSelectedModel(event.target.value)}
            >
              {models.map((model) => (
                <option value={model} key={model}>
                  {model}
                </option>
              ))}
            </select>
            <div>
              <span>Input token price</span>
              <b>{modelPricing ? `${unitCostMoney(modelPricing.input_cost_per_1k)} / 1K` : 'Not priced'}</b>
            </div>
            <div>
              <span>Output token price</span>
              <b>{modelPricing ? `${unitCostMoney(modelPricing.output_cost_per_1k)} / 1K` : 'Not priced'}</b>
            </div>
            <div>
              <span>API call price</span>
              <b>{modelPricing ? `${unitCostMoney(modelPricing.api_call_cost_per_1k)} / 1K` : 'Not priced'}</b>
            </div>
            <div>
              <span>Compute price</span>
              <b>{modelPricing ? `${unitCostMoney(computeCostPerSecond(modelPricing))} / sec` : 'Not priced'}</b>
            </div>
            <div>
              <span>Total run estimate</span>
              <b>{modelPricing ? costMoney(estimatedCost) : 'Add pricing row'}</b>
            </div>
            <p>
              Estimate uses {estimatedInputTokens.toLocaleString()} input tokens, {estimatedOutputTokens.toLocaleString()} output tokens, {API_CALLS_PER_AGENT_RUN} API calls, {COMPUTE_VCPU_PER_AGENT_RUN} vCPU, {COMPUTE_MEMORY_GIB_PER_AGENT_RUN} GiB memory, and {estimatedRunSeconds}s runtime.
            </p>
          </SettingPanel>

          <SettingPanel title="Run Defaults">
            <div><span>Selected scope</span><b>{scopeCopy[scope].label}</b></div>
            <div><span>Scope agents</span><b>{scopeAgentIds[scope].length}</b></div>
            <div><span>Quality judge</span><b>async</b></div>
            <div className="setting-actions">
              <button className="btn" type="button" onClick={() => onViewChange('evidence')}>
                Inspect trace
              </button>
              <button className="btn primary" type="button" onClick={onRunScope}>
                Run {scopeCopy[scope].label}
              </button>
            </div>
          </SettingPanel>

          <SettingPanel title="Single Agent">
            <label htmlFor="settings-agent">{scopeCopy[scope].label} agent</label>
            <AgentSelect
              id="settings-agent"
              agentIds={availableAgentIds}
              value={selectedAgent}
              onChange={(event) => setSelectedAgent(event.target.value as AgentKey)}
            />
            <p>Use this to validate one agent before running the full selected scope.</p>
            <div className="setting-actions">
              <button className="btn" type="button" onClick={() => onViewChange('run')}>
                Back to run console
              </button>
              <button className="btn primary" type="button" onClick={onRunAgent}>
                Run selected agent
              </button>
            </div>
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

const workflowNodeLabels: Record<string, string> = {
  node_decompose: 'Decompose scope',
  node_capacity_check: 'Capacity check',
  node_risk_assess: 'Risk assessment',
  node_assign: 'Owner assignment',
  node_synthesize: 'Plan synthesis',
}

function statusToneFor(status: string) {
  return status === 'FAILED' ? 'bad' : status === 'COMPLETE' ? 'good' : 'warn'
}

function runDisplayName(run: AgentRun) {
  if (workflowNodeLabels[run.agent_id]) return workflowNodeLabels[run.agent_id]
  const agent = agentCatalog[run.agent_id as AgentKey]
  return agent?.name ?? run.agent_id
}

function runTypeLabel(runType: string) {
  return runType.replace(/_/g, ' ').toLowerCase()
}

function EvidenceGroupView({ group }: { group: EvidenceGroup }) {
  const complete = group.items.filter((item) => evidenceRunGroupStatus(item) === 'COMPLETE').length
  const failed = group.items.filter((item) => evidenceRunGroupStatus(item) === 'FAILED').length
  const inFlight = group.items.length - complete - failed

  return (
    <details className="evidence-domain-group" open>
      <summary className="evidence-domain-head">
        <div>
          <span>Execution domain</span>
          <strong>{group.label}</strong>
          <em>{group.items.length} agent run{group.items.length === 1 ? '' : 's'} grouped by business capability</em>
        </div>
        <div className="evidence-domain-counts" aria-label={`${group.label} run status summary`}>
          <b>{complete} complete</b>
          <b>{failed} failed</b>
          <b>{inFlight} in flight</b>
        </div>
        <span className="evidence-domain-toggle" aria-hidden="true" />
      </summary>
      <div className="evidence-domain-list">
        {group.items.map((item) => (
          <EvidenceRunGroupView group={item} key={evidenceRunGroupKey(item)} />
        ))}
      </div>
    </details>
  )
}

function EvidenceRunGroupView({ group }: { group: EvidenceRunGroup }) {
  if (group.kind === 'workflow') {
    return <WorkflowRunGroup parent={group.parent} nodes={group.nodes} />
  }
  return <RunRow run={group.run} />
}

function WorkflowRunGroup({ parent, nodes }: { parent: AgentRun; nodes: AgentRun[] }) {
  const statusTone = statusToneFor(parent.status)
  const completed = nodes.filter((node) => node.status === 'COMPLETE').length
  const failed = nodes.filter((node) => node.status === 'FAILED').length
  const inFlight = nodes.length - completed - failed

  return (
    <article className="workflow-run-group">
      <div className="workflow-run-parent">
        <div>
          <span>ProjectPlanningAgent workflow</span>
          <strong>{runDisplayName(parent)}</strong>
          <em>{runTypeLabel(parent.run_type)} - {parent.model_used}</em>
        </div>
        <span className={`status-pill ${statusTone}`}>{parent.status}</span>
        <dl>
          <div><dt>Latency</dt><dd>{parent.latency_ms} ms</dd></div>
          <div><dt>Tokens</dt><dd>{parent.total_tokens}</dd></div>
          <div><dt>Quality</dt><dd>{parent.quality_score?.toFixed(2) ?? 'pending'}</dd></div>
        </dl>
        {parent.error_message && <p className="run-error">{parent.error_message}</p>}
      </div>

      <div className="workflow-node-summary" aria-label="Workflow node summary">
        <span>{nodes.length} workflow nodes</span>
        <b>{completed} complete</b>
        <b>{failed} failed</b>
        <b>{inFlight} in flight</b>
      </div>

      <div className="workflow-node-list">
        {nodes.length === 0 ? (
          <p className="workflow-node-empty">Workflow node evidence will appear as the planning run progresses.</p>
        ) : (
          nodes.map((node, index) => (
            <div className="workflow-node-row" key={node.id}>
              <span className="workflow-node-index">{String(index + 1).padStart(2, '0')}</span>
              <div className="workflow-node-main">
                <strong>{runDisplayName(node)}</strong>
                <span>{node.agent_id} - {node.model_used}</span>
              </div>
              <span className={`status-pill ${statusToneFor(node.status)}`}>{node.status}</span>
              <dl>
                <div><dt>Latency</dt><dd>{node.latency_ms} ms</dd></div>
                <div><dt>Tokens</dt><dd>{node.total_tokens}</dd></div>
                <div><dt>Quality</dt><dd>{node.quality_score?.toFixed(2) ?? 'pending'}</dd></div>
              </dl>
              {node.error_message && <p className="run-error">{node.error_message}</p>}
            </div>
          ))
        )}
      </div>
    </article>
  )
}

function RunRow({ run }: { run: AgentRun }) {
  const statusTone = statusToneFor(run.status)
  return (
    <article className="run-row">
      <div>
        <strong>{runDisplayName(run)}</strong>
        <span>{runTypeLabel(run.run_type)} - {run.model_used}</span>
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
