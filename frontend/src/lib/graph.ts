import { api } from './api'

export type EntityType =
  | 'objective'
  | 'action'
  | 'project'
  | 'context'
  | 'conversation'
  | 'journal'

export interface GraphNode {
  id: string
  type: EntityType
  label: string
  meta: Record<string, unknown>
}

export interface GraphLink {
  source: string
  target: string
  kind: string
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
  truncated: boolean
}

export const NODE_TYPES: EntityType[] = [
  'objective',
  'project',
  'context',
  'action',
  'conversation',
  'journal',
]

/** Matches the --node-* tokens in index.css (canvas needs literal colours). */
export const NODE_COLOR: Record<EntityType, string> = {
  objective: '#4ff8d2',
  project: '#7cc7ff',
  context: '#b7a5ff',
  action: '#8fe9b0',
  conversation: '#5c6e6c',
  journal: '#e0a3c7',
}

export const NODE_LABEL: Record<EntityType, string> = {
  objective: 'Objectives',
  project: 'Projects',
  context: 'Context',
  action: 'Actions',
  conversation: 'Conversations',
  journal: 'Journal',
}

/** Where "open screen" navigates for a given node type. */
export const NODE_ROUTE: Record<EntityType, string> = {
  objective: '/objectives',
  action: '/objectives',
  project: '/projects',
  context: '/context',
  conversation: '/',
  journal: '/journal',
}

export async function fetchGraph(): Promise<GraphData> {
  const { data } = await api.get<GraphData>('/graph')
  return data
}
