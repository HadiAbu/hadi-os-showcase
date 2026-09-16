import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthShell } from '@/components/AuthShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'

export default function Login() {
  const { login } = useAuth()
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
      await login(email, password)
      navigate('/')
    } catch (err: unknown) {
      const status =
        typeof err === 'object' && err && 'response' in err
          ? // @ts-expect-error narrow enough for a message
            err.response?.status
          : undefined
      setError(
        status === 423
          ? 'Account temporarily locked after too many attempts. Try again later.'
          : 'Invalid email or password.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Sign in"
      footer={
        <>
          No account?{' '}
          <Link to="/register" className="text-aqua hover:text-aqua-hi">
            Register
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
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
    </AuthShell>
  )
}
