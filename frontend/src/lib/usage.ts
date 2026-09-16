import { api } from './api'

export type UsageWindow = '7d' | '30d' | 'all'

export interface DayUsage {
  day: string
  prompt: number
  completion: number
  total: number
}
export interface ModelUsage {
  model: string
  prompt: number
  completion: number
  total: number
  pct: number
}
export interface ConversationUsage {
  conversation_id: string
  title: string
  total: number
}
export interface ToolUsage {
  tool_name: string
  count: number
}
export interface Usage {
  window: UsageWindow
  tokens: { prompt: number; completion: number; total: number }
  by_day: DayUsage[]
  by_model: ModelUsage[]
  by_conversation: ConversationUsage[]
  tool_calls_total: number
  tool_calls_by_name: ToolUsage[]
  estimated_cost_usd: number
  cost_known: boolean
}

export async function fetchUsage(window: UsageWindow): Promise<Usage> {
  const { data } = await api.get<Usage>('/usage', { params: { window } })
  return data
}

/** 12_345 → "12.3k", 900 → "900". */
export function compactTokens(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}k`
  return `${(n / 1_000_000).toFixed(1)}M`
}

export function costLabel(u: Pick<Usage, 'estimated_cost_usd' | 'cost_known'>): string {
  if (!u.cost_known) return 'cost n/a'
  if (u.estimated_cost_usd === 0) return '$0.00 · free tier'
  return `~$${u.estimated_cost_usd.toFixed(u.estimated_cost_usd < 1 ? 4 : 2)}`
}
