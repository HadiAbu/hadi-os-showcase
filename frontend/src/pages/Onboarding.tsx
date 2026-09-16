import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Question {
  id: string
  type: 'text' | 'long_text' | 'single_select' | 'multi_select' | 'repeatable'
  prompt: string
  options?: string[]
}

type AnswerValue = string | string[]

const REPEATABLE_CAP = 5

export default function Onboarding() {
  const { onboarded, markOnboarded } = useAuth()
  const navigate = useNavigate()
  const [questions, setQuestions] = useState<Question[]>([])
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({})
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    api
      .get<Question[]>('/onboarding/questions')
      .then((r) => setQuestions(r.data))
      .catch(() => setNote('Could not load onboarding questions.'))
  }, [])

  const q = questions[step]
  const isLast = step === questions.length - 1
  const progress = questions.length ? Math.round((step / questions.length) * 100) : 0

  const setValue = useCallback((id: string, value: AnswerValue) => {
    setAnswers((prev) => ({ ...prev, [id]: value }))
  }, [])

  async function submit() {
    setBusy(true)
    setNote(null)
    try {
      const payloadAnswers = Object.entries(answers)
        .filter(([id]) => id !== 'style_samples')
        .map(([question_id, value]) => ({ question_id, value }))
      const samples = ((answers['style_samples'] as string[]) ?? [])
        .filter(Boolean)
        .map((text) => ({ text, label: null }))

      await api.post('/onboarding/submit', { answers: payloadAnswers, samples })
      markOnboarded()
      navigate('/')
    } catch {
      setNote('Something went wrong submitting. Your answers are still here — try again.')
    } finally {
      setBusy(false)
    }
  }

  if (!q) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg text-sm text-muted-fg">
        {note ?? 'Loading…'}
      </div>
    )
  }

  return (
    <div className="flex min-h-screen justify-center bg-bg px-6 pt-16 text-text">
      <div className="w-full max-w-lg">
        {onboarded && (
          <p className="mb-4 rounded-md border border-hairline bg-surface px-3 py-2 text-xs text-muted-fg">
            You've done this before — re-running adds to what hadi-os knows, it won't wipe anything.
          </p>
        )}
        <div className="h-1 w-full overflow-hidden rounded bg-hairline">
          <div className="h-full rounded bg-aqua transition-all" style={{ width: `${progress}%` }} />
        </div>

        <div className="mt-9">
          <h2 className="text-lg font-semibold">{q.prompt}</h2>
          <div className="mt-4">
            {/* key by question id so React remounts the field on each step —
                a reused controlled input drops fast-typed values between steps */}
            <QuestionInput
              key={q.id}
              question={q}
              value={answers[q.id]}
              onChange={(v) => setValue(q.id, v)}
            />
          </div>
        </div>

        {note && <p className="mt-4 text-sm text-destructive">{note}</p>}

        <div className="mt-9 flex items-center justify-between">
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0 || busy}
            className="text-sm text-muted-fg hover:text-text disabled:opacity-40"
          >
            Back
          </button>
          <Button onClick={isLast ? submit : () => setStep((s) => s + 1)} disabled={busy}>
            {isLast ? (busy ? 'Setting up…' : 'Finish') : 'Next'}
          </Button>
        </div>
        <p className="mt-3 text-right text-xs text-faint">
          {step + 1} / {questions.length}
        </p>
      </div>
    </div>
  )
}

function QuestionInput({
  question,
  value,
  onChange,
}: {
  question: Question
  value: AnswerValue | undefined
  onChange: (v: AnswerValue) => void
}) {
  const entries = useMemo(() => (Array.isArray(value) ? value : ['']), [value])

  if (question.type === 'multi_select') {
    const selected = Array.isArray(value) ? value : []
    return (
      <div className="flex flex-wrap gap-2">
        {(question.options ?? []).map((opt) => {
          const on = selected.includes(opt)
          return (
            <button
              key={opt}
              type="button"
              onClick={() =>
                onChange(on ? selected.filter((s) => s !== opt) : [...selected, opt])
              }
              className={cn(
                'rounded-full border px-3 py-1 text-sm transition-colors',
                on
                  ? 'border-aqua bg-aqua text-ink'
                  : 'border-hairline text-muted-fg hover:text-text',
              )}
            >
              {opt}
            </button>
          )
        })}
      </div>
    )
  }

  if (question.type === 'repeatable') {
    return (
      <div className="space-y-2">
        {entries.map((entry, i) => (
          <Textarea
            key={i}
            value={entry}
            rows={question.id === 'style_samples' ? 3 : 1}
            onChange={(e) => {
              const next = [...entries]
              next[i] = e.target.value
              onChange(next)
            }}
          />
        ))}
        {entries.length < REPEATABLE_CAP && (
          <button
            type="button"
            onClick={() => onChange([...entries, ''])}
            className="text-sm text-aqua hover:text-aqua-hi"
          >
            + add another
          </button>
        )}
      </div>
    )
  }

  const asText = typeof value === 'string' ? value : ''
  if (question.type === 'long_text') {
    return <Textarea value={asText} rows={4} onChange={(e) => onChange(e.target.value)} />
  }
  return <Input value={asText} onChange={(e) => onChange(e.target.value)} />
}
