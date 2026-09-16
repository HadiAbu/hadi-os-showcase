import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

// Presets for the default provider (Groq), verified working. Any model id the
// configured LLM_BASE_URL accepts also works via "Custom".
const PRESETS = [
  { id: 'openai/gpt-oss-120b', label: 'GPT-OSS 120B', note: 'strongest (Groq)' },
  { id: 'openai/gpt-oss-20b', label: 'GPT-OSS 20B', note: 'faster' },
  { id: 'qwen/qwen3.8-27b', label: 'Qwen3 27B', note: 'alternative' },
]

interface Entry {
  id: string
  category: string
  key: string
  value: string
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-faint">
      {children}
    </div>
  )
}

export default function Settings() {
  const { user, logout } = useAuth()
  const [entryId, setEntryId] = useState<string | null>(null)
  const [model, setModel] = useState<string>('') // '' == use server default
  const [customDraft, setCustomDraft] = useState('')
  const [status, setStatus] = useState<'idle' | 'saving' | 'error'>('idle')

  useEffect(() => {
    api
      .get<Entry[]>('/context/entries', { params: { category: 'misc' } })
      .then(({ data }) => {
        const row = data.find((e) => e.key === 'chat_model')
        if (row) {
          setEntryId(row.id)
          setModel(row.value)
          if (!PRESETS.some((p) => p.id === row.value)) setCustomDraft(row.value)
        }
      })
      .catch(() => undefined)
  }, [])

  async function apply(next: string) {
    setModel(next)
    setStatus('saving')
    try {
      if (next === '') {
        if (entryId) {
          await api.post(`/context/entries/${entryId}/archive`)
          setEntryId(null)
        }
      } else {
        const { data } = await api.post<Entry>('/context/entries', {
          category: 'misc',
          key: 'chat_model',
          value: next,
        })
        setEntryId(data.id)
      }
      setStatus('idle')
    } catch {
      setStatus('error')
    }
  }

  const isPreset = PRESETS.some((p) => p.id === model)
  const customActive = model !== '' && !isPreset

  const rows: { key: string; label: React.ReactNode; note: React.ReactNode; on: boolean; act: () => void }[] = [
    {
      key: '',
      label: 'Server default',
      note: <code className="mono">LLM_MODEL</code>,
      on: model === '',
      act: () => apply(''),
    },
    ...PRESETS.map((m) => ({
      key: m.id,
      label: m.label,
      note: m.note,
      on: model === m.id,
      act: () => apply(m.id),
    })),
  ]

  return (
    <div className="p-8">
      <h1 className="text-xl font-semibold">Settings</h1>

      <div className="mt-6 max-w-md space-y-8 text-sm">
        <div>
          <Label>Account</Label>
          <div className="mt-1 text-text">{user?.email}</div>
        </div>

        <div>
          <Label>
            Chat model
            {status === 'saving' && <span className="text-muted-fg"> · saving…</span>}
            {status === 'error' && <span className="text-destructive"> · couldn’t save</span>}
          </Label>

          <div className="mt-2 space-y-2">
            {rows.map((r) => (
              <label
                key={r.key || 'default'}
                className={cn(
                  'flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2',
                  r.on ? 'border-aqua' : 'border-hairline',
                )}
              >
                <input
                  type="radio"
                  name="model"
                  className="accent-[var(--aqua)]"
                  checked={r.on}
                  onChange={r.act}
                />
                <span className="font-medium">{r.label}</span>
                <span className="text-xs text-faint">{r.note}</span>
              </label>
            ))}

            <label
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2',
                customActive ? 'border-aqua' : 'border-hairline',
              )}
            >
              <input
                type="radio"
                name="model"
                className="accent-[var(--aqua)]"
                checked={customActive}
                onChange={() => customDraft.trim() && apply(customDraft.trim())}
              />
              <span className="font-medium">Custom</span>
              <Input
                value={customDraft}
                onChange={(e) => setCustomDraft(e.target.value)}
                onBlur={() => {
                  const v = customDraft.trim()
                  if (v && v !== model) apply(v)
                }}
                placeholder="model id"
                className="h-7 flex-1 text-xs"
              />
            </label>
          </div>
        </div>

        <Button variant="outline" onClick={logout}>
          Sign out
        </Button>
      </div>
    </div>
  )
}
