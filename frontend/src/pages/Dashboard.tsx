import { Fragment, useCallback, useEffect, useState } from 'react'
import { GraphPanel } from '@/components/graph/GraphPanel'
import { ReflectionTeaser } from '@/components/reflections/ReflectionTeaser'
import { UsageCard } from '@/components/usage/UsageCard'
import { api } from '@/lib/api'

/** Tiny renderer for the LLM's markdown-shaped focus notes: headings, list
 *  items, and `**bold**`. Not a full markdown parser. */
function Markdownish({ text }: { text: string }) {
  const inline = (s: string) =>
    s.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith('**') && part.endsWith('**') ? (
        <strong key={i} className="text-text">
          {part.slice(2, -2)}
        </strong>
      ) : (
        <Fragment key={i}>{part}</Fragment>
      ),
    )
  return (
    <div className="space-y-1">
      {text
        .split('\n')
        .filter((l) => l.trim())
        .map((line, i) => {
          const heading = line.match(/^#{1,6}\s+(.*)/)
          if (heading)
            return (
              <p key={i} className="font-semibold text-text">
                {inline(heading[1])}
              </p>
            )
          const bullet = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/)
          if (bullet)
            return (
              <p key={i} className="flex gap-2">
                <span className="text-aqua">•</span>
                <span>{inline(bullet[1])}</span>
              </p>
            )
          return <p key={i}>{inline(line)}</p>
        })}
    </div>
  )
}

interface ObjectiveProgress {
  id: string
  title: string
  horizon: string
  priority: number
  open_actions: number
  total_actions: number
  pct_done: number
}
interface Momentum {
  actions_done_7d: number
  actions_done_30d: number
  objectives_touched_7d: number
  projects_touched_7d: number
}
interface ChangeItem {
  kind: 'objective' | 'action' | 'project'
  title: string
  at: string
  detail: string
}
interface DashboardData {
  objectives: ObjectiveProgress[]
  momentum: Momentum
  changed_this_week: ChangeItem[]
}
interface Focus {
  content_md: string | null
  created_at: string | null
  stale: boolean
}

function SectionCard({
  title,
  right,
  children,
  className,
}: {
  title: string
  right?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <section
      className={`rounded-xl border border-hairline bg-surface p-4 ${className ?? ''}`}
    >
      <div className="flex items-center justify-between">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-fg">
          {title}
        </h2>
        {right}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  )
}

const NOW = new Date().toLocaleDateString(undefined, {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
})

