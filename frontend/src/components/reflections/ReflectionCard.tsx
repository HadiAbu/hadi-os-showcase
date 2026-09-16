import { Link } from 'react-router-dom'
import { KIND_COLOR, type Reflection, type ReflectionStatus } from '@/lib/reflections'
import { cn } from '@/lib/utils'

export function ReflectionCard({
  reflection,
  onStatus,
}: {
  reflection: Reflection
  onStatus: (id: string, status: ReflectionStatus) => void
}) {
  const { id, kind, body, evidence, status } = reflection
  const objectiveIds = evidence.objective_ids ?? []
  const entryIds = evidence.journal_entry_ids ?? []
  const terms = evidence.terms ?? []

  return (
    <div
      className="rounded-xl border border-hairline bg-surface p-3.5"
      style={{ borderLeft: `3px solid ${KIND_COLOR[kind]}` }}
    >
      <div className="flex items-start gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">
          {kind}
        </span>
        <div className="ml-auto flex gap-2 text-xs">
          <button
            onClick={() => onStatus(id, status === 'pinned' ? 'active' : 'pinned')}
            className={cn(
              'transition-colors',
              status === 'pinned' ? 'text-aqua' : 'text-faint hover:text-muted-fg',
            )}
          >
            {status === 'pinned' ? 'pinned' : 'pin'}
          </button>
          <button
            onClick={() => onStatus(id, 'dismissed')}
            className="text-faint hover:text-destructive"
          >
            dismiss
          </button>
        </div>
      </div>

      <p className="mt-1.5 text-sm text-text">{body}</p>

      {(objectiveIds.length > 0 || entryIds.length > 0 || terms.length > 0) && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {objectiveIds.map((oid) => (
            <Link
              key={oid}
              to="/objectives"
              className="rounded border border-hairline px-1.5 py-0.5 text-[11px] text-muted-fg hover:text-aqua"
            >
              objective
            </Link>
          ))}
          {entryIds.map((eid) => (
            <Link
              key={eid}
              to="/journal"
              className="rounded border border-hairline px-1.5 py-0.5 text-[11px] text-muted-fg hover:text-aqua"
            >
              note
            </Link>
          ))}
          {terms.slice(0, 6).map((t) => (
            <span
              key={t}
              className="mono rounded border border-hairline px-1.5 py-0.5 text-[11px] text-faint"
            >
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
