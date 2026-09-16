import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Input } from '@/components/ui/input'
import { GraphCanvasLazy } from '@/components/graph/GraphCanvasLazy'
import { GraphLegend } from '@/components/graph/GraphPanel'
import { GraphModeToggle } from '@/components/graph/GraphModeToggle'
import {
  fetchGraph,
  NODE_COLOR,
  NODE_LABEL,
  NODE_ROUTE,
  NODE_TYPES,
  type EntityType,
  type GraphData,
  type GraphNode,
} from '@/lib/graph'
import { useReducedMotion } from '@/lib/useReducedMotion'
import { cn } from '@/lib/utils'

export default function Graph() {
  const [data, setData] = useState<GraphData | null>(null)
  const [error, setError] = useState(false)
  const [mode, setMode] = useState<'2d' | '3d'>('2d')
  const [hidden, setHidden] = useState<Set<EntityType>>(new Set())
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const reducedMotion = useReducedMotion()

  const bodyRef = useRef<HTMLDivElement | null>(null)
  const [bodyHeight, setBodyHeight] = useState(600)

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

  useEffect(() => {
    const el = bodyRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const h = Math.floor(entry.contentRect.height)
      if (h > 0) setBodyHeight(h)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const filtered = useMemo<GraphData | null>(() => {
    if (!data) return null
    if (hidden.size === 0) return data
    const nodes = data.nodes.filter((n) => !hidden.has(n.type))
    const keep = new Set(nodes.map((n) => n.id))
    return {
      nodes,
      links: data.links.filter((l) => keep.has(l.source) && keep.has(l.target)),
      truncated: data.truncated,
    }
  }, [data, hidden])

  const highlightIds = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q || !filtered) return undefined
    return new Set(
      filtered.nodes.filter((n) => n.label.toLowerCase().includes(q)).map((n) => n.id),
    )
  }, [query, filtered])

  function toggle(type: EntityType) {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  return (
    <div className="flex h-screen flex-col bg-bg text-text">
      <header className="flex flex-wrap items-center gap-3 border-b border-hairline px-6 py-3">
        <h1 className="text-lg font-semibold">Graph</h1>
        <div className="flex flex-wrap gap-1.5">
          {NODE_TYPES.map((t) => {
            const on = !hidden.has(t)
            return (
              <button
                key={t}
                onClick={() => toggle(t)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs',
                  on ? 'border-hairline text-text' : 'border-hairline text-faint opacity-50',
                )}
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: NODE_COLOR[t] }}
                />
                {NODE_LABEL[t]}
              </button>
            )
          })}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search nodes…"
            className="h-8 w-44 text-xs"
          />
          {!reducedMotion && <GraphModeToggle mode={mode} onChange={setMode} />}
        </div>
      </header>

      <div ref={bodyRef} className="relative min-h-0 flex-1">
        {error ? (
          <div className="grid h-full place-items-center text-sm text-destructive">
            Couldn't load the graph.{' '}
            <button onClick={load} className="ml-1 underline">
              Retry
            </button>
          </div>
        ) : filtered && filtered.nodes.length === 0 && data?.nodes.length === 0 ? (
          <div className="grid h-full place-items-center px-8 text-center text-sm text-faint">
            Nothing connected yet — add objectives, projects and context, or chat
            with hadi-os, and the map fills in.
          </div>
        ) : filtered ? (
          <GraphCanvasLazy
            data={filtered}
            mode={mode}
            height={bodyHeight}
            highlightIds={highlightIds}
            onNodeClick={setSelected}
          />
        ) : (
          <div className="grid h-full place-items-center text-sm text-faint">
            Loading graph…
          </div>
        )}

        {selected && (
          <div className="absolute bottom-4 left-4 max-w-xs rounded-lg border border-hairline bg-raised p-3 text-sm shadow-lg">
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

      <footer className="border-t border-hairline px-6 py-2.5">
        <GraphLegend />
      </footer>
    </div>
  )
}
