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
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'

type ProjectStatus = 'active' | 'paused' | 'shipped' | 'archived'
const STATUSES: ProjectStatus[] = ['active', 'paused', 'shipped', 'archived']

interface Project {
  id: string
  name: string
  summary: string
  status: ProjectStatus
  tech: string[]
  repo_path: string | null
  repo_url: string | null
  next_steps: string
  notes: string
}

const EMPTY = {
  name: '',
  summary: '',
  status: 'active' as ProjectStatus,
  tech: '',
  repo_path: '',
  repo_url: '',
  next_steps: '',
  notes: '',
}

function StatusSelect({
  value,
  onChange,
}: {
  value: ProjectStatus
  onChange: (v: ProjectStatus) => void
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as ProjectStatus)}>
      <SelectTrigger className="h-8 w-[130px] text-xs">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {STATUSES.map((s) => (
          <SelectItem key={s} value={s}>
            {s}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [form, setForm] = useState(EMPTY)
  const [open, setOpen] = useState<string | null>(null)

  const load = useCallback(async () => {
    const { data } = await api.get<Project[]>('/projects')
    setProjects(data)
  }, [])

  useEffect(() => {
    load().catch(() => undefined)
  }, [load])

  async function create(e: React.FormEvent) {
    e.preventDefault()
    if (!form.name.trim()) return
    await api.post('/projects', {
      ...form,
      tech: form.tech.split(',').map((t) => t.trim()).filter(Boolean),
    })
    setForm(EMPTY)
    await load()
  }

  return (
    <div className="p-8">
      <h1 className="text-xl font-semibold">Projects</h1>
      <p className="mt-1 text-sm text-muted-fg">
        Manual records for now. Read-only git activity arrives in Phase 3.
      </p>

      <div className="mt-6 max-w-3xl space-y-6">
        <form
          onSubmit={create}
          className="space-y-2 rounded-xl border border-hairline bg-surface p-3.5"
        >
          <div className="flex gap-2">
            <Input
              placeholder="name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="flex-1"
            />
            <StatusSelect
              value={form.status}
              onChange={(status) => setForm({ ...form, status })}
            />
          </div>
          <Input
            placeholder="summary"
            value={form.summary}
            onChange={(e) => setForm({ ...form, summary: e.target.value })}
          />
          <Input
            placeholder="tech (comma separated)"
            value={form.tech}
            onChange={(e) => setForm({ ...form, tech: e.target.value })}
          />
          <Input
            placeholder="next steps"
            value={form.next_steps}
            onChange={(e) => setForm({ ...form, next_steps: e.target.value })}
          />
          <div className="flex gap-2">
            <Input
              placeholder="repo path (Phase 3)"
              value={form.repo_path}
              onChange={(e) => setForm({ ...form, repo_path: e.target.value })}
              className="flex-1 text-faint"
            />
            <Input
              placeholder="repo url (Phase 3)"
              value={form.repo_url}
              onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
              className="flex-1 text-faint"
            />
          </div>
          <Button type="submit">Add project</Button>
        </form>

        <ul className="space-y-2">
          {projects.map((p) => (
            <li key={p.id} className="rounded-xl border border-hairline bg-surface">
              <button
                onClick={() => setOpen(open === p.id ? null : p.id)}
                className="flex w-full items-center gap-2 px-3.5 py-3 text-left text-sm"
              >
                <span className="font-medium">{p.name}</span>
                <Badge variant="secondary" className="text-[11px] font-normal">
                  {p.status}
                </Badge>
                {p.tech.map((t) => (
                  <span key={t} className="mono text-[11px] text-faint">
                    {t}
                  </span>
                ))}
                <span className="ml-auto text-faint">{open === p.id ? '▲' : '▼'}</span>
              </button>
              {open === p.id && <ProjectEditor project={p} onSaved={load} />}
            </li>
          ))}
          {projects.length === 0 && (
            <p className="text-sm text-faint">No projects yet.</p>
          )}
        </ul>
      </div>
    </div>
  )
}

function ProjectEditor({ project, onSaved }: { project: Project; onSaved: () => void }) {
  const [draft, setDraft] = useState({
    summary: project.summary,
    status: project.status,
    tech: project.tech.join(', '),
    next_steps: project.next_steps,
    notes: project.notes,
  })

  async function save() {
    await api.patch(`/projects/${project.id}`, {
      ...draft,
      tech: draft.tech.split(',').map((t) => t.trim()).filter(Boolean),
    })
    onSaved()
  }

  return (
    <div className="space-y-2 border-t border-hairline p-3.5 text-sm">
      <StatusSelect
        value={draft.status}
        onChange={(status) => setDraft({ ...draft, status })}
      />
      <Textarea
        value={draft.summary}
        onChange={(e) => setDraft({ ...draft, summary: e.target.value })}
        placeholder="summary"
        rows={2}
      />
      <Input
        value={draft.tech}
        onChange={(e) => setDraft({ ...draft, tech: e.target.value })}
        placeholder="tech"
      />
      <Textarea
        value={draft.next_steps}
        onChange={(e) => setDraft({ ...draft, next_steps: e.target.value })}
        placeholder="next steps"
        rows={2}
      />
      <Textarea
        value={draft.notes}
        onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
        placeholder="notes"
        rows={2}
      />
      <Button size="sm" onClick={save}>
        Save
      </Button>
    </div>
  )
}
