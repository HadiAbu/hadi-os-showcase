import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchReflections, type Reflection } from '@/lib/reflections'

export function ReflectionTeaser() {
  const [latest, setLatest] = useState<Reflection | null | undefined>(undefined)

  useEffect(() => {
    fetchReflections()
      .then((rows) => setLatest(rows[0] ?? null))
      .catch(() => setLatest(null))
  }, [])

  if (latest === undefined) return null

  return (
    <Link
      to="/reflections"
      className="block rounded-xl border border-hairline bg-surface px-4 py-3 text-sm text-muted-fg transition-colors hover:text-text"
    >
      {latest ? (
        <span className="line-clamp-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">
            {latest.kind}
          </span>{' '}
          {latest.body} <span className="text-aqua">→</span>
        </span>
      ) : (
        <span className="text-faint">No reflections yet →</span>
      )}
    </Link>
  )
}
