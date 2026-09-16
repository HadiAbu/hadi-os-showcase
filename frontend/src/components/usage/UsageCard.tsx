import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Sparkline } from '@/components/charts/Sparkline'
import { compactTokens, costLabel, fetchUsage, type Usage } from '@/lib/usage'
import { NODE_COLOR } from '@/lib/graph'

export function UsageCard() {
  const [data, setData] = useState<Usage | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetchUsage('7d')
      .then(setData)
      .catch(() => setError(true))
  }, [])

  return (
    <section className="rounded-xl border border-hairline bg-surface p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-fg">
          Usage · this week
        </h2>
        <Link to="/usage" className="text-xs text-aqua hover:text-aqua-hi">
          Details ↗
        </Link>
      </div>

      {error ? (
        <p className="mt-3 text-sm text-faint">Couldn't load usage.</p>
      ) : !data ? (
        <p className="mt-3 text-sm text-faint">Loading…</p>
      ) : (
        <>
          <div className="mt-3 flex items-end gap-3">
            <div className="mono text-2xl font-semibold tracking-tight">
              {compactTokens(data.tokens.total)}
              <span className="ml-1 text-xs text-muted-fg">tok</span>
            </div>
            <Sparkline
              values={data.by_day.map((d) => d.total)}
              className="mb-1"
            />
            <span className="mono mb-1 ml-auto text-[11px] text-muted-fg">
              {costLabel(data)}
            </span>
          </div>

          <div className="mt-3 space-y-1.5">
            {data.by_model.slice(0, 3).map((m, i) => (
              <div key={m.model}>
                <div className="flex justify-between text-[11px] text-muted-fg">
                  <span className="mono truncate">{m.model}</span>
                  <span className="mono">{m.pct}%</span>
                </div>
                <div className="mt-0.5 h-1 overflow-hidden rounded bg-hairline">
                  <div
                    className="h-full rounded"
                    style={{
                      width: `${m.pct}%`,
                      background: i === 0 ? 'var(--aqua)' : NODE_COLOR.project,
                    }}
                  />
                </div>
              </div>
            ))}
            <p className="pt-1 text-[10px] text-faint">
              {data.tool_calls_total} tool calls · {data.by_conversation.length} conversations
            </p>
          </div>
        </>
      )}
    </section>
  )
}
