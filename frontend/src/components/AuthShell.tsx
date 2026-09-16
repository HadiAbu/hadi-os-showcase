export function AuthShell({
  title,
  children,
  footer,
}: {
  title: string
  children: React.ReactNode
  footer: React.ReactNode
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-6 text-text">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2.5">
          <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden>
            <rect width="32" height="32" rx="7" fill="var(--aqua)" />
            <path
              d="M11 8v16M11 16h10M21 14v10"
              stroke="var(--aqua-ink)"
              strokeWidth="2.6"
              strokeLinecap="round"
              fill="none"
            />
          </svg>
          <span className="text-lg font-bold tracking-[0.01em]">hadi-os</span>
        </div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {children}
        <p className="mt-5 text-sm text-muted-fg">{footer}</p>
      </div>
    </div>
  )
}
