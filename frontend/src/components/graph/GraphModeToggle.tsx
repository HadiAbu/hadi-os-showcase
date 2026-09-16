import { cn } from '@/lib/utils'

export function GraphModeToggle({
  mode,
  onChange,
}: {
  mode: '2d' | '3d'
  onChange: (m: '2d' | '3d') => void
}) {
  return (
    <div className="inline-flex overflow-hidden rounded-md border border-hairline text-xs">
      {(['2d', '3d'] as const).map((m) => (
        <button
          key={m}
          onClick={() => onChange(m)}
          className={cn(
            'px-2 py-1 uppercase',
            mode === m ? 'bg-aqua text-ink' : 'text-muted-fg hover:text-text',
          )}
        >
          {m}
        </button>
      ))}
    </div>
  )
}
