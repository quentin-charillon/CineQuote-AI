import { useEffect, useState } from 'react'

import { DifficultySelect } from './components/DifficultySelect'
import { Quiz } from './components/Quiz'
import { AuthScreen } from './components/AuthScreen'
import { StatsScreen } from './components/StatsScreen'
import { accountApi } from './api/quizApi'
import type { Difficulty, Genre, User } from './api/types'

type Screen = 'selection' | 'quiz' | 'auth' | 'stats'

export default function App() {
  const [screen, setScreen] = useState<Screen>('selection')
  const [difficulty, setDifficulty] = useState<Difficulty>('easy')
  const [genre, setGenre] = useState<Genre>('all')
  const [user, setUser] = useState<User | null>(null)
  const [customPrompt, setCustomPrompt] = useState<string | null>(null)
  useEffect(() => { accountApi.me().then(setUser).catch(() => setUser(null)) }, [])
  const logout = async () => { await accountApi.logout().catch(() => undefined); setUser(null) }

  return (
    <main>
      {screen === 'auth' ? (
        <AuthScreen onBack={() => setScreen('selection')} onAuthenticated={(account) => { setUser(account); setScreen('selection') }} />
      ) : screen === 'stats' && user ? (
        <StatsScreen user={user} onBack={() => setScreen('selection')} />
      ) : screen === 'selection' ? (
        <DifficultySelect
          onSelect={(selected, selectedGenre) => { setCustomPrompt(null); setDifficulty(selected); setGenre(selectedGenre); setScreen('quiz') }}
          onCustom={(prompt) => { setCustomPrompt(prompt); setScreen('quiz') }}
          user={user}
          onAccount={() => setScreen('auth')}
          onStats={() => setScreen('stats')}
          onLogout={() => void logout()}
        />
      ) : (
        <Quiz difficulty={difficulty} genre={genre} customPrompt={customPrompt} isAuthenticated={user !== null} onExit={() => setScreen('selection')} />
      )}
    </main>
  )
}

