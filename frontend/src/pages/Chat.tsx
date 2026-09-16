import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { streamChat, type ToolEvent } from '@/lib/sse'
import { cn } from '@/lib/utils'

interface Conversation {
  id: string
  title: string
  last_message_at: string | null
}
interface Message {
  role: 'user' | 'assistant'
  text: string
}
interface SidebarData {
  focus: string | null
  objectives: { id: string; title: string; priority: number }[]
  projects: { id: string; name: string }[]
  reviewCount: number
}

export default function Chat() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [assistantDraft, setAssistantDraft] = useState('')
  const [tools, setTools] = useState<ToolEvent[]>([])
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sidebar, setSidebar] = useState<SidebarData>({
    focus: null,
    objectives: [],
    projects: [],
    reviewCount: 0,
  })
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [conversationsOpen, setConversationsOpen] = useState(true)
  const threadRef = useRef<HTMLDivElement>(null)
  const booted = useRef(false)

  const loadConversations = useCallback(async () => {
    const { data } = await api.get<Conversation[]>('/chat/conversations')
    setConversations(data)
    return data
  }, [])

  const loadMessages = useCallback(async (id: string) => {
    const { data } = await api.get<Message[]>(`/chat/conversations/${id}/messages`)
    setMessages(data)
  }, [])

  const refreshSidebar = useCallback(async () => {
    const [obj, proj, review, focus] = await Promise.allSettled([
      api.get('/objectives', { params: { status: 'active' } }),
      api.get('/projects', { params: { status: 'active' } }),
      api.get('/context/review'),
      api.get('/dashboard/focus'),
    ])
    setSidebar({
      objectives: obj.status === 'fulfilled' ? obj.value.data.slice(0, 5) : [],
      projects: proj.status === 'fulfilled' ? proj.value.data.slice(0, 8) : [],
      reviewCount: review.status === 'fulfilled' ? review.value.data.length : 0,
      focus:
        focus.status === 'fulfilled' && focus.value.data
          ? (focus.value.data.content_md ?? null)
          : null,
    })
  }, [])

  useEffect(() => {
    // run once — a second invocation (React StrictMode / re-render) would POST
    // a second, empty conversation
    if (booted.current) return
    booted.current = true
    ;(async () => {
      const convs = await loadConversations()
      if (convs.length === 0) {
        const { data } = await api.post<{ id: string }>('/chat/conversations')
        await loadConversations()
        setActiveId(data.id)
      } else {
        setActiveId(convs[0].id)
      }
      await refreshSidebar()
    })().catch(() => setError('Could not load your chats.'))
  }, [loadConversations, refreshSidebar])

  useEffect(() => {
    if (activeId) loadMessages(activeId).catch(() => undefined)
  }, [activeId, loadMessages])

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight })
  }, [messages, assistantDraft, tools])

  async function newConversation() {
    const { data } = await api.post<{ id: string }>('/chat/conversations')
    await loadConversations()
    setActiveId(data.id)
    setMessages([])
  }

  async function send() {
    if (!draft.trim() || !activeId || streaming) return
    const text = draft.trim()
    setDraft('')
    setError(null)
    setMessages((m) => [...m, { role: 'user', text }])
    setAssistantDraft('')
    setTools([])
    setStreaming(true)

    await streamChat(activeId, text, {
      onToken: (delta) => setAssistantDraft((s) => s + delta),
      onTool: (t) =>
        setTools((prev) => {
          const i = prev.findIndex((p) => p.name === t.name && p.status === 'running')
          if (t.status !== 'running' && i >= 0) {
            const next = [...prev]
            next[i] = t
            return next
          }
          return [...prev, t]
        }),
      onMessage: (m) => {
        if (m) setMessages((prev) => [...prev, { role: 'assistant', text: m.text }])
        setAssistantDraft('')
      },
      onError: (detail) => setError(detail),
      onDone: () => {
        setStreaming(false)
        loadConversations().catch(() => undefined)
        refreshSidebar().catch(() => undefined)
      },
    })
    setStreaming(false)
  }

  return (
    <div className="flex h-screen bg-bg text-text">
      {/* conversation rail */}
      {conversationsOpen ? (
        <div className="flex w-56 shrink-0 flex-col border-r border-hairline bg-rail p-3">
          <div className="mb-3 flex items-center gap-2">
            <Button onClick={newConversation} className="flex-1">
              New chat
            </Button>
            <button
              onClick={() => setConversationsOpen(false)}
              className="text-faint hover:text-muted-fg"
              aria-label="Collapse conversations"
            >
              ‹
            </button>
          </div>
          <ul className="space-y-0.5 overflow-y-auto">
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => setActiveId(c.id)}
                  className={cn(
                    'w-full truncate rounded-md px-2 py-1.5 text-left text-sm transition-colors',
                    c.id === activeId
                      ? 'bg-aqua/[0.09] text-aqua'
                      : 'text-muted-fg hover:bg-raised hover:text-text',
                  )}
                >
                  {c.title || 'New chat'}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <button
          onClick={() => setConversationsOpen(true)}
          className="w-6 shrink-0 border-r border-hairline text-faint hover:text-muted-fg"
          aria-label="Expand conversations"
        >
          ›
        </button>
      )}

      {/* thread */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div ref={threadRef} className="flex-1 space-y-4 overflow-y-auto p-6">
          {messages.map((m, i) => (
            <Bubble key={i} role={m.role} text={m.text} />
          ))}
          {tools.map((t, i) => (
            <ToolChip key={`tool-${i}`} event={t} />
          ))}
          {assistantDraft && <Bubble role="assistant" text={assistantDraft} />}
          {streaming && !assistantDraft && <ThinkingPulse />}
          {error && <div className="text-sm text-destructive">{error}</div>}
        </div>
        <div className="border-t border-hairline p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              send()
            }}
            className="flex gap-2"
          >
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask hadi-os…"
              disabled={streaming}
              className="flex-1"
            />
            <Button disabled={streaming || !draft.trim()}>Send</Button>
          </form>
        </div>
      </div>

      {/* context sidebar */}
      {sidebarOpen ? (
        <div className="w-64 shrink-0 overflow-y-auto border-l border-hairline p-4 text-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-faint">
              What it knows
            </h3>
            <button
              onClick={() => setSidebarOpen(false)}
              className="text-faint hover:text-muted-fg"
            >
              ›
            </button>
          </div>

          {sidebar.focus && (
            <div className="mt-3 rounded-md border border-hairline bg-surface p-2 text-xs whitespace-pre-wrap text-muted-fg">
              {sidebar.focus}
            </div>
          )}

          <h4 className="mt-4 text-xs font-medium text-muted-fg">Objectives</h4>
          <ul className="mt-1 space-y-0.5">
            {sidebar.objectives.map((o) => (
              <li key={o.id} className="truncate text-text">
                <span className="mono text-faint">P{o.priority}</span> · {o.title}
              </li>
            ))}
            {sidebar.objectives.length === 0 && <li className="text-faint">none</li>}
          </ul>

          <h4 className="mt-4 text-xs font-medium text-muted-fg">Projects</h4>
          <ul className="mt-1 space-y-0.5">
            {sidebar.projects.map((p) => (
              <li key={p.id} className="truncate text-text">
                {p.name}
              </li>
            ))}
            {sidebar.projects.length === 0 && <li className="text-faint">none</li>}
          </ul>

          {sidebar.reviewCount > 0 && (
            <Link
              to="/context"
              className="mt-4 block rounded-md border border-[var(--warn)]/40 bg-[var(--warn)]/[0.06] px-2 py-1.5 text-xs text-warn"
            >
              {sidebar.reviewCount} proposed entr
              {sidebar.reviewCount === 1 ? 'y' : 'ies'} to review →
            </Link>
          )}
        </div>
      ) : (
        <button
          onClick={() => setSidebarOpen(true)}
          className="w-6 shrink-0 border-l border-hairline text-faint hover:text-muted-fg"
        >
          ‹
        </button>
      )}
    </div>
  )
}

function Bubble({ role, text }: { role: 'user' | 'assistant'; text: string }) {
  return (
    <div className={role === 'user' ? 'text-right' : ''}>
      <div
        className={cn(
          'inline-block max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm',
          role === 'user' ? 'bg-aqua text-ink' : 'bg-raised text-text',
        )}
      >
        {text}
      </div>
    </div>
  )
}

function ToolChip({ event }: { event: ToolEvent }) {
  const mark =
    event.status === 'running' ? '⋯' : event.status === 'error' ? '⚠' : '✓'
  return (
    <div
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs',
        event.status === 'error'
          ? 'border-[var(--danger)]/40 text-destructive'
          : 'border-hairline text-muted-fg',
      )}
    >
      <span className={event.status === 'running' ? 'animate-pulse text-aqua' : ''}>
        {mark}
      </span>
      <span className="mono">{event.summary || event.name}</span>
    </div>
  )
}

function ThinkingPulse() {
  return (
    <div className="flex items-center gap-1.5 text-xs text-faint">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-aqua" />
      thinking…
    </div>
  )
}
