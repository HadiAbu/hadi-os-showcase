import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { JournalEditor } from '@/components/journal/JournalEditor'
import { api } from '@/lib/api'
import { entryTitle, fetchEntries, type JournalEntry } from '@/lib/journal'
import { cn } from '@/lib/utils'

type NamedRow = { id: string; name: string }

const MOOD_DOT: Record<string, string> = {
  good: 'var(--node-act)',
  energised: 'var(--aqua)',
  flat: 'var(--text-faint)',
  low: 'var(--warn)',
  drained: 'var(--danger)',
}

export default function Journal() {
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [objectives, setObjectives] = useState<NamedRow[]>([])
  const [projects, setProjects] = useState<NamedRow[]>([])
  const [editorKey, setEditorKey] = useState<string>('new')
  const [activeId, setActiveId] = useState<string | null>(null)
  const [entriesOpen, setEntriesOpen] = useState(true)
  const booted = useRef(false)

  useEffect(() => {
    if (booted.current) return
    booted.current = true
    ;(async () => {
      const [es, os, ps] = await Promise.all([
        fetchEntries(),
        api.get<{ id: string; title: string }[]>('/objectives', { params: { status: 'active' } }),
        api.get<{ id: string; name: string }[]>('/projects'),
      ])
      setEntries(es)
      setObjectives(os.data.map((o) => ({ id: o.id, name: o.title })))
      setProjects(ps.data.map((p) => ({ id: p.id, name: p.name })))
      if (es.length) {
        setEditorKey(es[0].id)
        setActiveId(es[0].id)
      }
    })().catch(() => undefined)
  }, [])

  function openEntry(id: string) {
    setEditorKey(id)
    setActiveId(id)
  }

  function newEntry() {
    setEditorKey('new')
    setActiveId(null)
  }

  // stable identities so the editor's autosave effect isn't re-armed on every
  // parent render
  const onCreated = useCallback((created: JournalEntry) => {
    setEntries((prev) => [created, ...prev])
    setActiveId(created.id)
  }, [])
  const onUpdated = useCallback((updated: JournalEntry) => {
    setEntries((prev) => prev.map((e) => (e.id === updated.id ? updated : e)))
  }, [])
  const onDeleted = useCallback((id: string) => {
    setEntries((prev) => {
      const next = prev.filter((e) => e.id !== id)
      if (next.length) {
        setEditorKey(next[0].id)
        setActiveId(next[0].id)
      } else {
        setEditorKey('new')
        setActiveId(null)
      }
      return next
    })
  }, [])

  const activeEntry = entries.find((e) => e.id === editorKey) ?? null

  return (
    <div className="flex h-screen bg-bg text-text">
      {entriesOpen ? (
        <div className="flex w-64 shrink-0 flex-col border-r border-hairline bg-rail p-3">
          <div className="mb-3 flex items-center gap-2">
            <Button onClick={newEntry} className="flex-1">
              New entry
            </Button>
            <button
              onClick={() => setEntriesOpen(false)}
              className="text-faint hover:text-muted-fg"
              aria-label="Collapse entries"
            >
              ‹
            </button>
          </div>
          <ul className="space-y-0.5 overflow-y-auto">
            {entries.map((e) => (
              <li key={e.id}>
                <button
                  onClick={() => openEntry(e.id)}
                  className={cn(
                    'w-full rounded-md px-2 py-1.5 text-left transition-colors',
                    e.id === activeId
                      ? 'bg-aqua/[0.09] text-aqua'
                      : 'text-muted-fg hover:bg-raised hover:text-text',
                  )}
                >
                  <div className="flex items-center gap-1.5">
                    {e.mood && (
                      <span
                        className="h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ backgroundColor: MOOD_DOT[e.mood] }}
                      />
                    )}
                    <span className="truncate text-sm">{entryTitle(e)}</span>
                  </div>
                  <div className="mono mt-0.5 text-[10px] text-faint">
                    {e.created_at.slice(0, 10)}
                  </div>
                </button>
              </li>
            ))}
            {entries.length === 0 && (
              <li className="px-2 py-4 text-sm text-faint">No entries yet.</li>
            )}
          </ul>
        </div>
      ) : (
        <button
          onClick={() => setEntriesOpen(true)}
          className="w-6 shrink-0 border-r border-hairline text-faint hover:text-muted-fg"
          aria-label="Expand entries"
        >
          ›
        </button>
      )}

      <JournalEditor
        key={editorKey}
        entry={activeEntry}
        objectives={objectives}
        projects={projects}
        onCreated={onCreated}
        onUpdated={onUpdated}
        onDeleted={onDeleted}
      />
    </div>
  )
}
