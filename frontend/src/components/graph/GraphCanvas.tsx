import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
} from 'd3-force'
import ForceGraph2D from 'react-force-graph-2d'
import { NODE_COLOR, type GraphData, type GraphNode } from '@/lib/graph'
import { useReducedMotion } from '@/lib/useReducedMotion'

const GraphCanvas3D = lazy(() => import('./GraphCanvas3D'))

export interface GraphCanvasProps {
  data: GraphData
  mode: '2d' | '3d'
  height: number
  onNodeClick?: (node: GraphNode) => void
  /** When non-empty, matching nodes are lit and the rest are dimmed. */
  highlightIds?: Set<string>
}

const VOID = '#0a0f14'
const LINK_COLOR = 'rgba(79, 248, 210, 0.18)'
const LABEL_COLOR = '#e8f0ef'

type SimNode = GraphNode & { x?: number; y?: number; fx?: number; fy?: number }

function useMeasuredWidth(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null)
  const [width, setWidth] = useState(600)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const w = Math.floor(entry.contentRect.width)
      if (w > 0) setWidth(w)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width]
}

/** Run d3-force to convergence once and pin every node — a still layout for
 *  `prefers-reduced-motion`. */
function staticLayout(data: GraphData): { nodes: SimNode[]; links: GraphData['links'] } {
  const nodes: SimNode[] = data.nodes.map((n) => ({ ...n }))
  const simLinks = data.links.map((l) => ({ source: l.source, target: l.target }))
  // d3-force mutates its inputs; run it on the clones above, then read x/y back.
  /* eslint-disable @typescript-eslint/no-explicit-any */
  forceSimulation(nodes as any[])
    .force(
      'link',
      forceLink(simLinks as any[])
        .id((d: any) => d.id)
        .distance(40),
    )
    .force('charge', forceManyBody().strength(-140))
    .force('center', forceCenter(0, 0))
    .force('collide', forceCollide(14))
    .stop()
    .tick(300)
  /* eslint-enable @typescript-eslint/no-explicit-any */
  for (const n of nodes) {
    n.fx = n.x
    n.fy = n.y
  }
  return { nodes, links: data.links.map((l) => ({ ...l })) }
}

export default function GraphCanvas({
  data,
  mode,
  height,
  onNodeClick,
  highlightIds,
}: GraphCanvasProps) {
  const [ref, width] = useMeasuredWidth()
  const reducedMotion = useReducedMotion()
  const isStatic = reducedMotion
  const effectiveMode = reducedMotion ? '2d' : mode

  const graphData = useMemo(
    () =>
      isStatic
        ? staticLayout(data)
        : { nodes: data.nodes.map((n) => ({ ...n })), links: data.links.map((l) => ({ ...l })) },
    [data, isStatic],
  )

  const dimActive = !!highlightIds && highlightIds.size > 0
  const isLit = (id: string) => !dimActive || highlightIds!.has(id)

  const paintNode = (node: SimNode, ctx: CanvasRenderingContext2D, scale: number) => {
    const lit = isLit(node.id)
    const r = 4
    ctx.globalAlpha = lit ? 1 : 0.12
    ctx.beginPath()
    ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI)
    ctx.fillStyle = NODE_COLOR[node.type]
    ctx.fill()
    if (lit && (scale > 1.4 || dimActive)) {
      ctx.font = `${11 / scale}px 'Hanken Grotesk', system-ui, sans-serif`
      ctx.fillStyle = LABEL_COLOR
      ctx.textAlign = 'center'
      ctx.fillText(node.label.slice(0, 28), node.x ?? 0, (node.y ?? 0) + r + 9 / scale)
    }
    ctx.globalAlpha = 1
  }

  const common = {
    graphData,
    width,
    height,
    backgroundColor: VOID,
    nodeLabel: (n: object) => (n as GraphNode).label,
    nodeColor: (n: object) => NODE_COLOR[(n as GraphNode).type],
    linkColor: () => LINK_COLOR,
    onNodeClick: (n: object) => onNodeClick?.(n as GraphNode),
    cooldownTicks: isStatic ? 0 : 120,
  }

  return (
    <div ref={ref} className="w-full" style={{ height }}>
      {effectiveMode === '3d' ? (
        <Suspense
          fallback={
            <div className="grid h-full place-items-center text-sm text-faint">
              Loading 3D…
            </div>
          }
        >
          <GraphCanvas3D {...common} enableNodeDrag={!isStatic} />
        </Suspense>
      ) : (
        <ForceGraph2D
          {...common}
          nodeRelSize={4}
          enableNodeDrag={!isStatic}
          nodeCanvasObjectMode={() => 'replace'}
          nodeCanvasObject={paintNode as never}
          linkWidth={(l: object) => {
            const link = l as { source: SimNode | string; target: SimNode | string }
            if (!dimActive) return 1
            const s = typeof link.source === 'string' ? link.source : link.source.id
            const t = typeof link.target === 'string' ? link.target : link.target.id
            return isLit(s) && isLit(t) ? 1.5 : 0.4
          }}
        />
      )}
    </div>
  )
}
