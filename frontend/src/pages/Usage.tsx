import { useCallback, useEffect, useState } from 'react'
import { BarChart } from '@/components/charts/BarChart'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  compactTokens,
  costLabel,
  fetchUsage,
  type Usage,
  type UsageWindow,
} from '@/lib/usage'

const WINDOWS: { value: UsageWindow; label: string }[] = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: 'all', label: 'All time' },
]

function Card({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-xl border border-hairline bg-surface p-4">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-fg">
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

export default function Usage() {
  const [window, setWindow] = useState<UsageWindow>('7d')
  const [data, setData] = useState<Usage | null>(null)
  const [error, setError] = useState(false)

  const load = useCallback(async (w: UsageWindow) => {
    setError(false)
    try {
      setData(await fetchUsage(w))
    } catch {
      setError(true)
    }
  }, [])

  useEffect(() => {
    load(window)
  }, [load, window])

  return (
    <div className="p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Usage</h1>
        <Tabs value={window} onValueChange={(v) => setWindow(v as UsageWindow)}>
          <TabsList>
            {WINDOWS.map((w) => (
              <TabsTrigger key={w.value} value={w.value}>
                {w.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {error ? (
        <p className="mt-6 text-sm text-destructive">
          Couldn't load usage.{' '}
          <button onClick={() => load(window)} className="underline">
            Retry
          </button>
        </p>
      ) : !data ? (
        <p className="mt-6 text-sm text-faint">Loading…</p>
      ) : (
        <div className="mt-6 max-w-4xl space-y-5">
          {/* headline */}
          <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2">
            <div>
              <div className="mono text-4xl font-semibold tracking-tight">
                {compactTokens(data.tokens.total)}
                <span className="ml-1 text-base text-muted-fg">tokens</span>
              </div>
              <div className="mt-1 text-xs text-faint">
                {compactTokens(data.tokens.prompt)} in ·{' '}
                {compactTokens(data.tokens.completion)} out
              </div>
            </div>
            <div>
              <div className="mono text-2xl font-semibold">{costLabel(data)}</div>
              <div className="mt-1 text-xs text-faint">
                {data.tool_calls_total} tool calls · {data.by_conversation.length} conversations
              </div>
            </div>
          </div>

          <Card title={`Tokens per day · ${window}`}>
            <BarChart
              data={data.by_day.map((d) => ({ label: d.day, value: d.total }))}
            />
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="By model">
              {data.by_model.length === 0 ? (
                <p className="text-sm text-faint">No model activity.</p>
              ) : (
                <ul className="space-y-3">
                  {data.by_model.map((m) => (
                    <li key={m.model}>
                      <div className="flex justify-between text-xs text-muted-fg">
                        <span className="mono truncate">{m.model}</span>
                        <span className="mono">{m.pct}%</span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded bg-hairline">
                        <div
                          className="h-full rounded bg-aqua"
                          style={{ width: `${m.pct}%` }}
                        />
                      </div>
                      <div className="mt-0.5 text-[10px] text-faint">
                        {compactTokens(m.total)} tokens
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card title="Tool calls">
              {data.tool_calls_by_name.length === 0 ? (
                <p className="text-sm text-faint">No tool calls in this window.</p>
              ) : (
                <ul className="space-y-1.5 text-sm">
                  {data.tool_calls_by_name.map((t) => (
                    <li key={t.tool_name} className="flex justify-between">
                      <span className="mono text-muted-fg">{t.tool_name}</span>
                      <span className="mono">{t.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <Card title="Top conversations">
            {data.by_conversation.length === 0 ? (
              <p className="text-sm text-faint">No conversations in this window.</p>
            ) : (
              <ul className="space-y-1.5 text-sm">
                {data.by_conversation.map((c) => (
                  <li key={c.conversation_id} className="flex justify-between gap-4">
                    <span className="truncate">{c.title || 'Untitled'}</span>
                    <span className="mono shrink-0 text-muted-fg">
                      {compactTokens(c.total)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
