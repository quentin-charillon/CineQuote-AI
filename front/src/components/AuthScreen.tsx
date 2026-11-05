import { useState } from 'react'
import { accountApi, ApiError } from '../api/quizApi'
import type { User } from '../api/types'
import './Account.css'

export function AuthScreen({ onBack, onAuthenticated }: { onBack: () => void; onAuthenticated: (user: User) => void }) {
  const [mode, setMode] = useState<'login'|'register'>('login')
  const [email, setEmail] = useState(''); const [username, setUsername] = useState(''); const [password, setPassword] = useState('')
  const [error, setError] = useState<string|null>(null); const [loading, setLoading] = useState(false)
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setLoading(true); setError(null)
    try { onAuthenticated(mode === 'login' ? await accountApi.login(email,password) : await accountApi.register(email,username,password)) }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : 'Authentication failed.') }
    finally { setLoading(false) }
  }
  return <section className="account-shell"><nav className="account-nav"><strong>CineQuote <span>Play</span></strong><button onClick={onBack}>Back to cinema</button></nav><div className="account-card">
    <p className="quiz-kicker">Members only</p><h1>{mode === 'login' ? 'Welcome back.' : 'Join the cast.'}</h1>
    <div className="account-tabs"><button className={mode==='login'?'active':''} onClick={()=>setMode('login')}>Sign in</button><button className={mode==='register'?'active':''} onClick={()=>setMode('register')}>Create account</button></div>
    <form className="account-form" onSubmit={submit}>
      {mode==='register' && <label>Username<input required minLength={3} maxLength={30} value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username" /></label>}
      <label>Email<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email" /></label>
      <label>Password<input required type="password" minLength={mode==='register'?10:1} value={password} onChange={e=>setPassword(e.target.value)} autoComplete={mode==='login'?'current-password':'new-password'} /></label>
      {error && <p className="account-error" role="alert">{error}</p>}
      <button className="primary-action" disabled={loading}>{loading?'Please wait…':mode==='login'?'Sign in':'Create my account'}</button>
      {mode==='register' && <p className="account-note">Use at least 10 characters, including a letter and a number. Your password is salted and hashed before storage.</p>}
    </form>
  </div></section>
}
