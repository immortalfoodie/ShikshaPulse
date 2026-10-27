// Shapes returned by the API (only the fields the UI reads).
export type User = {
  id: string; name: string; role: 'state' | 'district' | 'block' | 'headmaster'; title: string
  scope_type: 'state' | 'district' | 'block' | 'school'; scope: string | null; district: string | null; block: string | null
  school_name?: string; teacher?: boolean; crc?: boolean
}

export type LlmStatus = { provider: string; model: string; available: boolean; mode: string; calls: number; errors: number; last_error: string | null }

export type Meta = {
  public_demo?: boolean
  user: User; ready: boolean; years: string[]; tree: Record<string, string[]>; mode: string
  provenance_tiers: string[]; synthetic: boolean; scenario: string; llm: LlmStatus; schools: number; today?: string
}

export type Kpi = {
  metric: string; label: string; latest: number | null; baseline: number | null; change_pp: number | null
  state_latest: number | null; higher_is_better: boolean; spark: (number | null)[]; caveats: string[]; latest_year: string
}

export type Overview = {
  unit_type: string; unit: string; unit_label: string; baseline_year: string; latest_year: string; kpis: Kpi[]
  rank: { position: number | null; of: number; within: string; state_position: number | null; state_of: number } | null
  n_schools: number; n_blocks: number
  quality: { confidence: number; label: string; warnings: string[]; warning_items: { kind: string; source?: string; pct?: number; n?: number; from_year?: string; to_year?: string }[] }
}

export type TrendPoint = { year: string; value: number | null; value_all_instruments: number | null; n_schools: number }
export type Trend = { metric: string; label: string; unit_label: string; points: TrendPoint[]; change_pp: number | null; caveats: string[]; sources: string[] }

export type ChildReason = {
  unit_type: string; unit: string; name: string; baseline: number | null; latest: number | null; change_pp: number | null
  verdict: string; reasons: string[]; reason_items: import('./components/ui').ReasonItem[]; data_confidence: number; needs_review: boolean; district: string; block: string; comparable: boolean
}

export type Signal = {
  id: string; factor: string; label: string; classification: string; type: string; period: string; coverage: number
  baseline?: number; latest?: number; change?: number; assoc_r?: number; contribution_pp?: number; n_schools?: number
  direction?: string; note?: string; sources: string[]
  affected_schools?: { udise_code: string; school_name: string; block: string; baseline: number; latest: number; change: number }[]
  affected_units?: { unit_type: string; unit: string; change: number }[]
}

export type Diagnosis = {
  unit_type: string; unit: string; unit_label: string; metric_label: string; period: string; verdict: string; verdict_reason: string
  direction?: string; data_confidence: number; data_confidence_label: string; quality_warnings: string[]
  outcome: { baseline?: number; latest?: number; change_pp: number | null; n_schools_compared: number; sources: string[] }
  signals: Signal[]
  context: { id: string; event: string; period: string; avg_teacher_days_lost: number; blocks_affected: number; classification: string; source: string; start: string; end: string }[]
  unresolved: { id: string; text: string; remainder_pp?: number; child?: string; kind?: string; pp?: number | null; factor?: string; coverage_pct?: number; child_verdict?: string }[]
  data_gaps: string[]; data_gap_keys: string[]
  field_observations: { n_visits: number; n_schools: number; avg_score: number; items: { item: string; pct_yes: number }[]; first: string; last: string; simulated: boolean } | null
  quality_warning_items: { kind: string; source?: string; pct?: number; n?: number; from_year?: string; to_year?: string }[]
  explained_pp: number | null; remainder_pp: number | null
  model: { type: string; n: number; r2: number; coefficients: Record<string, number> }
  comparability_flags: { from_year: string; to_year: string; reason: string; detail: string }[]
}

export type Finding = { label: 'observed_fact' | 'associated_signal' | 'unresolved_question'; text: string; evidence: string[]; period?: string; added_by_guard?: boolean }
export type Evidence = { id: string; kind: string; title: string; type: string; period: string | null; data: Record<string, unknown>; source: string[] | string | null; link: Record<string, string> | null }
export type AskResult = {
  question: string; lang: string; engine: 'llm' | 'deterministic'; latency_ms: number; engine_note?: string
  answer: { summary: string; findings: Finding[]; next_steps: string[] }
  guard: { passed: boolean; badge: string; notes: string[]; numbers_checked: number; numbers_verified: number; unverified_numbers: { value: string; where: string }[] }
  tool_calls: { tool: string; args: Record<string, unknown>; ok: boolean }[]
  evidence: Evidence[]; llm: LlmStatus
}

export type Measurement = { id: number; kind: 'implementation' | 'learning'; indicator: string; unit: string | null; baseline: number | null; target: number | null; value: number | null; baseline_date: string | null; measured_at: string | null; evidence: string | null; recorded_by: string; is_simulated: number }
export type Action = {
  id: number; title: string; description: string; intervention_key: string | null; unit_type: string; unit: string; unit_name?: string; can_update?: boolean
  schools: ({ udise_code: string; school_name: string } | string)[]; owner_name: string; owner_role: string | null; owner_id: string | null
  due_date: string; priority: string; status: string; created_by: string; created_at: string; verified_by: string | null; verified_at: string | null
  evidence_note: string | null; evidence_file: string | null; is_simulated: boolean; measurements: Measurement[]
  updates: { id: number; user_name: string; note: string; status_from: string | null; status_to: string | null; at: string }[]
  outcome_status: string; overdue: boolean; implementation_ratio: number | null; learning_change: number | null; days_to_due: number | null
  issue?: { title: string; evidence: unknown[] }
}
export type ActionSummary = Record<string, number>

export type RadarSchool = {
  udise_code: string; school_name: string; block: string; district: string; flags: string[]; n_flags: number; reasons: string[]
  missing: string[]; tier: string; numeracy: number | null; numeracy_change: number | null; attendance: number | null
  attendance_change: number | null; maths_vacancy: number | null; infra: number | null; teacher_att: number | null
}
