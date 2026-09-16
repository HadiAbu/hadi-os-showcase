import { api } from './api'

export type Mood = '' | 'good' | 'flat' | 'low' | 'energised' | 'drained'
export const MOODS: Exclude<Mood, ''>[] = ['good', 'flat', 'low', 'energised', 'drained']

export interface JournalEntry {
  id: string
  title: string
  body: string
  mood: Mood
  tags: string[]
  linked_objective_id: string | null
  linked_project_id: string | null
  learn_from_style: boolean
  created_at: string
  updated_at: string
}

export type JournalDraft = Partial<
  Pick<
    JournalEntry,
    | 'title'
    | 'body'
    | 'mood'
    | 'tags'
    | 'linked_objective_id'
    | 'linked_project_id'
    | 'learn_from_style'
  >
>

export async function fetchEntries(): Promise<JournalEntry[]> {
  const { data } = await api.get<JournalEntry[]>('/journal')
  return data
}

export async function createEntry(draft: JournalDraft): Promise<JournalEntry> {
  const { data } = await api.post<JournalEntry>('/journal', draft)
  return data
}

export async function patchEntry(id: string, draft: JournalDraft): Promise<JournalEntry> {
  const { data } = await api.patch<JournalEntry>(`/journal/${id}`, draft)
  return data
}

export async function deleteEntry(id: string): Promise<void> {
  await api.delete(`/journal/${id}`)
}

export async function continueEntry(id: string): Promise<string> {
  const { data } = await api.post<{ text: string }>(`/journal/${id}/continue`)
  return data.text
}

export function entryTitle(e: Pick<JournalEntry, 'title' | 'body'>): string {
  return e.title.trim() || e.body.trim().split('\n')[0].slice(0, 60) || 'Untitled'
}
