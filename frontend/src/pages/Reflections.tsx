import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { ReflectionCard } from '@/components/reflections/ReflectionCard'
import {
  fetchReflections,
  generateReflections,
  patchReflection,
  type Reflection,
  type ReflectionStatus,
} from '@/lib/reflections'

function groupByDay(rows: Reflection[]): [string, Reflection[]][] {
  const map = new Map<string, Reflection[]>()
  for (const r of rows) {
    const day = r.created_at.slice(0, 10)
    const bucket = map.get(day)
    if (bucket) bucket.push(r)
    else map.set(day, [r])
  }
  return [...map.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1))
}

export default function Reflections() {
  const [rows, setRows] = useState<Reflection[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [reason, setReason] = useState<string | null>(null)
  const [error, setError] = useState(false)

  const load = useCallback(async () => {
    setError(false)
    try {
      setRows(await fetchReflections())
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function onGenerate() {
    setGenerating(true)
    setReason(null)
    try {
      const out = await generateReflections()
      setReason(out.reason)
      if (out.reflections.length) await load()
    } catch {
      setError(true)
    } finally {
      setGenerating(false)
    }
  }

  async function onStatus(id: string, status: ReflectionStatus) {
    const updated = await patchReflection(id, status)
    setRows((prev) =>
      status === 'dismissed'
        ? prev.filter((r) => r.id !== id)
        : prev.map((r) => (r.id === id ? updated : r)),
    )
  }

  const groups = groupByDay(rows)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Reflections</h1>
          <p className="mt-1 text-sm text-muted-fg">
            Observations from your journal and objective progress. Generate when you
            want a fresh read.
          </p>
        </div>
        <Button onClick={onGenerate} disabled={generating}>
          {generating ? 'thinking…' : 'Generate'}
        </Button>
      </div>

      <div className="mt-6 max-w-3xl space-y-6">
        {reason && <p className="text-sm text-faint">{reason}</p>}
        {error && (
          <p className="text-sm text-destructive">
            Couldn't load reflections.{' '}
            <button onClick={load} className="underline">
              Retry
            </button>
          </p>
        )}
        {!loading && !error && rows.length === 0 && !reason && (
          <p className="text-sm text-faint">
            No reflections yet — hit Generate.
          </p>
        )}

        {groups.map(([day, items]) => (
          <div key={day}>
            <h2 className="mono text-[11px] uppercase tracking-[0.08em] text-faint">
              {day}
            </h2>
            <div className="mt-2 space-y-2">
              {items.map((r) => (
                <ReflectionCard key={r.id} reflection={r} onStatus={onStatus} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