const KIND_COLOR: Record<ChangeItem['kind'], string> = {
  objective: 'var(--node-obj)',
  project: 'var(--node-proj)',
  action: 'var(--node-act)',
}

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [focus, setFocus] = useState<Focus | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [focusError, setFocusError] = useState<string | null>(null)

  const load = useCallback(async () => {
    const [d, f] = await Promise.all([
      api.get<DashboardData>('/dashboard'),
      api.get<Focus>('/dashboard/focus'),
    ])
    setData(d.data)
    setFocus(f.data)
  }, [])

  useEffect(() => {
    load().catch(() => undefined)
  }, [load])

  async function refreshFocus() {
    setRefreshing(true)
    setFocusError(null)
    try {
      const { data: f } = await api.post<Focus>('/dashboard/focus/refresh')
      setFocus(f)
    } catch (err: unknown) {
      const status =
        typeof err === 'object' && err && 'response' in err
          ? // @ts-expect-error narrow enough
            err.response?.status
          : undefined
      setFocusError(
        status === 503
          ? 'AI features are not configured on this server.'
          : 'Could not refresh.',
      )
    } finally {
      setRefreshing(false)
    }
  }

  if (!data) return <div className="p-8 text-sm text-faint">Loading…</div>

  const m = data.momentum
  const tiles = [
    { label: 'actions done · 7d', value: m.actions_done_7d },
    { label: 'actions done · 30d', value: m.actions_done_30d },
    { label: 'objectives touched · 7d', value: m.objectives_touched_7d },
    { label: 'projects touched · 7d', value: m.projects_touched_7d },
  ]

  return (
    <div className="p-8">
      <div className="flex items-baseline justify-between">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <span className="text-xs text-faint">{NOW}</span>
      </div>

      <div className="mt-6 space-y-4">
        {/* row 1 — objective progress + changed this week */}
        <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
          <SectionCard
            title="Objective progress"
            right={
              <span className="mono text-[11px] text-faint">
                {data.objectives.length} active
              </span>
            }
          >
            <ul className="space-y-2">
              {data.objectives.map((o) => (
                <li
                  key={o.id}
                  className="rounded-lg border border-hairline bg-raised p-3"
                >
                  <div className="flex items-center gap-2">
                    <span className="mono rounded bg-aqua/[0.12] px-1.5 py-0.5 text-[11px] text-aqua">
                      P{o.priority}
                    </span>
                    <span className="text-[13px] font-medium">{o.title}</span>
                    <span className="rounded bg-hairline/60 px-1.5 py-0.5 text-[10px] text-faint">
                      {o.horizon}
                    </span>
                    <span className="mono ml-auto text-lg font-semibold tracking-tight text-text">
                      {o.pct_done}%
                    </span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded bg-hairline">
                    <div
                      className="h-full rounded bg-aqua"
                      style={{ width: `${o.pct_done}%` }}
                    />
                  </div>
                  <div className="mt-1.5 text-[11px] text-muted-fg">
                    {o.total_actions - o.open_actions} / {o.total_actions} actions done
                  </div>
                </li>
              ))}
              {data.objectives.length === 0 && (
                <li className="text-sm text-faint">No active objectives.</li>
              )}
            </ul>
          </SectionCard>

          <SectionCard
            title="Changed this week"
            right={
              <span className="mono text-[11px] text-faint">
                {data.changed_this_week.length}
              </span>
            }
          >
            <ul className="space-y-0">
              {data.changed_this_week.map((c, i) => (
                <li key={i} className="relative flex gap-3 pb-3.5 pl-4 last:pb-0">
                  {i < data.changed_this_week.length - 1 && (
                    <span className="absolute top-2 left-[3px] h-full w-px bg-hairline" />
                  )}
                  <span
                    className="absolute top-1 left-0 h-[7px] w-[7px] shrink-0 rounded-full"
                    style={{ backgroundColor: KIND_COLOR[c.kind] }}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <span className="truncate text-[13px] font-medium">{c.title}</span>
                      <span
                        className="shrink-0 text-[10px] font-semibold tracking-[0.06em] uppercase"
                        style={{ color: KIND_COLOR[c.kind] }}
                      >
                        {c.kind}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-baseline gap-2 text-[11px] text-muted-fg">
                      <span className="truncate">{c.detail}</span>
                      <span className="mono shrink-0 text-faint">{relativeTime(c.at)}</span>
                    </div>
                  </div>
                </li>
              ))}
              {data.changed_this_week.length === 0 && (
                <li className="text-sm text-faint">Nothing yet this week.</li>
              )}
            </ul>
          </SectionCard>
        </div>

        {/* row 2 — graph + focus/momentum/usage */}
        <div className="grid gap-4 lg:grid-cols-[1.55fr_1fr]">
          <GraphPanel height={460} />

          <div className="flex flex-col gap-4">
            <SectionCard
              title="Focus now"
              right={
                <span className="text-xs text-muted-fg">
                  {focus?.stale && focus.content_md && (
                    <span className="mr-2 text-warn">stale</span>
                  )}
                  <button
                    onClick={refreshFocus}
                    disabled={refreshing}
                    className="text-aqua hover:text-aqua-hi disabled:opacity-40"
                  >
                    {refreshing ? 'thinking…' : 'refresh'}
                  </button>
                </span>
              }
            >
              <div className="text-[13px] text-muted-fg">
                {focus?.content_md ? (
                  <Markdownish text={focus.content_md} />
                ) : (
                  'No focus note yet — hit refresh.'
                )}
              </div>
              {focusError && (
                <p className="mt-2 text-xs text-destructive">{focusError}</p>
              )}
            </SectionCard>

            <SectionCard title="Momentum">
              <div className="grid grid-cols-2 gap-2.5">
                {tiles.map((t) => (
                  <div
                    key={t.label}
                    className="rounded-lg border border-hairline bg-raised p-3"
                  >
                    <div className="mono text-2xl font-semibold tracking-tight">
                      {t.value}
                    </div>
                    <div className="mt-0.5 text-[11px] text-muted-fg">{t.label}</div>
                  </div>
                ))}
              </div>
            </SectionCard>

            <UsageCard />
            <ReflectionTeaser />
          </div>
        </div>
      </div>
    </div>
  )
}
