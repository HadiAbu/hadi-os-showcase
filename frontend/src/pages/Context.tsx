import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

type Category =
  | 'identity'
  | 'preference'
  | 'goal_context'
  | 'project_context'
  | 'working_style'
  | 'misc'

const CATEGORIES: Category[] = [
  'identity',
  'preference',
  'goal_context',
  'project_context',
  'working_style',
  'misc',
]

interface Entry {
  id: string
  category: Category
  key: string
  value: string
  source: string
  pinned: boolean
  status: 'active' | 'proposed' | 'archived'
  updated_at: string
}

interface StyleSample {
  id: string
  text: string
  label: string | null
}

type Tab = 'entries' | 'review' | 'style'

export default function Context() {
  const [tab, setTab] = useState<Tab>('entries')
  const [reviewCount, setReviewCount] = useState(0)

  const refreshReviewCount = useCallback(async () => {
    const { data } = await api.get<Entry[]>('/context/review')
    setReviewCount(data.length)
  }, [])

  useEffect(() => {
    refreshReviewCount().catch(() => undefined)
  }, [refreshReviewCount])

  return (
    <div className="p-8">
      <h1 className="text-xl font-semibold">Context</h1>
      <p className="mt-1 text-sm text-muted-fg">What hadi-os knows about you.</p>

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as Tab)}
        className="mt-6 max-w-3xl"
      >
        <TabsList>
          <TabsTrigger value="entries">Entries</TabsTrigger>
          <TabsTrigger value="review">
            Review
            {reviewCount > 0 && (
              <span className="ml-1.5 rounded-full bg-warn px-1.5 py-0.5 text-[10px] font-semibold text-ink">
                {reviewCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="style">Style</TabsTrigger>
        </TabsList>

        <TabsContent value="entries" className="mt-6">
          <EntriesTab onChange={refreshReviewCount} />
        </TabsContent>
        <TabsContent value="review" className="mt-6">
          <ReviewTab onResolved={refreshReviewCount} />
        </TabsContent>
        <TabsContent value="style" className="mt-6">
          <StyleTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function EntriesTab({ onChange }: { onChange: () => void }) {
  const [entries, setEntries] = useState<Entry[]>([])
  const [form, setForm] = useState({ category: 'identity' as Category, key: '', value: '' })

  const load = useCallback(async () => {
    const { data } = await api.get<Entry[]>('/context/entries', { params: { status: 'active' } })
    setEntries(data)
  }, [])

  useEffect(() => {
    load().catch(() => undefined)
  }, [load])

  async function add(e: React.FormEvent) {
    e.preventDefault()
    if (!form.key.trim() || !form.value.trim()) return
    await api.post('/context/entries', form)
    setForm({ ...form, key: '', value: '' })
    await load()
    onChange()
  }

  async function save(id: string, value: string) {
    await api.patch(`/context/entries/${id}`, { value })
    await load()
  }

  async function togglePin(entry: Entry) {
    await api.patch(`/context/entries/${entry.id}`, { pinned: !entry.pinned })
    await load()
  }

  async function archive(id: string) {
    await api.post(`/context/entries/${id}/archive`)
    await load()
  }

  const grouped = CATEGORIES.map((c) => ({
    category: c,
    rows: entries.filter((e) => e.category === c),
  }))

  return (
    <div className="space-y-6">
      <form onSubmit={add} className="flex flex-wrap items-end gap-2">
        <Select
          value={form.category}
          onValueChange={(v) => setForm({ ...form, category: v as Category })}
        >
          <SelectTrigger className="h-8 w-[160px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CATEGORIES.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="key"
          value={form.key}
          onChange={(e) => setForm({ ...form, key: e.target.value })}
          className="w-32"
        />
        <Input
          placeholder="value"
          value={form.value}
          onChange={(e) => setForm({ ...form, value: e.target.value })}
          className="flex-1"
        />
        <Button type="submit">Add</Button>
      </form>

      {grouped
        .filter((g) => g.rows.length > 0)
        .map((g) => (
          <div key={g.category}>
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-faint">
              {g.category}
            </h3>
            <ul className="mt-2 divide-y divide-[var(--hairline)] rounded-xl border border-hairline bg-surface">
              {g.rows.map((entry) => (
                <EntryRow
                  key={entry.id}
                  entry={entry}
                  onSave={save}
                  onTogglePin={togglePin}
                  onArchive={archive}
                />
              ))}
            </ul>
          </div>
        ))}
      {entries.length === 0 && (
        <p className="text-sm text-faint">No active entries yet.</p>
      )}
    </div>
  )
}

function PinIcon({ filled }: { filled: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 17v5" />
      <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z" />
    </svg>
  )
}

function EntryRow({
  entry,
  onSave,
  onTogglePin,
  onArchive,
}: {
  entry: Entry
  onSave: (id: string, value: string) => void
  onTogglePin: (entry: Entry) => void
  onArchive: (id: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(entry.value)

  return (
    <li className="flex items-center gap-3 px-3.5 py-2.5 text-sm">
      <span className="mono w-32 shrink-0 text-xs text-muted-fg">{entry.key}</span>
      {editing ? (
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="h-7 flex-1 text-xs"
        />
      ) : (
        <span className="flex-1">{entry.value}</span>
      )}
      <button
        onClick={() => onTogglePin(entry)}
        title="pin (always in the prompt)"
        className={cn(
          'transition-colors',
          entry.pinned ? 'text-aqua' : 'text-faint hover:text-muted-fg',
        )}
      >
        <PinIcon filled={entry.pinned} />
      </button>
      {editing ? (
        <button
          onClick={() => {
            onSave(entry.id, value)
            setEditing(false)
          }}
          className="text-xs text-aqua hover:text-aqua-hi"
        >
          save
        </button>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="text-xs text-muted-fg hover:text-text"
        >
          edit
        </button>
      )}
      <button
        onClick={() => onArchive(entry.id)}
        className="text-xs text-faint hover:text-destructive"
      >
        archive
      </button>
    </li>
  )
}

function ReviewTab({ onResolved }: { onResolved: () => void }) {
  const [rows, setRows] = useState<Entry[]>([])

  const load = useCallback(async () => {
    const { data } = await api.get<Entry[]>('/context/review')
    setRows(data)
  }, [])

  useEffect(() => {
    load().catch(() => undefined)
  }, [load])

  async function resolve(id: string, action: 'approve' | 'discard', value?: string) {
    if (action === 'approve')
      await api.post(`/context/review/${id}/approve`, value ? { value } : {})
    else await api.post(`/context/review/${id}/discard`)
    await load()
    onResolved()
  }

  if (rows.length === 0) return <p className="text-sm text-faint">Nothing to review.</p>

  return (
    <ul className="space-y-3">
      {rows.map((entry) => (
        <ReviewRow key={entry.id} entry={entry} onResolve={resolve} />
      ))}
    </ul>
  )
}

function ReviewRow({
  entry,
  onResolve,
}: {
  entry: Entry
  onResolve: (id: string, action: 'approve' | 'discard', value?: string) => void
}) {
  const [value, setValue] = useState(entry.value)
  const edited = value !== entry.value

  return (
    <li className="rounded-xl border border-[var(--warn)]/40 bg-[var(--warn)]/[0.06] p-3.5 text-sm">
      <div className="mono text-xs text-warn">
        {entry.category}/{entry.key}
      </div>
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={2}
        className="mt-2"
      />
      <div className="mt-2 flex gap-2">
        <Button
          size="sm"
          onClick={() => onResolve(entry.id, 'approve', edited ? value : undefined)}
        >
          {edited ? 'Approve edited' : 'Approve'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onResolve(entry.id, 'discard')}
        >
          Discard
        </Button>
      </div>
    </li>
  )
}

function StyleTab() {
  const [guide, setGuide] = useState('')
  const [saved, setSaved] = useState(true)
  const [samples, setSamples] = useState<StyleSample[]>([])
  const [draft, setDraft] = useState({ text: '', label: '' })

  const load = useCallback(async () => {
    const [g, s] = await Promise.all([
      api.get<{ guide_md: string }>('/context/style-guide'),
      api.get<StyleSample[]>('/context/style-samples'),
    ])
    setGuide(g.data.guide_md)
    setSamples(s.data)
    setSaved(true)
  }, [])

  useEffect(() => {
    load().catch(() => undefined)
  }, [load])

  async function saveGuide() {
    await api.put('/context/style-guide', { guide_md: guide })
    setSaved(true)
  }

  async function addSample(e: React.FormEvent) {
    e.preventDefault()
    if (!draft.text.trim()) return
    await api.post('/context/style-samples', {
      text: draft.text,
      label: draft.label || null,
    })
    setDraft({ text: '', label: '' })
    await load()
  }

  async function removeSample(id: string) {
    await api.delete(`/context/style-samples/${id}`)
    await load()
  }

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-sm font-semibold">Style guide</h3>
        <p className="text-xs text-muted-fg">
          Injected into every chat response. Prose only — never code or lists.
        </p>
        <Textarea
          value={guide}
          onChange={(e) => {
            setGuide(e.target.value)
            setSaved(false)
          }}
          rows={6}
          className="mt-2"
        />
        <Button onClick={saveGuide} disabled={saved} size="sm" className="mt-2">
          {saved ? 'Saved' : 'Save'}
        </Button>
      </div>

      <div>
        <h3 className="text-sm font-semibold">Writing samples</h3>
        <form onSubmit={addSample} className="mt-2 space-y-2">
          <Textarea
            placeholder="Paste something you wrote…"
            value={draft.text}
            onChange={(e) => setDraft({ ...draft, text: e.target.value })}
            rows={3}
          />
          <div className="flex gap-2">
            <Input
              placeholder="label (optional)"
              value={draft.label}
              onChange={(e) => setDraft({ ...draft, label: e.target.value })}
              className="w-40"
            />
            <Button type="submit" variant="outline" size="sm">
              Add sample
            </Button>
          </div>
        </form>
        <ul className="mt-3 space-y-2">
          {samples.map((s) => (
            <li
              key={s.id}
              className="rounded-xl border border-hairline bg-surface p-3 text-sm"
            >
              {s.label && <div className="text-xs text-faint">{s.label}</div>}
              <div className="whitespace-pre-wrap">{s.text}</div>
              <button
                onClick={() => removeSample(s.id)}
                className="mt-1 text-xs text-faint hover:text-destructive"
              >
                remove
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
