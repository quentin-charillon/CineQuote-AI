import { useCallback, useEffect, useState } from 'react'

import { DifficultySelect } from './components/DifficultySelect'
import { Quiz } from './components/Quiz'
import { AuthScreen } from './components/AuthScreen'
import { StatsScreen } from './components/StatsScreen'
import { WelcomeScreen } from './components/WelcomeScreen'
import { BackendGate } from './components/BackendGate'
import { accountApi } from './api/quizApi'
import type { Difficulty, Genre, User } from './api/types'

type Screen = 'welcome' | 'selection' | 'multiplayer' | 'quiz' | 'auth' | 'stats'

export default function App() {
  const [screen, setScreen] = useState<Screen>('welcome')
  const [difficulty, setDifficulty] = useState<Difficulty>('easy')
  const [genre, setGenre] = useState<Genre>('all')
  const [user, setUser] = useState<User | null>(null)
  const [backendReady, setBackendReady] = useState(false)
  const [authChecked, setAuthChecked] = useState(false)
  const [statsRequested, setStatsRequested] = useState(false)
  const [customPrompt, setCustomPrompt] = useState<string | null>(null)
  useEffect(() => {
    if (!backendReady || authChecked) return
    accountApi.me().then(setUser).catch(() => setUser(null)).finally(() => setAuthChecked(true))
  }, [authChecked, backendReady])
  useEffect(() => {
    if (!statsRequested || !backendReady || !authChecked) return
    setStatsRequested(false)
    setScreen(user ? 'stats' : 'auth')
  }, [authChecked, backendReady, statsRequested, user])
  const logout = async () => { await accountApi.logout().catch(() => undefined); setUser(null) }
  const markBackendReady = useCallback(() => setBackendReady(true), [])

  return (
    <main>
      {screen === 'welcome' ? (
        <WelcomeScreen onSolo={() => setScreen('selection')} onMultiplayer={() => setScreen('multiplayer')} onStats={() => { setStatsRequested(true); setScreen('selection') }} />
      ) : screen === 'multiplayer' ? (
        <WelcomeScreen multiplayer onSolo={() => setScreen('selection')} onMultiplayer={() => setScreen('multiplayer')} onStats={() => { setStatsRequested(true); setScreen('selection') }} onBack={() => setScreen('welcome')} />
      ) : screen === 'auth' ? (
        <AuthScreen onBack={() => setScreen('selection')} onAuthenticated={(account) => { setUser(account); setScreen('selection') }} />
      ) : screen === 'stats' && user ? (
        <StatsScreen user={user} onBack={() => setScreen('selection')} />
      ) : screen === 'selection' ? (
        <BackendGate onReady={markBackendReady}>
          <DifficultySelect
            onSelect={(selected, selectedGenre) => { setCustomPrompt(null); setDifficulty(selected); setGenre(selectedGenre); setScreen('quiz') }}
            onCustom={(prompt) => { setCustomPrompt(prompt); setScreen('quiz') }}
            user={user}
            onAccount={() => setScreen('auth')}
            onStats={() => setScreen('stats')}
            onLogout={() => void logout()}
            onBack={() => setScreen('welcome')}
          />
        </BackendGate>
      ) : (
        <Quiz difficulty={difficulty} genre={genre} customPrompt={customPrompt} isAuthenticated={user !== null} onExit={() => setScreen('selection')} />
      )}
    </main>
  )
}

