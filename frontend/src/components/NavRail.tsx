import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

const S = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

const ICONS: Record<string, React.ReactNode> = {
  chat: <path d="M2.5 4.5h11v7H6l-3 2.5v-2.5H2.5z" {...S} />,
  dashboard: <path d="M2.5 2.5h4.5v4.5H2.5zM9 2.5h4.5v3H9zM9 8h4.5v5.5H9zM2.5 9h4.5v4.5H2.5z" {...S} />,
  objectives: (
    <g {...S}>
      <circle cx="8" cy="8" r="5.5" />
      <circle cx="8" cy="8" r="2" />
    </g>
  ),
  projects: (
    <g {...S}>
      <path d="M2.6 5.4 8 2.8l5.4 2.6v5.2L8 13.2 2.6 10.6z" />
      <path d="M2.6 5.4 8 8l5.4-2.6M8 8v5.2" />
    </g>
  ),
  context: (
    <g {...S}>
      <circle cx="5" cy="6" r="1.7" />
      <circle cx="11.2" cy="4.8" r="1.7" />
      <circle cx="8" cy="11.4" r="1.7" />
      <path d="M6.4 6.9 7.1 9.9M9.6 6.1 8.7 9.8M6.6 5.7 9.6 5.1" />
    </g>
  ),
  graph: (
    <g {...S}>
      <circle cx="4" cy="8" r="1.9" />
      <circle cx="12" cy="4" r="1.9" />
      <circle cx="12" cy="12" r="1.9" />
      <path d="M5.7 7.1 10.3 4.9M5.7 8.9 10.3 11.1" />
    </g>
  ),
  usage: <path d="M1.8 9h2.6l1.8-4.6L9 12l1.6-3h3.6" {...S} />,
  journal: (
    <g {...S}>
      <path d="M4 2.5h7.5v11H4zM4 2.5a1.5 1.5 0 0 0-1.5 1.5v8A1.5 1.5 0 0 0 4 13.5" />
      <path d="M6.2 5.5h3.5M6.2 8h3.5" />
    </g>
  ),
  reflections: (
    <g {...S}>
      <path d="M8 1.8v2M8 12.2v2M2.3 8h2M11.7 8h2M4 4l1.4 1.4M10.6 10.6 12 12M12 4l-1.4 1.4M5.4 10.6 4 12" />
      <circle cx="8" cy="8" r="2.4" />
    </g>
  ),
  settings: (
    <g {...S}>
      <circle cx="8" cy="8" r="2.3" />
      <path d="M8 1.6v2.1M8 12.3v2.1M1.6 8h2.1M12.3 8h2.1M3.6 3.6 5 5M11 11l1.4 1.4M12.4 3.6 11 5M5 11l-1.4 1.4" />
    </g>
  ),
  signOut: (
    <g {...S}>
      <path d="M6.5 2.5h-3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h3" />
      <path d="M10.5 5.3 13.5 8l-3 2.7M13.5 8h-8" />
    </g>
  ),
}

const NAV = [
  { to: '/', label: 'Chat', icon: 'chat', end: true },
  { to: '/dashboard', label: 'Dashboard', icon: 'dashboard' },
  { to: '/journal', label: 'Journal', icon: 'journal' },
  { to: '/objectives', label: 'Objectives', icon: 'objectives' },
  { to: '/projects', label: 'Projects', icon: 'projects' },
  { to: '/context', label: 'Context', icon: 'context' },
  { to: '/graph', label: 'Graph', icon: 'graph' },
  { to: '/usage', label: 'Usage', icon: 'usage' },
  { to: '/reflections', label: 'Reflections', icon: 'reflections' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

export function NavRail() {
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={cn(
        'flex shrink-0 flex-col border-r border-hairline bg-rail transition-[width] duration-150',
        collapsed ? 'w-14 p-[18px_8px]' : 'w-[214px] p-[18px_14px]',
      )}
    >
      <div
        className={cn(
          'flex items-center pb-[22px] pt-0.5',
          collapsed ? 'justify-center' : 'justify-between gap-2.5 px-1.5',
        )}
      >
        <div className="flex items-center gap-2.5">
          <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
            <rect width="32" height="32" rx="7" fill="var(--aqua)" />
            <path
              d="M11 8v16M11 16h10M21 14v10"
              stroke="var(--aqua-ink)"
              strokeWidth="2.6"
              strokeLinecap="round"
              fill="none"
            />
          </svg>
          {!collapsed && <span className="font-bold tracking-[0.01em]">hadi-os</span>}
        </div>
        {!collapsed && (
          <button
            onClick={() => setCollapsed(true)}
            className="text-faint hover:text-muted-fg"
            aria-label="Collapse navigation"
          >
            ‹
          </button>
        )}
      </div>

      {collapsed && (
        <button
          onClick={() => setCollapsed(false)}
          className="mb-3 self-center text-faint hover:text-muted-fg"
          aria-label="Expand navigation"
        >
          ›
        </button>
      )}

      <nav className="flex flex-col gap-0.5">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            title={collapsed ? item.label : undefined}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-[11px] rounded-[9px] py-2 text-sm font-medium',
                collapsed ? 'justify-center px-0' : 'px-2.5',
                isActive
                  ? 'bg-aqua/[0.09] text-aqua shadow-[inset_2px_0_0_var(--aqua)]'
                  : 'text-muted-fg hover:bg-raised hover:text-text',
              )
            }
          >
            <svg width="16" height="16" viewBox="0 0 16 16" className="shrink-0" aria-hidden>
              {ICONS[item.icon]}
            </svg>
            {!collapsed && item.label}
          </NavLink>
        ))}
      </nav>

      <div className={cn('mt-auto flex flex-col gap-0.5', collapsed ? 'items-center' : 'px-2')}>
        {!collapsed && <div className="mono truncate text-[11px] text-faint">{user?.email}</div>}
        <button
          onClick={logout}
          title={collapsed ? 'Sign out' : undefined}
          className={cn(
            'text-muted-fg hover:text-text',
            collapsed ? 'flex items-center justify-center py-1' : 'w-fit text-xs',
          )}
        >
          {collapsed ? (
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
              {ICONS.signOut}
            </svg>
          ) : (
            'Sign out'
          )}
        </button>
      </div>
    </aside>
  )
}
