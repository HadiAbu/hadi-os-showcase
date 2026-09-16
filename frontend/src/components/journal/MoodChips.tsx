import { MOODS, type Mood } from '@/lib/journal'
import { cn } from '@/lib/utils'

export function MoodChips({
  value,
  onChange,
}: {
  value: Mood
  onChange: (m: Mood) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {MOODS.map((m) => {
        const on = value === m
        return (
          <button
            key={m}
            type="button"
            onClick={() => onChange(on ? '' : m)}
            className={cn(
              'rounded-full border px-2.5 py-1 text-xs capitalize transition-colors',
              on
                ? 'border-aqua bg-aqua text-ink'
                : 'border-hairline text-muted-fg hover:text-text',
            )}
          >
            {m}
          </button>
        )
      })}
    </div>
  )
}
