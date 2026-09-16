import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import {
  fetchGraph,
  NODE_COLOR,
  NODE_LABEL,
  NODE_ROUTE,
  NODE_TYPES,
  type GraphData,
  type GraphNode,
} from '@/lib/graph'
import { useReducedMotion } from '@/lib/useReducedMotion'
import { GraphCanvasLazy } from './GraphCanvasLazy'
import { GraphModeToggle } from './GraphModeToggle'

export function GraphLegend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-fg">
      {NODE_TYPES.map((t) => (
        <span key={t} className="inline-flex items-center gap-1.5">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: NODE_COLOR[t] }}
          />
          {NODE_LABEL[t]}
        </span>
      ))}
    </div>
  )
}

export function GraphPanel({ height = 420 }: { height?: number }) {
  const [data, setData] = useState<GraphData | null>(null)
  const [error, setError] = useState(false)
  const [mode, setMode] = useState<'2d' | '3d'>('2d')
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const reducedMotion = useReducedMotion()

  const load = useCallback(async () => {
    setError(false)
    try {
      setData(await fetchGraph())
    } catch {
      setError(true)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const isEmpty = data !== null && data.nodes.length === 0

  return (
    <section className="flex flex-col rounded-xl border border-hairline bg-surface">
      <header className="flex items-center gap-3 border-b border-hairline px-4 py-3">
        <h2 className="text-sm font-semibold">Knowledge graph</h2>
        {data?.truncated && (
          <span className="text-xs text-warn">showing 250 of many</span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {!reducedMotion && <GraphModeToggle mode={mode} onChange={setMode} />}
          <Button variant="outline" size="sm" onClick={load}>
            Rescan
          </Button>
          <Link
            to="/graph"
            className="text-xs text-aqua hover:text-aqua-hi"
          >
            Fullscreen ↗
          </Link>
        </div>
      </header>

      <div className="relative min-h-0 flex-1">
        {error ? (
          <div className="grid place-items-center p-8 text-sm text-destructive" style={{ height }}>
            Couldn't load the graph. <button onClick={load} className="ml-1 underline">Retry</button>
          </div>
        ) : isEmpty ? (
          <div
            className="grid place-items-center p-8 text-center text-sm text-faint"
            style={{ height }}
          >
            Nothing connected yet — add objectives, projects and context, or chat
            with hadi-os, and the map fills in.
          </div>
        ) : data ? (
          <GraphCanvasLazy
            data={data}
            mode={mode}
            height={height}
            onNodeClick={setSelected}
          />
        ) : (
          <div className="grid place-items-center text-sm text-faint" style={{ height }}>
            Loading graph…
          </div>
        )}

        {selected && (
          <div className="absolute bottom-3 left-3 max-w-xs rounded-lg border border-hairline bg-raised p-3 text-sm shadow-lg">
            <div className="flex items-start gap-2">
              <span
                className="mt-1 h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: NODE_COLOR[selected.type] }}
              />
              <div className="min-w-0">
                <div className="font-medium">{selected.label}</div>
                <div className="text-xs text-faint">{selected.type}</div>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="ml-auto text-faint hover:text-text"
              >
                ✕
              </button>
            </div>
            <Link
              to={NODE_ROUTE[selected.type]}
              className="mt-2 inline-block text-xs text-aqua hover:text-aqua-hi"
            >
              Open {selected.type === 'conversation' ? 'chat' : selected.type} screen →
            </Link>
          </div>
        )}
      </div>

      <footer className="border-t border-hairline px-4 py-3">
        <GraphLegend />
      </footer>
    </section>
  )
}
