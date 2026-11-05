import { useEffect, useRef, useState } from 'react'

import { ApiError, quizApi } from '../api/quizApi'
import type { Difficulty, Genre, QuizAvailability, User } from '../api/types'
import { FilmMark } from './FilmMark'
import './DifficultySelect.css'

interface Props { onSelect: (difficulty: Difficulty, genre: Genre) => void; onCustom: (prompt: string) => void; user: User | null; onAccount: () => void; onStats: () => void; onLogout: () => void; onBack: () => void }
type GameBuilder = 'classic' | 'custom' | null

const genres: Genre[] = ['all', 'horror', 'comedy', 'science_fiction', 'thriller', 'action', 'animation', 'romance', 'fantasy', 'adventure']
const descriptions: Record<Difficulty, string> = {
  easy: 'Iconic lines everyone knows.',
  medium: 'Familiar scenes that reward deeper recall.',
  hard: 'Subtle dialogue for true film buffs.',
}
const genreLabel = (genre: Genre) => genre === 'all' ? 'All Genres' : genre === 'romance' ? 'Romance / Musical Comedy' : genre.replace('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase())

export function DifficultySelect({ onSelect, onCustom, user, onAccount, onStats, onLogout, onBack }: Props) {
  const [availability, setAvailability] = useState<QuizAvailability[]>([])
  const [genre, setGenre] = useState<Genre>('all')
  const [builder, setBuilder] = useState<GameBuilder>('classic')
  const [error, setError] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const [customPrompt, setCustomPrompt] = useState('')
  const builderRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setError(null)
    quizApi.getAvailability().then(setAvailability).catch((caught: unknown) => setError(caught instanceof ApiError ? caught.message : 'Could not load the catalog.'))
  }, [reload])

  const openBuilder = (choice: Exclude<GameBuilder, null>) => {
    setBuilder(choice)
    window.setTimeout(() => builderRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0)
  }
  const selectedLevels = availability.filter(entry => entry.genre === genre)

  return <section className="difficulty-shell" aria-labelledby="difficulty-title">
    <div className="difficulty-grain" aria-hidden="true" />
    <nav className="difficulty-nav">
      <div className="difficulty-nav__left"><button className="selection-back" type="button" onClick={onBack}>← Back</button><div className="difficulty-brand"><FilmMark /><span>Cine</span><b>Quote</b></div></div>
      <div className="selection-account">{user ? <><span>{user.username}</span><button type="button" onClick={onStats}>My stats</button><button type="button" onClick={onLogout}>Sign out</button></> : <button className="sign-in" type="button" onClick={onAccount}>Sign in</button>}</div>
    </nav>

    <div className="difficulty-content">
      <div className="selection-hero">
        <div className="selection-copy">
          <p className="quiz-kicker">Now playing</p>
          <h1 id="difficulty-title">One line.<br/><em>Which film?</em></h1>
          <p className="difficulty-intro">Ten scenes. Four choices. Prove you were paying attention in the dark.</p>
          <div className="builder-actions">
            <button className={builder === 'classic' ? 'active' : ''} type="button" onClick={() => openBuilder('classic')}>Get your ticket <span>→</span></button>
            <button className={builder === 'custom' ? 'active secondary' : 'secondary'} type="button" onClick={() => openBuilder('custom')}>Build a custom quiz</button>
          </div>
        </div>
      </div>

      <div className="builder-zone" ref={builderRef}>
        {builder === 'custom' && <form className="custom-quiz mode-reveal" onSubmit={event => { event.preventDefault(); if (customPrompt.trim().length >= 3) onCustom(customPrompt.trim()) }}>
          <div><span>Custom screening</span><strong>Describe exactly what you want.</strong><p>Combine genres and choose one difficulty. Example: “A hard science-fiction and animation quiz.”</p></div>
          <div><input autoFocus value={customPrompt} onChange={event => setCustomPrompt(event.target.value)} minLength={3} maxLength={500} placeholder="Easy horror, or hard animation and fantasy…" aria-label="Custom quiz request"/><button type="submit" disabled={customPrompt.trim().length < 3}>Play it</button></div>
        </form>}

        {builder === 'classic' && <div className="classic-builder mode-reveal">
          {error ? <div className="difficulty-error" role="alert"><p>{error}</p><button type="button" onClick={() => setReload(value => value + 1)}>Retry</button></div>
          : availability.length === 0 ? <p className="difficulty-loading">Checking the film vault…</p>
          : <><p className="section-label">Pick your genre</p><div className="genre-picker" aria-label="Movie genre">{genres.map(item => <button key={item} type="button" className={genre === item ? 'selected' : ''} onClick={() => setGenre(item)}>{genreLabel(item)}</button>)}</div>
            <div className="difficulty-grid">{selectedLevels.map((level, index) => <button key={level.difficulty} type="button" className="difficulty-card" disabled={!level.available} onClick={() => onSelect(level.difficulty, genre)}>
              <span className="difficulty-number">0{index + 1}</span><strong>{level.difficulty}</strong><p>{descriptions[level.difficulty]}</p><span className={level.available ? 'available' : 'unavailable'}>{level.available ? 'Play now →' : 'Not available yet'}</span>
            </button>)}</div></>}
        </div>}
      </div>
    </div>
  </section>
}
