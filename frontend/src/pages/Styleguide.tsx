import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const SWATCHES = [
  ['bg', 'var(--bg)'],
  ['rail', 'var(--rail)'],
  ['surface', 'var(--surface)'],
  ['raised', 'var(--raised)'],
  ['void', 'var(--void)'],
  ['hairline', 'var(--hairline)'],
  ['aqua', 'var(--aqua)'],
  ['warn', 'var(--warn)'],
  ['danger', 'var(--danger)'],
  ['node-proj', 'var(--node-proj)'],
  ['node-ctx', 'var(--node-ctx)'],
  ['node-act', 'var(--node-act)'],
]

/** Dev reference for the Phase-2 token system + shadcn primitives. Route: /styleguide */
export default function Styleguide() {
  return (
    <div className="min-h-screen bg-bg p-10 text-text">
      <h1 className="text-xl font-semibold">hadi-os design system</h1>
      <p className="mt-1 text-sm text-muted-fg">Turso palette · Hanken Grotesk / JetBrains Mono</p>

      <section className="mt-8">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-fg">Palette</h2>
        <div className="mt-3 grid grid-cols-6 gap-3">
          {SWATCHES.map(([name, value]) => (
            <div key={name} className="rounded-md border border-hairline p-2 text-xs">
              <div className="h-10 rounded" style={{ background: value }} />
              <div className="mt-1.5 text-muted-fg">{name}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8 flex flex-wrap items-center gap-3">
        <Button>Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="destructive">Destructive</Button>
        <Button size="sm">Small</Button>
        <Badge>Badge</Badge>
        <Badge variant="secondary">Secondary</Badge>
        <Badge variant="outline">Outline</Badge>
      </section>

      <section className="mt-8 grid max-w-3xl gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Card</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-fg">
            <p>Surfaces use <code className="mono">--surface</code>; borders <code className="mono">--hairline</code>.</p>
            <Input placeholder="An input on --bg" />
            <div className="mono text-2xl font-semibold text-text">418<span className="text-sm text-muted-fg">k tok</span></div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tabs</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="a">
              <TabsList>
                <TabsTrigger value="a">Entries</TabsTrigger>
                <TabsTrigger value="b">Review</TabsTrigger>
                <TabsTrigger value="c">Style</TabsTrigger>
              </TabsList>
              <TabsContent value="a" className="pt-3 text-sm text-muted-fg">Entries tab</TabsContent>
              <TabsContent value="b" className="pt-3 text-sm text-muted-fg">Review tab</TabsContent>
              <TabsContent value="c" className="pt-3 text-sm text-muted-fg">Style tab</TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
