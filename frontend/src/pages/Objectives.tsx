import { useCallback, useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { api } from '@/lib/api'

type Horizon = 'month' | 'quarter' | 'year' | 'someday'
type ObjStatus = 'active' | 'done' | 'paused' | 'dropped'
type ActionStatus = 'todo' | 'doing' | 'done' | 'dropped'

const HORIZONS: Horizon[] = ['month', 'quarter', 'year', 'someday']
const OBJ_STATUSES: ObjStatus[] = ['active', 'done', 'paused', 'dropped']
const ACTION_STATUSES: ActionStatus[] = ['todo', 'doing', 'done', 'dropped']

interface Objective {
  id: string
  title: string
  description: string
  horizon: Horizon
  status: ObjStatus
  priority: number
  tags: string[]
  project_id: string | null
  target_date: string | null
}

interface Action {
  id: string
  objective_id: string
  title: string
  status: ActionStatus
  due_date: string | null
  source: string
}

interface ProjectLite {
  id: string
  name: string
}

const EMPTY = {
  title: '',
  horizon: 'quarter' as Horizon,
  priority: 2,
  tags: '',
  target_date: '',
  project_id: '',
}

const NO_PROJECT = '__none__'

export default function Objectives() {
  const [objectives, setObjectives] = useState<Objective[]>([])
  const [projects, setProjects] = useState<ProjectLite[]>([])
  const [form, setForm] = useState(EMPTY)
  const [open, setOpen] = useState<string | null>(null)

  const load = useCallback(async () => {
    const [o, p] = await Promise.all([
      api.get<Objective[]>('/objectives'),
      api.get<ProjectLite[]>('/projects'),
    ])
    setObjectives(o.data)
    setProjects(p.data)
  }, [])

  useEffect(() => {
    load().catch(() => undefined)
  }, [load])

  async function create(e: React.FormEvent) {
    e.preventDefault()
    if (!form.title.trim()) return
    await api.post('/objectives', {
      title: form.title,
      horizon: form.horizon,
      priority: Number(form.priority),
      tags: form.tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      target_date: form.target_date || null,
      project_id: form.project_id || null,
    })
    setForm(EMPTY)
    await load()
  }

  async function setStatus(id: string, status: ObjStatus) {
    await api.patch(`/objectives/${id}`, { status })
    await load()
  }

  return (
    <div className="p-8">
      <h1 className="text-xl font-semibold">Objectives</h1>
      <p className="mt-1 text-sm text-muted-fg">
        Objectives with a horizon, plus their actions. Tag with{' '}
        <code className="mono text-faint">skill</code> or{' '}
        <code className="mono text-faint">learning</code> for growth goals.
      </p>

      <div className="mt-6 max-w-3xl space-y-6">
        <form
          onSubmit={create}
          className="space-y-2 rounded-xl border border-hairline bg-surface p-3.5"
        >
          <Input
            placeholder="title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <div className="flex flex-wrap gap-2">
            <Select
              value={form.horizon}
              onValueChange={(v) => setForm({ ...form, horizon: v as Horizon })}
            >
              <SelectTrigger className="h-8 w-[120px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HORIZONS.map((h) => (
                  <SelectItem key={h} value={h}>
                    {h}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={String(form.priority)}
              onValueChange={(v) => setForm({ ...form, priority: Number(v) })}
            >
              <SelectTrigger className="h-8 w-[80px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">P1</SelectItem>
                <SelectItem value="2">P2</SelectItem>
                <SelectItem value="3">P3</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder="tags (comma separated)"
              value={form.tags}
              onChange={(e) => setForm({ ...form, tags: e.target.value })}
              className="flex-1"
            />
          </div>
          <div className="flex gap-2">
            <Input
              type="date"
              value={form.target_date}
              onChange={(e) => setForm({ ...form, target_date: e.target.value })}
              className="w-[160px]"
            />
            <Select
              value={form.project_id || NO_PROJECT}
              onValueChange={(v) =>
                setForm({ ...form, project_id: v === NO_PROJECT ? '' : v })
              }
            >
              <SelectTrigger className="h-8 flex-1 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_PROJECT}>(no project)</SelectItem>
                {projects.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit">Add objective</Button>
        </form>

        <ul className="space-y-2">
          {objectives.map((o) => (
            <li key={o.id} className="rounded-xl border border-hairline bg-surface">
              <div className="flex items-center gap-2 px-3.5 py-3 text-sm">
                <span className="mono rounded bg-raised px-1.5 py-0.5 text-[11px] text-aqua">
                  P{o.priority}
                </span>
                <button
                  onClick={() => setOpen(open === o.id ? null : o.id)}
                  className="font-medium hover:text-aqua"
                >
                  {o.title}
                </button>
                <span className="text-xs text-faint">{o.horizon}</span>
                {o.tags.map((t) => (
                  <Badge key={t} variant="secondary" className="text-[11px] font-normal">
                    {t}
                  </Badge>
                ))}
                <div className="ml-auto">
                  <Select
                    value={o.status}
                    onValueChange={(v) => setStatus(o.id, v as ObjStatus)}
                  >
                    <SelectTrigger className="h-7 w-[100px] text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {OBJ_STATUSES.map((s) => (
                        <SelectItem key={s} value={s}>
                          {s}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {open === o.id && <ActionList objectiveId={o.id} />}
            </li>
          ))}
          {objectives.length === 0 && (
            <p className="text-sm text-faint">No objectives yet.</p>
          )}
        </ul>
      </div>
    </div>
  )
}

function ActionList({ objectiveId }: { objectiveId: string }) {
  const [actions, setActions] = useState<Action[]>([])
  const [title, setTitle] = useState('')

  const load = useCallback(async () => {
    const { data } = await api.get<{ actions: Action[] }>(`/objectives/${objectiveId}`)
    setActions(data.actions)
  }, [objectiveId])

  useEffect(() => {
    load().catch(() => undefined)
  }, [load])

  async function add(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    await api.post(`/objectives/${objectiveId}/actions`, { title })
    setTitle('')
    await load()
  }

  async function setStatus(id: string, status: ActionStatus) {
    await api.patch(`/actions/${id}`, { status })
    await load()
  }

  return (
    <div className="space-y-2 border-t border-hairline p-3.5 text-sm">
      {actions.map((a) => (
        <div key={a.id} className="flex items-center gap-2">
          <Select
            value={a.status}
            onValueChange={(v) => setStatus(a.id, v as ActionStatus)}
          >
            <SelectTrigger className="h-7 w-[90px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ACTION_STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className={a.status === 'done' ? 'text-faint line-through' : ''}>
            {a.title}
          </span>
          {a.source === 'suggested' && (
            <span className="text-xs text-warn">suggested</span>
          )}
          {a.due_date && <span className="text-xs text-faint">due {a.due_date}</span>}
        </div>
      ))}
      <form onSubmit={add} className="flex gap-2">
        <Input
          placeholder="new action"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="flex-1"
        />
        <Button type="submit" variant="outline" size="sm">
          Add
        </Button>
      </form>
    </div>
  )
}
