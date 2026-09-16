import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  continueEntry,
  createEntry,
  deleteEntry,
  patchEntry,
  type JournalDraft,
  type JournalEntry,
  type Mood,
} from '@/lib/journal'
import { MoodChips } from './MoodChips'

const NONE = '__none__'
const AUTOSAVE_MS = 2000

type NamedRow = { id: string; name: string }
type SaveState = 'idle' | 'saving' | 'saved' | 'error'

interface Props {
  entry: JournalEntry | null
  objectives: NamedRow[]
  projects: NamedRow[]
  onCreated: (entry: JournalEntry) => void
  onUpdated: (entry: JournalEntry) => void
  onDeleted: (id: string) => void
}

function draftOf(entry: JournalEntry | null): Required<JournalDraft> {
  return {
    title: entry?.title ?? '',
    body: entry?.body ?? '',
    mood: entry?.mood ?? '',
    tags: entry?.tags ?? [],
    linked_objective_id: entry?.linked_objective_id ?? null,
    linked_project_id: entry?.linked_project_id ?? null,
    learn_from_style: entry?.learn_from_style ?? true,
  }
}

export function JournalEditor({
  entry,
  objectives,
  projects,
  onCreated,
  onUpdated,
  onDeleted,
}: Props) {
  const [draft, setDraft] = useState(() => draftOf(entry))
  const [tagText, setTagText] = useState((entry?.tags ?? []).join(', '))
  const [save, setSave] = useState<SaveState>('idle')
  const [savedAt, setSavedAt] = useState<string | null>(null)
  const [aiHidden, setAiHidden] = useState(false)
  const [continuing, setContinuing] = useState(false)

  const savedId = useRef<string | null>(entry?.id ?? null)
  // serialised snapshot of what's on the server; used to debounce and to stop
  // the autosave effect re-triggering itself when a save re-renders the parent
  const savedSnapshot = useRef(JSON.stringify(draftOf(entry)))

  const persist = useCallback(
    async (next: Required<JournalDraft>): Promise<boolean> => {
      const isEmpty =
        !next.title.trim() && !next.body.trim() && next.tags.length === 0 && !next.mood
      if (savedId.current === null && isEmpty) return false
      setSave('saving')
      try {
        if (savedId.current === null) {
          const created = await createEntry(next)
          savedId.current = created.id
          onCreated(created)
        } else {
          onUpdated(await patchEntry(savedId.current, next))
        }
        setSave('saved')
        setSavedAt(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
        return true
      } catch {
        setSave('error')
        return false
      }
    },
    [onCreated, onUpdated],
  )
  const persistRef = useRef(persist)
  useEffect(() => {
    persistRef.current = persist
  })

  // save only once the draft has been idle for AUTOSAVE_MS and actually differs
  // from what's saved
  useEffect(() => {
    const snapshot = JSON.stringify(draft)
    if (snapshot === savedSnapshot.current) return
    const t = setTimeout(() => {
      void persistRef.current(draft).then((ok) => {
        if (ok) savedSnapshot.current = snapshot
      })
    }, AUTOSAVE_MS)
    return () => clearTimeout(t)
  }, [draft])

  function set<K extends keyof JournalDraft>(key: K, value: Required<JournalDraft>[K]) {
    setDraft((d) => ({ ...d, [key]: value }))
  }

  function commitTags(text: string) {
    setTagText(text)
    set(
      'tags',
      text
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
    )
  }

  async function onContinue() {
    if (savedId.current === null) return
    setContinuing(true)
    try {
      const text = await continueEntry(savedId.current)
      set('body', `${draft.body}${draft.body.endsWith('\n') || !draft.body ? '' : '\n\n'}${text}`)
    } catch (err: unknown) {
      const status =
        typeof err === 'object' && err && 'response' in err
          ? // @ts-expect-error narrow enough
            err.response?.status
          : undefined
      if (status === 503) setAiHidden(true)
    } finally {
      setContinuing(false)
    }
  }

  async function onDelete() {
    if (savedId.current === null) {
      onDeleted('new')
      return
    }
    await deleteEntry(savedId.current)
    onDeleted(savedId.current)
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-3 p-6">
      <div className="flex items-center gap-3">
        <Input
          value={draft.title}
          onChange={(e) => set('title', e.target.value)}
          placeholder="Title (optional)"
          className="h-10 flex-1 text-lg font-semibold"
        />
        <span className="text-xs text-faint">
          {save === 'saving'
            ? 'saving…'
            : save === 'error'
              ? 'save failed'
              : savedAt
                ? `saved · ${savedAt}`
                : ''}
        </span>
        <Button variant="ghost" size="sm" onClick={onDelete} className="text-faint hover:text-destructive">
          Delete
        </Button>
      </div>

      <Textarea
        value={draft.body}
        onChange={(e) => set('body', e.target.value)}
        placeholder="Write…"
        className="min-h-[46vh] flex-1 resize-none text-[15px] leading-relaxed"
      />

      {!aiHidden && (
        <div>
          <Button
            variant="outline"
            size="sm"
            onClick={onContinue}
            disabled={continuing || savedId.current === null}
          >
            {continuing ? 'writing…' : 'Continue in my voice'}
          </Button>
        </div>
      )}

      <div className="space-y-3 border-t border-hairline pt-3">
        <MoodChips value={draft.mood} onChange={(m: Mood) => set('mood', m)} />
        <Input
          value={tagText}
          onChange={(e) => commitTags(e.target.value)}
          placeholder="tags, comma separated"
          className="h-8 text-xs"
        />
        <div className="flex flex-wrap gap-2">
          <Select
            value={draft.linked_objective_id ?? NONE}
            onValueChange={(v) => set('linked_objective_id', v === NONE ? null : v)}
          >
            <SelectTrigger className="h-8 w-[190px] text-xs">
              <SelectValue placeholder="link an objective" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>(no objective)</SelectItem>
              {objectives.map((o) => (
                <SelectItem key={o.id} value={o.id}>
                  {o.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={draft.linked_project_id ?? NONE}
            onValueChange={(v) => set('linked_project_id', v === NONE ? null : v)}
          >
            <SelectTrigger className="h-8 w-[190px] text-xs">
              <SelectValue placeholder="link a project" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>(no project)</SelectItem>
              {projects.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-fg">
          <input
            type="checkbox"
            className="accent-[var(--aqua)]"
            checked={!draft.learn_from_style}
            onChange={(e) => set('learn_from_style', !e.target.checked)}
          />
          Don't learn my writing style from this entry
        </label>
      </div>
    </div>
  )
}
