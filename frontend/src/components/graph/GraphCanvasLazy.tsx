import { Component, lazy, Suspense, useMemo, useState, type ReactNode } from 'react'
import type { GraphCanvasProps } from './GraphCanvas'

// Code-split: react-force-graph + three are only pulled when a graph renders.
// A transient chunk-load failure would otherwise be cached forever by lazy(),
// so retry the import a few times and, if it still fails, surface a recoverable
// error instead of crashing the page.
function importCanvas(attempts = 3, delayMs = 400): Promise<typeof import('./GraphCanvas')> {
  return import('./GraphCanvas').catch((err) => {
    if (attempts <= 1) throw err
    return new Promise<void>((r) => setTimeout(r, delayMs)).then(() =>
      importCanvas(attempts - 1, delayMs * 2),
    )
  })
}

class CanvasBoundary extends Component<
  { height: number; onReset: () => void; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div
        className="grid place-items-center text-sm text-destructive"
        style={{ height: this.props.height }}
      >
        The graph view failed to load.
        <button
          className="ml-1 underline"
          onClick={() => {
            this.setState({ failed: false })
            this.props.onReset()
          }}
        >
          Reload
        </button>
      </div>
    )
  }
}

export function GraphCanvasLazy(props: GraphCanvasProps) {
  const [attempt, setAttempt] = useState(0)
  // a fresh lazy() per attempt so "Reload" actually re-runs the import
  const GraphCanvas = useMemo(
    () => lazy(() => importCanvas()),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [attempt],
  )

  return (
    <CanvasBoundary height={props.height} onReset={() => setAttempt((a) => a + 1)}>
      <Suspense
        fallback={
          <div
            className="grid place-items-center text-sm text-faint"
            style={{ height: props.height }}
          >
            Loading graph…
          </div>
        }
      >
        <GraphCanvas {...props} />
      </Suspense>
    </CanvasBoundary>
  )
}
