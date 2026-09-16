import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthShell } from '@/components/AuthShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await register(email, password)
      navigate('/')
    } catch (err: unknown) {
      const status =
        typeof err === 'object' && err && 'response' in err
          ? // @ts-expect-error narrow enough for a message
            err.response?.status
          : undefined
      if (status === 409) setError('That email is already registered.')
      else if (status === 422)
        setError('Password must be 8-72 characters with an uppercase letter and a digit.')
      else setError('Could not create the account.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Create your account"
      footer={
        <>
          Already have one?{' '}
          <Link to="/login" className="text-aqua hover:text-aqua-hi">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="mt-6 space-y-3">
        <Input
          type="email"
          required
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          type="password"
          required
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? 'Creating…' : 'Create account'}
        </Button>
      </form>
    </AuthShell>
  )
}
