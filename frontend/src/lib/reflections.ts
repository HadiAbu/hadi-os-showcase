import { api } from './api'

export type ReflectionKind = 'momentum' | 'drift' | 'theme'
export type ReflectionStatus = 'active' | 'pinned' | 'dismissed'

export interface ReflectionEvidence {
  objective_ids?: string[]
  journal_entry_ids?: string[]
  terms?: string[]
}

export interface Reflection {
  id: string
  kind: ReflectionKind
  body: string
  evidence: ReflectionEvidence
  status: ReflectionStatus
  created_at: string
}

export interface GenerateResult {
  reflections: Reflection[]
  reason: string | null
}

export const KIND_COLOR: Record<ReflectionKind, string> = {
  momentum: 'var(--aqua)',
  drift: 'var(--warn)',
  theme: 'var(--node-ctx)',
}

export async function fetchReflections(status?: ReflectionStatus): Promise<Reflection[]> {
  const { data } = await api.get<Reflection[]>('/reflections', {
    params: status ? { status } : undefined,
  })
  return data
}

export async function generateReflections(): Promise<GenerateResult> {
  const { data } = await api.post<GenerateResult>('/reflections/generate')
  return data
}

export async function patchReflection(
  id: string,
  status: ReflectionStatus,
): Promise<Reflection> {
  const { data } = await api.patch<Reflection>(`/reflections/${id}`, { status })
  return data
}
